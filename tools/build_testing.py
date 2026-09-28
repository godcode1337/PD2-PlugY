"""Rebuild the testing modpack (CubeMain.txt + UniqueItems.txt) and the bosser kit recipes.

    python tools/build_testing.py --base reference/s13 [--old-base reference/s13]

--base      folder with the current season's extracted excel txt files (from extract_excel.py)
--old-base  folder with the season the current testing files were built on (defaults to --base)

What it does:
  CubeMain    = base CubeMain + testing-only recipes (testing rows not in old base) + kit rows from kits/kits.tsv
  UniqueItems = base UniqueItems with nolimit=1 on every row (uniques not limited per game / rerollable)
Writes both to modpacks/testing/ AND ProjectD2/data/global/excel/ (the folder -direct -txt reads).
Aborts without writing if any kit references an item code / unique / set name that isn't in the base
files, or if a kit's cube inputs would also match an existing recipe.
"""
import argparse, os, re, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL = os.path.join(ROOT, "ProjectD2", "data", "global", "excel")
TESTING = os.path.join(EXCEL, "modpacks", "testing")
KITS = os.path.join(ROOT, "kits", "kits.tsv")
KIT_TAG = "KIT "  # description prefix for generated kit rows

# Kit input scheme: 1 Identify Scroll + 1 chipped gem (build color) + N Town Portal Scrolls (N = part).
GEMS = {"amethyst": "gcv", "topaz": "gcy", "sapphire": "gcb", "emerald": "gcg",
        "ruby": "gcr", "diamond": "gcw", "skull": "skc"}


def read(path):
    with open(path, encoding="latin-1", newline="") as f:
        return [l.rstrip("\r\n").split("\t") for l in f if l.strip("\r\n")]


def write(path, rows):
    with open(path, "w", encoding="latin-1", newline="") as f:
        f.write("".join("\t".join(r) + "\r\n" for r in rows))


def col(rows, name):
    return rows[0].index(name)


def load_items(base):
    """code -> (types), plus unique/set index names, item type equivalences, socket limits."""
    items, sockets = {}, {}
    for f in ("Armor", "Weapons", "Misc"):
        t = read(os.path.join(base, f + ".txt"))
        c, a, b, g = col(t, "code"), col(t, "type"), col(t, "type2"), col(t, "gemsockets")
        for r in t[1:]:
            if len(r) > c and r[c]:
                items[r[c]] = {r[a], r[b]} - {""}
                sockets[r[c]] = int(r[g] or 0)
    it = read(os.path.join(base, "ItemTypes.txt"))
    equiv = {r[1]: {r[2], r[3]} - {""} for r in it[1:] if len(r) > 3}
    ms = col(it, "MaxSock40")
    maxsock = {r[1]: int(r[ms] or 0) for r in it[1:] if len(r) > ms}
    u = read(os.path.join(base, "UniqueItems.txt"))
    uniq = {}  # index name -> [enabled flags]; an index can appear on several rows
    for r in u[1:]:
        uniq.setdefault(r[0], []).append(r[col(u, "enabled")] == "1")
    sets = {r[0]: r for r in read(os.path.join(base, "SetItems.txt"))[1:]}
    # pre=# in cube outputs is MagicPrefix's *comment id; keep its allowed item types
    mp = read(os.path.join(base, "MagicPrefix.txt"))
    ids = [col(mp, "itype%d" % i) for i in range(1, 8) if "itype%d" % i in mp[0]]
    prefixes = {r[col(mp, "*comment")]: {r[i] for i in ids if i < len(r)} - {""} for r in mp[1:]}
    return items, sockets, equiv, maxsock, uniq, sets, prefixes


def all_types(code, items, equiv):
    out, todo = {code}, list(items.get(code, ()))
    while todo:
        t = todo.pop()
        if t not in out:
            out.add(t)
            todo += equiv.get(t, ())
    return out


def recipe_matches(inputs, cube, items, equiv):
    """True if an existing recipe's inputs would accept exactly the cube contents (codes)."""
    need = []
    for x in inputs:
        parts = x.strip('"').split(",")
        q = next((int(p[4:]) for p in parts if p.startswith("qty=")), 1)
        need += [parts[0]] * q
    if len(need) != len(cube):
        return False
    types = [all_types(c, items, equiv) for c in cube]

    def bt(i, used):
        if i == len(need):
            return True
        return any(j not in used and need[i] in types[j] and bt(i + 1, used | {j}) for j in range(len(cube)))
    return bt(0, frozenset())


def kit_rows(header, items, sockets, maxsock, uniq, sets, prefixes, equiv, existing):
    """Parse kits/kits.tsv -> CubeMain rows. Returns (rows, errors)."""
    rows, errors, combos = [], [], {}
    H = {n: i for i, n in enumerate(header)}
    for n, line in enumerate(open(KITS, encoding="utf-8"), 1):
        line = line.rstrip("\r\n")
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split("\t")
        kit, gem, part, outs = f[0], f[1].lower(), int(f[2]), [o for o in f[3:6] if o]
        where = f"kits.tsv:{n} ({kit} part {part})"
        if gem not in GEMS:
            errors.append(f"{where}: unknown gem {gem}")
            continue
        if not 1 <= part <= 9 or not 1 <= len(outs) <= 3:
            errors.append(f"{where}: part must be 1-9 and 1-3 outputs")
            continue
        key = (gem, part)
        if key in combos:
            errors.append(f"{where}: combo already used by {combos[key]}")
        combos[key] = where
        for o in outs:
            q = o.split(",")
            name, quals = q[0], q[1:]
            if name in uniq:
                if uniq[name] != [True]:
                    errors.append(f"{where}: unique '{name}' is disabled or its index is used by several rows "
                                  f"{uniq[name]} - output '<base code>,uni' instead")
            elif name in sets:
                pass
            elif name in items:
                types = all_types(name, items, equiv)
                s = next((int(x[5:]) for x in quals if x.startswith("sock=")), 0)
                cap = min(sockets[name], max((maxsock.get(t, 0) for t in types), default=0))
                if s > cap:
                    errors.append(f"{where}: {name} can't have {s} sockets (max {cap})")
                for p in (x[4:] for x in quals if x.startswith("pre=")):
                    if p not in prefixes or not prefixes[p] & types:
                        errors.append(f"{where}: prefix {p} doesn't exist or can't spawn on {name}")
            else:
                errors.append(f"{where}: '{name}' is not an item code, unique or set item in the base files")
        cube = [GEMS[gem], "isc"] + ["tsc"] * part
        for r in existing:
            if r[H["enabled"]] == "1" and recipe_matches([x for x in r[H["input 1"]:H["input 7"] + 1] if x], cube, items, equiv):
                errors.append(f"{where}: inputs collide with existing recipe '{r[0]}'")
        row = [""] * len(header)
        row[H["description"]] = f"{KIT_TAG}{kit} part {part}"
        row[H["enabled"]] = "1"
        row[H["version"]] = "100"
        ins = [GEMS[gem], "isc", "tsc" if part == 1 else f'"tsc,qty={part}"']
        row[H["numinputs"]] = str(len(ins))
        for i, x in enumerate(ins):
            row[H[f"input {i + 1}"]] = x
        for c, o in zip(("output", "output b", "output c"), outs):
            row[H[c]] = f'"{o}"' if "," in o else o
        for lvl in ("lvl", "b lvl", "c lvl")[:len(outs)]:
            row[H[lvl]] = "99"
        for ilvl in ("ilvl", "b ilvl", "c ilvl")[:len(outs)]:
            row[H[ilvl]] = "100"
        row[H["*eol"]] = "0"
        rows.append(row)
    return rows, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--old-base")
    a = ap.parse_args()
    base, old = a.base, a.old_base or a.base

    new_cm = read(os.path.join(base, "CubeMain.txt"))
    old_cm = read(os.path.join(old, "CubeMain.txt"))
    cur_cm = read(os.path.join(TESTING, "CubeMain.txt"))
    if not (new_cm[0] == old_cm[0] == cur_cm[0]):
        sys.exit("CubeMain columns changed between seasons - compare headers and update this script by hand.")
    old_set = Counter(map(tuple, old_cm[1:]))
    extras = []
    for r in cur_cm[1:]:
        if r[0].strip('"').startswith(KIT_TAG):
            continue
        if old_set[tuple(r)]:
            old_set[tuple(r)] -= 1
        else:
            extras.append(r)

    items, sockets, equiv, maxsock, uniq, sets, prefixes = load_items(base)
    kits, errors = kit_rows(new_cm[0], items, sockets, maxsock, uniq, sets, prefixes, equiv, new_cm[1:] + extras)
    if errors:
        print("\n".join(errors))
        sys.exit(f"{len(errors)} kit error(s) - nothing written.")

    cube = [new_cm[0]] + new_cm[1:] + extras + kits
    ui = read(os.path.join(base, "UniqueItems.txt"))
    nl = col(ui, "nolimit")
    for r in ui[1:]:
        r[nl] = "1"
    for d in (TESTING, EXCEL):
        write(os.path.join(d, "CubeMain.txt"), cube)
        write(os.path.join(d, "UniqueItems.txt"), ui)
    print(f"CubeMain: {len(new_cm) - 1} base + {len(extras)} testing + {len(kits)} kit rows. "
          f"UniqueItems: {len(ui) - 1} rows. All kit items verified against {base}.")


if __name__ == "__main__":
    main()
