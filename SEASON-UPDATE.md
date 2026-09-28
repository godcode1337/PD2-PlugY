# Updating for a new season (next: Season 14, Oct 23 2026)

> **Singleplayer doesn't work while only the beta is live.** Wait for the real season launch, then do the steps below.

Everything here is text-only: the `.d2s` characters and `pd2data.mpq` are only ever *read*.

## 0. Update the game
Run PD2 once through the normal **PD2 launcher**, let it patch, and close it. Check that
`C:\Program Files (x86)\Diablo II\ProjectD2\pd2data.mpq` now has a new modified date.

## 1. Extract the new season's tables
Needs Python 3 and StormLib (x64): download http://www.zezula.net/download/stormlib_dll.zip and unzip it somewhere,
e.g. `Desktop\PD2\tools\stormlib\` (that's where it lives now).

```powershell
cd Desktop\PD2\PD2-PlugY
python tools\extract_excel.py "C:\Program Files (x86)\Diablo II" reference\s14 ..\tools\stormlib\x64\StormLib.dll
```

This writes every `data\global\excel\*.txt` plus `strings.tsv` (internal name -> in-game name) to `reference\s14`.

## 2. Rebuild the testing modpack on top of it

```powershell
python tools\build_testing.py --base reference\s14 --old-base reference\s13
```

- New CubeMain = S14 CubeMain + every testing recipe that wasn't in S13 + the kit rows from `kits\kits.tsv`.
- New UniqueItems = S14 UniqueItems with `nolimit=1` on every row, which is the testing change.
- Output goes to both `ProjectD2\data\global\excel\` and `...\modpacks\testing\`.

Nothing is written if a kit item no longer exists, was renamed or disabled, has too many sockets, or if a kit's cube
inputs now clash with a new recipe. The script prints each problem instead.

If it says **"CubeMain columns changed"**, PD2 added or removed columns. Compare the header lines and fix the script
by hand; don't paste old rows into a new layout.

Upstream TDLofCC may also change their testing recipes. To pull them in:
1. `git fetch upstream`
2. Merge.
3. Run step 2 again.

## 3. Re-verify the kits
1. **Re-check each build's gear** against current guides (start at wiki.projectdiablo2.com, then pd2.tools usage stats), because items get reworked each season.
2. **Find internal names:** kits use internal names, not in-game names. Search `reference\s14\strings.tsv`:
   ```powershell
   Select-String reference\s14\strings.tsv -Pattern "Gore Rider"   # -> Gorerider<TAB>Gore Rider
   ```
   Also check that the internal name is in `UniqueItems.txt` / `SetItems.txt` column 1 exactly once.
3. **Check runeword recipes and allowed bases** in `reference\s14\Runes.txt`: the `Rune1-6` and `itype` columns.
4. **Check skiller prefix IDs:** these are the `*comment` column of `MagicPrefix.txt` (rows whose mod is `skilltab`). They shift if PD2 inserts affixes.
5. Edit `kits\kits.tsv` and repeat step 2 until it prints no errors.
6. Update `KITS.md`.

## 4. Deploy and save
1. Back up `Diablo II\ProjectD2\data` (zip it into `Desktop\PD2\Backups`).
2. Copy the rebuilt files in:
   ```powershell
   $r="$HOME\OneDrive\Desktop\PD2\PD2-PlugY\ProjectD2\data\global\excel"
   $d="C:\Program Files (x86)\Diablo II\ProjectD2\data\global\excel"
   foreach($f in "CubeMain.txt","UniqueItems.txt"){ Copy-Item "$r\$f" "$d\$f"; Copy-Item "$r\modpacks\testing\$f" "$d\modpacks\testing\$f" }
   ```
3. Test one kit in game using the **PD2 SP Testing** shortcut.
4. Commit and push:
   ```powershell
   git add -A; git commit -m "Season 14 update"; git push
   ```

Old characters may not load in a new season; see the README troubleshooting section (PD2-Converter).
