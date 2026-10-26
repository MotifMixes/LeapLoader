# How LeapLoader runs cartridge games from the SD card

Last updated 2026-10-25. Everything here targets **Leapster 2 BIOS 0.6** (`152-12206`, CRC fa94d9a7).
Labels: **VERIFIED-EMU** = seen working in the emulator (research/sdboot-emu, built on Ribbit),
**VERIFIED-FW** = read from the BIOS/game code, **UNVERIFIED** = expected but not tested.
**Nothing has been tested on real hardware yet.**

Per-game results: [games.md](games.md). Background: [research-report.md](research-report.md),
[sd-boot-proof.md](sd-boot-proof.md). Current state and next steps: [HANDOFF.md](HANDOFF.md).

## 1. The card

```
Leapster/System/SDMenu/SDMenu.bin   the menu the home screen's SD icon boots
Leapster/Apps/<Game>/game.bin       the game, converted for SD (research/sdpack.py)
Leapster/Apps/<Game>/meta.inf       LeapFrog's fields; ProfileAccess "0,1,2" = all three players
Leapster/Apps/<Game>/icon.swf       the game's round button (research/icongen.py)
Leapster/Apps/<Game>/save.dat       saves, ActionScript kinds (hex text; created on first save)
Leapster/Apps/<Game>/save.bin       saves, native chip (binary; created on first save)
```
Built by `research/mkcard.py [--menu leaploader|LSTR-0x00130001-000000.lfp] OUT_DIR DUMPS...`.

The BIOS copies `game.bin` to RAM at **0x3C80_0000** and runs it. RAM ends at 0x3D00_0000, so an
image may be at most **8 MiB** (VERIFIED-FW/EMU).

## 2. Menus

| Menu | How to get it | Notes |
|---|---|---|
| LeapLoader menu (default) | `mkcard.py OUT DUMPS` | Our own list menu, optional background music (`--music SONG.mid --music-loop SECONDS`). VERIFIED-EMU |
| LeapFrog's own SD menu ("vanilla") | `mkcard.py --menu LSTR-0x00130001-000000.lfp OUT DUMPS` | VERIFIED-EMU with 72 games |

LeapLoader menu v0.3.0 (`research/menugen.py`; all VERIFIED-EMU with 77 titles, 2026-10-25):
* **Game names** from `research/gamenames.py`: the box name of every known dump, by the CRC-32 of the
  dump file (file names are often codes like `letrfactry.bin`, and the cartridge's own title field is an
  internal name like "PUZ - Puzzle Power"); else a cleaned-up file name; else the title field. Folders
  on the card keep their old names (from the file name), so saves stay with their games.
* **Tool column** right of the list (touch): a magnifying glass (opens the search keyboard straight
  from the list; Pause on the keyboard goes back to where it was opened) and up/down arrows that move
  a page (4 games). The D-pad's left/right also move a page. The arrows hide when everything fits.
  A touched tool key lights up (the yellow glow) for 6 frames; paging with the D-pad lights its arrow.
* **Sounds for moves:** the BIOS home screen's D-pad sounds, lfh(29) for a move back/up and lfh(27)
  for a move on/down (`doDPadNarr` in BIOS movie 0x5B_01B8 = LPSR_BROM_MenuUp_6 / MenuDown_6;
  lfh() of the name string plays the BIOS's error beep instead), on the D-pad and the arrows.
* **Keyboard:** delete, **CLR** (clears the text) and OK on the bottom row; OK blinks for 8 frames
  before the search runs (no keys meanwhile).
* **Marquee:** a newly selected long title scrolls at once, 2 pixels a frame (a pause at each end
  after the first round).
* **Footer:** a 10-pixel bar with only the version number (no control hints).
* **Music volume:** `LF_SetRawVolume(127)` around each music part's start too (voice volume 0x7FFF).
* **Background music** (`--music SONG.mid`, `--music-loop 20.21`): the MIDI is rendered with the
  BIOS's own instruments into one 8 kHz A-law clip (`research/musicrender.py`) and played with
  `LF_PlayAudioRaw`, so every note of every track sounds (the BIOS sequencer has only 5 voices: the
  user's 13-track song lost ~800 notes there). Rendering: each track on its own at 48 kHz float from
  16x upsampled samples, the BIOS's zone choice, pitch formula and frequency table, loops, velocity as
  a SoundFont's default curve; then mixed, low-passed to 8 kHz, dithered, A-law. Checked against the
  BIOS sequencer playing one track (bass, track 038) in the emulator: envelope correlation 0.976, same
  pitch in 49 of 55 quarter-second windows. The song plays once from its start, then loops from
  `--music-loop`: two raw sounds in the same bytes (intro; loop part with 80 entry points 1 ms apart).
  tick() (once a frame) stops the playing part with `LF_StopAudioPlayer` and starts the loop part at
  the music's current place, so the joins are seamless (measured within ~2 ms, 128 s run).
  Raw-sound facts found on the way (BIOS 0.6):
  * For a raw sound of 64 KiB or more the BIOS does not write the real end's low half but reads it
    back from the voice's start-low register (0x0180_40C8 + 8 x voice; 0x4003_64F8). Ribbit reads 0,
    so such sounds stopped up to 8 s early; the hardware's value is UNVERIFIED. Each music part
    therefore runs on 64 KiB past its join.
  * `LF_StopAllAudio` and `LF_StopAudioPlayer` send the pause command (0x20 | voice); the BIOS then
    takes free voices from the status register. Ribbit counted paused voices as busy and the music
    stopped at its second loop; fixed in Ribbit (`docs/changes-from-leaploader.md` there).
  * There is a fixed ~7 ms between starting the next part and it lining up (calibrated:
    `MUSIC_JOIN_LEAD_MS`).
  * `LF_PlayAudioRaw` returns the audio player's id (for `LF_StopAudioPlayer`).
* **Welcome sound** when it starts (`assets/welcome.mp3`, the user's; `mkcard.py --welcome FILE|none`):
  `research/sndgen.py` `load_alaw` turns any audio into 8 kHz G.711 A-law, stored as the menu
  image's raw-sound table (resource 0x1006/5, handle 0x8000) and played with
  `LF_PlayAudioRaw(lfh(0x8000))`, the way the BIOS plays its own sounds. Plays over the menu music,
  louder than the narrator: `LF_SetRawVolume(127)` just before it starts and back to the BIOS's 100
  after (voice volume 0x7FFF instead of 0x273E, +10 dB, VERIFIED-EMU; the volume is latched when the
  voice starts). v0.2.0 played it at the narrator's level and it sounded too quiet. Output = the
  A-law clip exactly (correlation 1.00000).
  * Raw-sound table format (BIOS table at 0x4000_5C2C, VERIFIED-FW + EMU): `{0x100, 0, first
    handle, count}` then `count` pointers in **(start, end) pairs**; handle first + i plays pair i
    (the BIOS select sound lfh(28) = pointers 56/57, its output matches the A-law source at
    correlation 0.99999).
  * Why not a SWF sound (v0.2.0 used SWF ADPCM, 11025 Hz): the player mixes SWF sound into the
    32 kHz PCM DAC stream through a **band-pass of about 300-5500 Hz**, at every SWF rate (5.5, 11,
    22, 44 kHz), measured on white noise: under 250 Hz -30 to -40 dB and incoherent, flat 350-5000
    Hz. The voice lost its low end and sounded thin next to the narrator (the user noticed). The
    ADPCM itself was fine (the player decodes it exactly as `sndgen.adpcm_decode`; round trip
    23 dB SNR).
* **Pause** opens Options: Search (top), Resume, Music On/Off, Sort A-Z / Recent, Leapster Home, About.
  B or Pause goes back. Touch works on every row and key.
* **Search**: an on-screen keyboard laid out like the console's name entry (7 x 4: A-Z, ".", space; then
  delete and OK), drawn by us. D-pad + A or touch; B deletes; Pause cancels. Sounds: the BIOS's letter
  sound lfh(29) per key, lfh(28) on OK. Finds the text anywhere in a title ("ZZ" -> Get Puzzled!); the
  list then shows "Search: TEXT" or "No games found."; an empty search shows everything again.
* **Settings** `b:\Leapster\System\SDMenu\LeapLoader.txt` = `LL1|music|sort|recent path|...|` (10 most
  recent games, saved when a game starts). `SD_WriteText` creates the file.
* **Home** goes back to the console (below).

Buttons: the button callback (event type 3) gets UP 256, DOWN 512, LEFT 1024, RIGHT 2048, A 4096,
B 8192, HOME 16384, HINT 32768. **Pause is not a button bit**: it is a system button, event type 5
(`ret1..3` = sysButton, bIsPressed, newSysValue), `LF_PAUSE_BUTTON` = 8, as the BIOS's
`UI_HandleSystemButtons` reads it (BIOS movie 0x61_7020).

**ActionScript speed on the Leapster's Flash player** (BIOS 0.6, timed with `getTimer()` in the emulator):
* String **methods** cost about **12 ms per character of the string they are called on**:
  `indexOf` on a 69-character title takes 0.93 s, on 17 characters 0.19 s. `split` on a long string is
  as slow. `Array.join` of 30 short strings: 70 ms.
* **Opcodes are fast** (under 1 ms): StringLength 0x14, StringExtract 0x15 (1-based), StringLess 0x29,
  Equals2, StringAdd 0x21, chr 0x33, GetMember. 3000 plain loop steps: 1.5 s.
* **A script that runs longer than about 6-7 s freezes the player** (no error; the screen stops). So the
  menu uses only opcodes on strings: the search is a binary search (StringLess) in a sorted list of
  every title position (capitals, 12 characters) made at build time, and the settings file is parsed one
  character at a time.
* Only named **sprites** can be moved or hidden by path; a named shape cannot (wrap it in a sprite).
* `pressed & bit` is a number (e.g. 512); combine conditions with BitAnd only as booleans (`!= 0`),
  else 512 & 1 = 0.
* **Home** goes back to the console: `BT_StartSDGame("LeapLoader\home.txt")`, a small text file mkcard
  writes. The BIOS reads it, finds no game in it and boots normally (logo, Sign In) at once, silently
  (VERIFIED-EMU). v0.2.0 used a file that does not exist: the BIOS then beeps 17 times over ~7 s and
  restarts twice (the user heard it). Older notes: v0.2.0 used `LeapLoader\home.none`, a file that does not
  exist. The console restarts, `CopyGameFromSdFatToRam` fails, and the BIOS boots normally (logo, then
  Sign In). Tried first, with no effect from the SD menu: `BT_Execute("System")`,
  `BT_Execute("Application")`, `BT_SetNextBoot(0 or 1)` + `BT_Execute(...)`. (`BT_Execute("TheCartridge")`
  is how the BIOS menu starts a cartridge; BT_Execute = 0x4002_2A38, BT_SetNextBoot = 0x4002_2D00.)
  LeapFrog's own SD menu ignores Home.
* The BIOS's name-entry keyboard (movie at BIOS 0x5D_3020: `mc_keyBoard`, `initKeyBoard`) is part of
  the sign-in movie and exports nothing, so a menu cannot borrow it.

LeapFrog's menu (VERIFIED-FW from its ActionScript, VERIFIED-EMU in use):
* counts the games with its own native `SDM_GetNumGames` (folders in `B:\Leapster\Apps\` whose
  `meta.inf` lists the signed-in player in `ProfileAccess`);
* shows **6 per page** in a 3 x 2 grid (x = 15 + 45 * column, y = 40 + 45 * row) with **Back/Next
  arrows** at the bottom; 72 games = 12 pages;
* draws each button from the game's `icon.swf` (ours: a 36-pixel disc with the title, centred at 18, 18);
* marks a game "corrupt" (grey) if its `meta.inf` or `BinFile` is missing, or a file named `doom`
  is in its folder;
* starts a game with `BT_StartSDGame`.

Emulator pitfall: do not test LeapFrog's menu from a saved emulator state taken while another card
was in. The Flash player keeps the icon movies it loaded under fixed temporary names and shows those
stale icons, drawn huge. Boot the console fresh (setup, sign in, tap the SD icon) instead.

## 3. Back to the menu: HINT + A + B

Holding **HINT + A + B** in a game shows "Back to the LeapLoader menu" (or "Back to the **SD Menu**"
when LeapFrog's menu is on the card); keep holding until the bar fills (2.5 s), let go to cancel
(the prompt no longer says so: that line overlapped the bar).
Then pending saves are written and `BT_StartSDMenu` (BIOS 0x4002_2C8C) reboots into whatever
`SDMenu.bin` is on the card, so it returns to the vanilla menu too (VERIFIED-EMU, page 1).
PAUSE cannot be used: the BIOS freezes the Flash player while it is held. Code: `research/ingame.py`.
* **The prompt movie is appended to the game's own movie table** (handle first + count; the 0x1006
  entry points at an extended copy). Until 2026-10-25 it had a one-entry table of its own (handle
  0x8000_FF00), which the player did not find in every game: the prompt never loaded in Cars, I Spy
  Challenger, Creature Create (VERIFIED-EMU; it was always so, not a regression).
* **Native games poll the buttons:** some games keep the button events from the ActionScript
  listener (Kindergarten, I Spy, Creature Create: no prompt and no return before). The RAM chip
  stub's `__llEE()` (called every frame by the save flusher) now adds 2^29 to its result while
  ButtonMPI's GetButtonState shows HINT + A + B; the flusher strips it and sets `_level0.__llK`,
  which the watcher uses. (A second native, `__llKB`, was never found by the player, in the same
  0x1009 resource or its own.) VERIFIED-EMU: Kindergarten, I Spy Challenger, Creature Create show the
  prompt and return (I Spy's prompt comes ~1 s late; the game runs slowly).
* **Cars** (fixed 2026-10-25, VERIFIED-EMU): the keys did reach `__llK` and the prompt showed; the
  return died in the save written before leaving: the ActionScript writer joined Cars' 2 KB chip
  into 4096 characters, which took ~10 s and the player ended the script before `BT_StartSDMenu`.
  The stub now writes the file itself (section 4b).

**Games on the native chip (section 4c)** have no room for the ActionScript prompt, so they get a
native version (`research/nativechip.py`, VERIFIED-EMU on Go Diego Go): no prompt on screen, but
holding HINT + A + B for 2.5 s goes back to the menu the same way.
* The BIOS reaches the buttons through ButtonMPI, whose function table address is in RAM at
  **[[gp+4] + 0x7C]** (ROM table 0x4013_2874: +4 GetButtonState(out) -> out[0] = pressed buttons,
  out[1] = changed; +8 the poll, which the button task calls **every 10 ms** through that RAM
  pointer, BIOS 0x400B_1FB8; VERIFIED-FW/EMU).
* The chip's install (first call of any of the game's natives) puts a copy of that table in RAM
  whose +8 calls the original poll, then GetButtonState, and counts polls with HINT, A and B held
  (pressed bits 0x1000_0000, 0x4000, 0x2000, the GPIO bits Ribbit uses). At 250 (2.5 s) it does what
  `BT_StartSDMenu` does: the path from 0x400F_16C8(buf, 100, "System" at 0x3C7F_B3D0, 1,
  "SDMenu\SDMenu.bin"), then 0x4002_2AA8(path), which writes `PlayGame.lnk` and restarts the console
  into the menu. The chip writes every save at once, so nothing is pending.

**Fallback for screens where no script runs** (2026-10-26, VERIFIED-EMU: all 77 dumps go back): on
name-entry keyboards and during videos the game's ActionScript doesn't run, so neither the prompt nor
the save flusher sees the keys (Sonic X, NASCAR, Schoolhouse Rock; it was always so, also with the
old AS shim). The RAM chip stub (`eestub.py`) now wraps ButtonMPI's poll too, like the native chip;
held 4 s (after the prompt would already have gone back) it restarts into the menu.
* **No file access from the button task.** A save written from it hung the console while
  Schoolhouse Rock streamed a video from the card, and BT_StartSDMenu's own PlayGame.lnk write from
  it failed (console went to its home screen: the WALL-E prototype's "Base selected").
* So both stubs write **PlayGame.lnk = the menu's path** once at install, in the game's context
  (as 0x4002_2AA8 does: path 0x400F_16C8, .lnk path 0x400F_1724(buf, 260, 1), fopen "w+",
  fwrite(strlen)), and the poll only calls **LC_Boot("ExtStorage")** (0x400F_0674 with 0x400F_78FC),
  the restart that reads it. A power-on still boots the console's home screen (it ignores the .lnk).
* Saves still pending when the fallback fires are not written (they are written 10 quiet frames
  after each change, so normally nothing is pending).

The [gp+4] structure is a list of BIOS services `{0, descriptor table, function table}`, one every
12 bytes; the function tables end with the service's name (ButtonMPI at +0x7C, EEpromMPI at +0x88,
the Flash player's at +0x64).

## 4. Saves

On a cartridge, games save to the cartridge's I2C EEPROM ("save chip", 256 B to 2 KB, size in the
game's resource 0x1005/3 at +0x14). Booted from SD there is no chip: every access fails and games
show leftover RAM as player names (VERIFIED-EMU). The BIOS reaches the chip through a table of
functions whose address is in RAM at **[[gp+4] + 0x88]** (0x3C00_01D4 -> 0x4013_3420):
+0 write with checksum, +4 read with checksum, +8 write, +0xC read, +0x10 size; device 0 is the
console's own memory (emulated in flash), devices 1-3 are the cartridge chip (VERIFIED-FW/EMU).
LeapLoader uses one of three ways, picked automatically by `sdpack.convert`:

**Since 2026-10-25 every game uses 4b** (the RAM chip; Flash-only games' LF_* natives reach it
through the BIOS's EEPROM table). 4a is kept behind `LL_AS_SHIM=1`: it read the save byte by byte
in ActionScript at start (1st Grade's title came ~4 s later than with 4b, VERIFIED-EMU).

### 4a. Flash-only games: the ActionScript shim (`research/saveshim.py`, now only with LL_AS_SHIM=1)
Games without native code save through the BIOS natives `LF_ReadCartridgeMemoryBytes`,
`LF_WriteCartridgeMemoryString`, ... Every movie's calls to them are renamed (same length, so no
movie changes size) to `_level0:__llXX` functions injected into the main movie. Those keep the
memory in ActionScript arrays, load `save.dat` at start (`SD_ReadText`) and write it (`SD_WriteText`)
the frame after a change. Semantics copied from BIOS 0x400A_0528-0x400A_0896 (byte order, sign
extension, string padding, address wrap-around, floats as IEEE singles). VERIFIED-EMU.

### 4b. Native games with room: the RAM save chip (`research/eestub.py` + `saveshim.build_ee_loader`)
Native code calls the EEPROM table directly, so renaming natives is not enough. A small ARC stub
(added as one more 0x1009 resource with the native `__llEE()`) replaces the table with a copy whose
four data functions serve devices 1-3 from a RAM buffer and pass device 0 to the BIOS. The main
movie's injected ActionScript calls `__llEE(0)` once (install; the stub reads `save.dat`, hex, with
the BIOS's fopen/fread) and `__llEE(0)` every frame; the stub writes the whole chip as hex
(fopen/fwrite) after 10 calls without changes (Star Wars Jedi Reading formats its memory a little
per frame), or at once on `__llEE(1)` (leaving with HINT + A + B). Until 2026-10-25 loading and
writing were ActionScript (slow: Cars' 2 KB chip took ~10 s to write). A Flash-only game without a
0x1009 list gets a copy of the resource directory with a 0x1009 entry (header 0x140 repointed).
VERIFIED-EMU: load (marker bytes) and write-back in Cars and 1st Grade.

### 4c. Native games without room: the native chip (`research/nativechip.py`, new 2026-10-25)
4a and 4b need a copy of the main movie (the injected ActionScript makes it longer, so it must move),
often 100+ KB. Ten 8 MiB games have no space for that. The native chip needs only ~1-2 KB:
* every function pointer in the game's 0x1009 native lists is pointed at an 8-byte trampoline
  (`mov r12, k; b common`); the first call of any native installs the chip, then every call jumps
  to the original function. ActionScript enters native code only through these natives, so the
  chip is in place before the game's code can reach the EEPROM;
* the chip's memory comes from the BIOS's `malloc` (0x400F_1FDC), filled from `save.bin` at install;
  it starts **zeroed**, not erased (0xFF): Pet Pals and Finding Nemo show an erased chip as junk
  player names ("ÿÿÿÿ…"), and with zeros they start their new-player flow; Clifford too
  (VERIFIED-EMU; `LL_CHIP_FILL=0xff` restores the old fill for tests);
* every write saves the whole chip to `save.bin` (`fopen` 0x400F_0830 with "w", `fwrite`
  0x400F_09C8, `fclose` 0x400F_06A0; read with `fread` 0x400F_0890), the BIOS's own C library
  (VERIFIED-FW: the calls `SD_ReadText`/`SD_WriteText` make);
* the code goes into a run of 0xFF/0x00 padding no known pointer reaches (`sdpack.gap`, 256-byte
  margins), usually just before the image's trailer.
Go Diego Go: VERIFIED-EMU (no failed chip commands, `save.bin` written, game runs).
Not yet verified: that a saved game loads back after a restart.

### Not yet proven for any kind
A full "save in the game, power off, power on, progress is still there" test.

## 5. Converting a cartridge image (`research/sdpack.py`)

A cartridge image is built for address 0x8000_0000; every pointer must move to 0x3C80_0000.
Only fields whose meaning is known are rewritten; unknown resource types make the converter refuse.
* RIB header (0x11C-0x128, 0x140) and the LEAP resource directory; every directory entry.
* 0x1006 tables `{0x100, flags, first handle, count, pointers[count]}`: the pointers (the first
  handle is a number the game's ActionScript uses, not an address), null slots skipped, and a
  **second address array** right after the first where present (sound tables).
* Instrument banks (table 2, first handle 0x2000): 20-byte zones, start/end pointers.
* **Fonts**: every entry of the font table 0x1006/1, whatever its first word (0x0101_0100 usually;
  **Bratz World's is 0x0650_0100**), and the last resource of an image runs to the image's end.
  Inside a font, every word pointing into the same font is relocated.
* **Bitmaps with a pointer to their own pixel data** in their first 0x20 bytes: Scooby-Doo Arcade's
  table 13 `{data = +0x14, 2, width, height, size}`, Go Diego Go's and Schoolhouse Rock's table 16
  `{width, height, data = +8}`.
* Save descriptor 0x1005/3 (long form: three functions and a data address at +0x1C..+0x28).
* **Native ARC code** (resources 0x1000/0x1001/0x1009/0x100D/0x3001): `research/nativescan` finds
  every absolute address in code and data (long immediates, data words, switch tables, INI blocks).
  **Data words from 0x8000_0000 up to 0x8000_0000 + (the largest table's entry count, at least
  0x100) are left alone**: they are resource handles (0x8000_0000 + index), not pointers. Go Diego
  Go's 0x100D lists hold 571 of them, Rock the World's go up to 0x8000_1A1F (its table 9 has 6687
  entries). Relocating them broke both games' native apps (white/black screens) until 2026-10-25.
  No exception is made for handles that equal a resource's address (0x8000_0000 is also the
  header, 0x8000_0010 the 0x1001 list): making one broke Go Diego Go again.
* **0x100D/11 handle lists** `{0x0100_0100, kind, pairs}` (fixed 2026-10-26, VERIFIED-EMU): pairs
  `{count, address of count handles}` up to a count of 0; each address is relocated. nativescan found
  them only where they lie in native data, so in Cosmic Math, Letterpillar, Number Raiders, Word
  Chasers, The Batman: Strength in Numbers, Rock the World (3), WALL-E (48) and 2nd Grade (1) some
  stayed at 0x8000_xxxx. The game then read its sound handles from the empty cartridge window, got
  0, and at the first sound the BIOS asserted `{ResolveHandle(x0)Fail}` (message saved at
  0x0300_FF00, B008 bit 0 set) and restarted to its home screen ("Base selected"). The four 4 MiB
  games never got past their first sound before this; their "name entry" screenshots were the
  console's own profile keyboard. Traced: sound request 0x4002_EFC8 (handle in r0) <- game code
  reading `[[obj + 0x1C] + 4 * index]`, obj = 0x8000_1B14 (Cosmic Math) = the pair list.
* The header checksum (one word every 0xF94 bytes, BIOS 0x4005_28A4) is recomputed.

### Dump problems handled
| Problem | Seen in | What happens |
|---|---|---|
| A 24-byte text marker (`LBK...`) inserted by the dumping tool at a 4 KiB boundary, shifting everything after it | Cars Supercharged (`LBK00000014000000018a813` at 0x40_0000) | `sdpack.repair` removes it, but only if the checksum then matches |
| Checksum never written (FFFFFFFF) | Ni Hao Kai-lan | converted anyway, noted "CHECKSUM MISMATCH" |
| Checksum differs for an unknown reason | Penguins of Madagascar (old dump) | converted anyway; still black, as a cartridge too. The dump was damaged: a new dump (checksum OK) runs |

## 6. Games larger than 8 MiB (`research/bigimage.py`, `research/streamstub.py`)
Five dumps are 16 MiB (all five work). Their biggest resources stay on the card as files next to `game.bin` and are
read into a RAM slot at the top of the 8 MiB area just before the game uses them (BIOS `fopen`/`fread`).
1. **Cut**: the resources are removed from the image in whole 4 KiB blocks (so everything after
   keeps its alignment), and every word the converter relocated is moved to the new layout (its
   list of rewritten words is complete: header, directory, tables, fonts, bitmaps, native code).
   A word pointing into a removed resource is an error, except table entries (set by the loader)
   and data words the native scan only guessed at (they get their original value back).
   Nothing after the image's trailer is kept; the file ends at its last byte in use.
2. **Load**, two ways (a third for Story Explorers: 4. below):

| Kind | Games | Trigger | Slots |
|---|---|---|---|
| Story movies loaded with `getURL(lfh(handle), "_level1")` | Talking Words Factory (8 stories, files `m1.bin`-`m8.bin`), Letter Factory (7) | `lfh` renamed to the same-length native **`llZ`** in the remaining movies' ActionScript; llZ converts its argument with the BIOS's own to-number routine (0x4009_5FA4, as lfh), and if it is a story's handle reads that story's file and points the movie table at it, then jumps to the BIOS's lfh (0x400A_0EA8; for a string it returns the same string, which getURL takes as a handle) | 2, used in turn (the story playing is never overwritten by the next) |
| Videos played by a native PEG app | Schoolhouse Rock America Rock, Grammar Rock (files `v0.bin`-`v5.bin`: a video and its songs) | the game's own natives are wrapped (their pointers in the 0x1009 list): `LF_WriteGlobalDataBytes(1, n, 1)` remembers video number n, `LF_PlayPegApplication` first reads file n. Video n's command list (table 10 #n) names its video (command 0x55, handle 6 bytes on) and songs (0x59, handle next) | 1 (Flash is stopped while a video plays) |

   Natives read their arguments the way the games' own do: `obj = ([[gp+4]+0x64]+0x40)()`,
   `obj.vtable[+8](ctx, index)` -> double, then BIOS 0x400E_F75C double -> int.
   Talking Words Factory had no 0x1009 list at all: the converter adds one (a copy of the LEAP
   directory with the entry inserted in tag order, 0x140 pointed at it).
3. Results (VERIFIED-EMU): America Rock plays its music video (lyrics on screen) from `v*.bin`,
   Grammar Rock plays "A noun's a special kind of word", Talking Words Factory and Letter Factory
   play stories. Not verified: the songs' sound, every story/video, real-hardware loading time
   (2-3 MB per load).
4. **Story Explorers** (16 MiB; VERIFIED-EMU 2026-10-25): 96 movies (7.4 MiB), 2331 sound clips
   (5 MiB), a 1.9 MB table-1 resource. Neither way above fits it: its movies are loaded with
   `GetURL2(handle, "_level" + N)` from handles that `lfh()` put into arrays at start-up (so an lfh
   hook loads the wrong things at the wrong time), several levels at once (framework, title,
   activities, assets, score card). Third way, **pool mode** (`plan_pool`, `install_pool`):
   * every movie of 32 KB or more (70, 7 MiB) goes to **`m.bin`**; its table word points at a 17-byte
     empty movie until loaded (a load the hook misses shows nothing instead of crashing);
   * `research/avm1patch.py` inserts code at all 25 `GetURL2`s whose target is `"_level" + N` (or a
     constant `"_levelN"`, also from the constant pool): `llL(N)` while N is on top of the stack,
     then `llU(url)` with the stack as it was (StackSwap/PushDuplicate). It fixes If/Jump offsets,
     DefineFunction/DefineFunction2/With sizes, DoAction/DoInitAction/DefineSprite lengths and the
     SWF length. Patched movies kept in the image move to free space (their table word is moved);
   * natives `llL`/`llU` (`streamstub.build_pool`): each level holds its current and its previous
     movie (the one being replaced may still run this frame); the movie before that is freed, its
     table word back to the empty movie. A new movie goes to the first pool address clear of every
     loaded movie (16-byte aligned), read with BIOS `fopen`/`fseek`/`fread`/`fclose`. Levels 0-63;
     a load that does not fit is counted (word after `pending`), not done. Pool here: 3.1 MiB (0x31_E000);
   * the **LF_PlayLFC clips** (table 0x1006/4, handles 0x8000+n) go to **`s.bin`**: `LF_PlayLFC` is
     renamed to the same-length native **`LL_PlayLFC`** in every movie (also in `m.bin`); it reads the
     clip into a 256 KiB ring (`fseek` + `fread`), points table 4's word at it and jumps to the
     BIOS's LF_PlayLFC (0x400A_2F54). Clips have no length field: a clip ends where the next clip
     starts, so the last clip of each run of clips stays in the image (`plan_lfc`). The movies-only
     planner tries this too, after movies alone.
   * BIOS `fseek` = thunk 0x400F_098C (slot 0x38 of the C library table, after fwrite 0x34; the only
     three-argument call there; VERIFIED-EMU by the clips and movies it reads).
   Result: title, sign-in books, name entry, intro, Adventure Book, the Ogre's Cottage story with
   narration, the first activity; HINT + A + B back to the menu; the name is still there after a
   relaunch (`save.dat`, RAM chip). The activity's scene is gray in the emulator, the same with the
   original cartridge (an emulator matter); later stories unlock through it, so they are not tested.

### Main movie
The image's main movie is the one named by resource 0x2000 **id 1** (`{0x0001_0100, 0, 0, handle}`).
Talking Words Factory has 0x2000/3 and /5 too; using the last one broke it.

## 7. Testing
* `D:\leaploader-tmp\native\run_all.py` / `run_all2.py`: boot every dump from SD (LeapLoader menu),
  screenshots at 40/48/56/64 s, stray cartridge-window accesses, EEPROM traffic.
* A dump can be booted as a cartridge for comparison: `sdboot-emu --cart DUMP --script
  cartboot/setup.txt` (first-time setup, sign-in, power cycle). The BIOS refuses cartridges with a bad
  checksum, so that only works for good dumps.
