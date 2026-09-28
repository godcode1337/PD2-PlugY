"""Extract PD2's game tables using StormLib (read-only; nothing is written to the MPQs).

Usage: python extract_excel.py "<Diablo II folder>" <out_dir> <StormLib.dll>
Get StormLib.dll (x64) from http://www.zezula.net/download/stormlib_dll.zip

Writes:
  <out_dir>/*.txt        every data\\global\\excel\\*.txt from ProjectD2\\pd2data.mpq
  <out_dir>/strings.tsv  internal key -> in-game English name (vanilla + PD2 .tbl string tables),
                         used to find the internal UniqueItems/SetItems index for an in-game item name
"""
import ctypes, os, struct, sys, tempfile
from ctypes import wintypes

d2, out, dll_path = sys.argv[1:4]

S = ctypes.WinDLL(dll_path)
S.SFileOpenArchive.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
S.SFileOpenArchive.restype = ctypes.c_bool
S.SFileExtractFile.argtypes = [wintypes.HANDLE, ctypes.c_char_p, wintypes.LPCWSTR, wintypes.DWORD]
S.SFileExtractFile.restype = ctypes.c_bool
S.SFileCloseArchive.argtypes = [wintypes.HANDLE]
READ_ONLY = 0x100
tmp = tempfile.mkdtemp()


def open_mpq(path):
    h = wintypes.HANDLE()
    if not S.SFileOpenArchive(path, 0, READ_ONLY, ctypes.byref(h)):
        sys.exit(f"open failed {path}: {ctypes.GetLastError()}")
    return h


def extract(h, name, dst):
    return S.SFileExtractFile(h, name.encode("latin-1"), dst, 0)


def parse_tbl(path):
    b = open(path, "rb").read()
    _, n, hs, _, _, _, _ = struct.unpack_from("<HHIBIII", b, 0)
    base, d = 21 + 2 * n, {}
    for i in range(hs):
        used, _, _, ko, so, _ = struct.unpack_from("<BHIIIH", b, base + 17 * i)
        if used:
            d[b[ko:b.index(0, ko)].decode("latin-1")] = b[so:b.index(0, so)].decode("latin-1")
    return d


os.makedirs(out, exist_ok=True)

# 1) excel tables, located via the archive's own (listfile)
h = open_mpq(os.path.join(d2, "ProjectD2", "pd2data.mpq"))
lst = os.path.join(tmp, "listfile.txt")
if not extract(h, "(listfile)", lst):
    sys.exit(f"no (listfile): {ctypes.GetLastError()}")
excel = sorted({n for n in open(lst, encoding="latin-1").read().split()
                if n.lower().startswith("data\\global\\excel\\") and n.lower().endswith(".txt")})
failed = [n for n in excel if not extract(h, n, os.path.join(out, n.split("\\")[-1]))]
S.SFileCloseArchive(h)
print(f"{len(excel) - len(failed)}/{len(excel)} excel tables extracted", *failed)

# 2) string tables, later files override earlier ones (same order the game uses)
strings = {}
for mpq, tbl in [("d2data.mpq", "string"), ("d2exp.mpq", "expansionstring"), ("d2exp.mpq", "patchstring"),
                 ("patch_d2.mpq", "patchstring"), ("ProjectD2\\pd2data.mpq", "patchstring")]:
    h = open_mpq(os.path.join(d2, mpq))
    dst = os.path.join(tmp, "s.tbl")
    if extract(h, f"data\\local\\lng\\eng\\{tbl}.tbl", dst):
        strings.update(parse_tbl(dst))
    S.SFileCloseArchive(h)
with open(os.path.join(out, "strings.tsv"), "w", encoding="utf-8", newline="\n") as f:
    for k, v in strings.items():
        f.write(f"{k}\t{v.replace(chr(10), ' ')}\n")
print(f"{len(strings)} strings -> strings.tsv")
