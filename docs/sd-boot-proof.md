# Leapster 2 SD boot: proof in emulation (Phase 2a)

Date: 2026-10-25. Status: **VERIFIED-EMU** (Ribbit, BIOS 0.6 `152-12206`). **Not yet tested on real hardware.**

## Result

A stock Leapster 2 with an SD slot (BIOS 0.6 / Connected B5) can boot a converted cartridge game from its SD
card **through its own home-screen menu**, with no extra hardware and no firmware changes:

1. On a PC, put on the card:
   * `\Leapster\System\SDMenu\SDMenu.bin`: the game image converted for SD (`research/sdpack.py`);
   * `\Leapster\Apps\<any folder>\meta.inf`: a text file containing `ProfileAccess="0,1,2"`.
2. In the console: sign in as a named player (not Guest). The arcade-cabinet icon (top right of the home
   screen) is now in colour. Tap it.
3. The BIOS writes `\Leapster\PlayGame.lnk` itself (the path of `SDMenu.bin`), restarts with boot selector
   0x0180_B008 = SD (`10`), shows "Loading…", copies the file to RAM at `0x3C80_0000` and starts its main movie.
4. Afterwards B008 is back to 0: the next power-on is a normal boot (no boot loop).

Shown in Ribbit for SpongeBob Saves the Day, 1st Grade and Learning with Leap (title screen, then name entry,
as from the cartridge). The full flow (first boot, setup, sign-in, icon, tap, game) passed on four card layouts:
the factory layout (FAT32, no partition table), **Windows-style FAT16 and FAT32 with a partition table**, and
FAT16 without a table.

## How the BIOS decides (VERIFIED-FW, BIOS 0.6; ActionScript of the main-menu movie at BIOS offset 0x5B01B8)

| Step | Code | Condition |
|---|---|---|
| Icon enabled | menu init 0x5B9F52.. | `BT_CheckStatus(1)` (card present) and `SD_CheckSDMenu()` (`SDMenu\SDMenu.bin` exists) and not `SD_CheckSDLocked()` and the user is not Guest |
| Tap | 0x5B50B2.. | `SD_GetNumGames(user) > 0` and no file `B:\Leapster\System\SDMenu\doom`; otherwise a "connect to the computer" warning plays |
| `SD_GetNumGames` | native 0x4002C670 → 0x4002C79C | counts directories in `B:\Leapster\Apps\` whose `meta.inf` has `ProfileAccess="a,b,c"` containing the user's number (0-2; up to 3 values, comma separated, read by 0x4002C918) |
| Launch | `StartSDGame()` → `BT_StartSDMenu()` (0x40022C8C) | writes `b:\Leapster\PlayGame.lnk` = path of SDMenu.bin, then the menu unloads its movies and the console restarts into SD boot |
| Load | `CopyGameFromSdFatToRam` (0x4004_0260) | reads up to 260 bytes of path from PlayGame.lnk (trailing CR/LF/space/tab removed), copies that file to 0x3C80_0000 in 512-byte blocks, **no size check** |
| Start | BaseROMApp | `howBooted='ExtStorage'`; `PlayMovie("Packed RIB Movie(s)", handle)` with the handle from the image's 0x2000 descriptor |

Natives available to Flash content (registration table pairs `name, function`): `SD_Dir`, `SD_CheckFile`,
`SD_ReadText`, `SD_WriteText`, `SD_GetNumGames`, `SD_CheckSDMenu`, `SD_CheckSDLocked`, `SD_MakeDir`, `SD_DeleteFile`,
`BT_StartSDGame`, `BT_StartSDMenu`, `BT_SetNextBoot`, `BT_Execute`, `BT_CheckStatus`, …

## Converting a cartridge image (research/sdpack.py)

The image must be **relocated** from 0x8000_0000 to 0x3C80_0000. Only fields whose meaning is known are
rewritten; images with anything else are refused.

| Field | Rule |
|---|---|
| RIB header +0x1C/+0x20/+0x24/+0x28 (base, end, end+8, pointer to checksum) | relocate |
| 0x140 (pointer to the LEAP directory, in both layouts) | relocate |
| LEAP directory entries | relocate the sub-entry list pointer |
| Sub-entry values | relocate if inside the image (otherwise immediates) |
| 0x1006 tables `{0x100, 0, first handle, count, ptr[count]}` | relocate `ptr[]` only. **`first handle` is a number used by ActionScript, not an address** |
| 0x2000 `{0x00010100, 0, 0, main-movie handle}` | **unchanged**: the handle (e.g. 0x8000_0006) only looks like an address |
| 0x1003, 0x1005, 0x100C | unchanged (no pointers seen) |
| Header checksum | recomputed (sum of one word every 0xF94 bytes from base to end) |
| Other tags (0x1000, 0x1001, 0x1009, 0x100D, 0x3001) | **refused**: they carry native ARC code or unknown structures |

Coverage of the user's 37 dumps: **3 supported** (SpongeBob Saves the Day, 1st Grade, Learning with Leap: 2003
Flash-only titles). 2 are 16 MiB (too big for the 8 MiB load area). 32 contain native-code resources
(0x1000/0x1009, many also 0x1001/0x3001); supporting them needs code relocation (planned: find absolute
cartridge addresses in the ARC code with Ribbit's decoder; Ribbit's unmapped-access log exposes misses).

Open: 1006/5 in SpongeBob declares 11 entries but 22 pointers follow; the extra 11 are not referenced by any
known structure and are left unchanged (no effect seen).

## Limitations found

* **Saves:** SD-loaded games use the cartridge save chip (I²C device 0x20), which is absent; commands time out
  and games read garbage (1st Grade's Sign In list shows junk names). No saves until a solution is found.
* **One game at a time** with the stock flow (SDMenu.bin is a single file). A homebrew `SDMenu.bin` menu is the
  way to several games (Phase 4).
* **8 MiB maximum** image size; CIP3 (m9) units have no SD slot (NAND only); only BIOS 0.6 was run end to end
  (B5 and m9 contain the same code paths).
* **SDHC:** the BIOS parses both CSD versions (0x400C_F322), so SDHC is anticipated, but Ribbit emulates only a
  1 GiB standard-capacity card: untested. Use a ≤ 2 GB SD card for the first hardware test.

## Reproduce

```
research/sdboot-emu   (Rust; needs the Ribbit checkout next to LeapLoader)
  cargo build --release
  target/release/sdboot-emu --bios <BIOS 0.6> --b008 1 --card-format mbr-fat16 \
    --put "Leapster/System/SDMenu/SDMenu.bin=<converted.bin>" \
    --put "Leapster/Apps/Game1/meta.inf=<meta.inf>" --script <setup+tap script> [--view]
python research/sdpack.py <cartridge.bin> <converted.bin>
```

The setup script used: run 21000, tap 42 95 (U.S.A.), tap 80 132 (OK), type a name, OK, tap the name, run
40000, tap 120 33 (SD icon), run 45000.

## Ribbit

No inaccuracies requiring changes to Ribbit were found in this work; Ribbit is unmodified.
