# LeapLoader handoff notes (updated 2026-10-25, late session)

## START HERE (2026-10-26, latest: 0.2.2 hotfix: USB drive letter; 0.2.1 B5 fix)
* **B5 (Leapster Connected) fixed** (how-it-works 8): 0.2.0's stubs called BIOS 0.6 addresses;
  `research/bioscall.py` makes them portable (service table + per-BIOS Flash natives). VERIFIED-EMU
  on B5 from power-on, 9 representative games (`native\g16`, `run_b5.py`: RAM chip, files on the
  card, native chip): game, HINT + A + B, relaunch, 5 restarts, same saves as 0.6. A 0.2.0-built
  card reproduces the bug (restarts back to Sign In). The "repeated 512-byte block" hang was a test
  artifact (B5 save state + swapped card): test B5 only from power-on.
* Menu music from any Leapster 2 BIOS (0.6, B5, m9). Version bumped to 0.2.1 (app + menu label,
  which still said v0.1.0 in 0.2.0). Docs and README caution updated for 0.2.1.
* Ribbit (uncommitted, logged in its changes-from-leaploader.md): optional SDHC card `RIBBIT_SDHC=1`.
* **0.2.2 USB fix (tester report 2026-10-26):** on a real console Windows gives the SD
  disk a letter (F:) before C2, so the app showed "Build card onto" at once and mkcard said "the output
  folder F:\ is not there". `usb.rs` disks(): a letter counts only once GetDiskFreeSpaceExW reads it
  (critical-error dialog off); otherwise the log says "has a letter but can't be read yet" and the
  app offers "Open the SD card". Tested: readable disks unchanged, empty CD drive -> error 21, no
  dialog. Not tested on a console. SNES emulator idea parked (user); ARC GCC 2026.03 unpacked in
  D:\leaploader-tmprc-gcc, untested.
* Still to do: game names on real consoles (MAME names, part numbers), menu battery icon and power
  button.

## Earlier (2026-10-26, earlier: 0.2.0)
* **0.2.0** (user asked: "hotfix but add the other stuff too"): start-up crash fix (Ribbit's GPU
  fallback + guard file, leaploader.log, panic/native-crash logging), in-app updates (updates.rs,
  install.rs: the package folder is swapped item by item; macOS swaps LeapLoader.app), packages
  bring their own Python 3.12 + numpy + scipy (python-build-standalone 20261003; user: "people
  shouldn't have to install anything besides leaploader"), the menu music is required (Build card
  asks for the BIOS 0.6), Linux (WSL build) and macOS (manual workflow .github/workflows/macos.yml,
  arm64 + Intel; scripts and Python in LeapLoader.app/Contents/Resources). Repo PUBLIC since
  2026-10-26 (history rewritten first to drop C:\Users paths).
* **"Incompatible" for tested games** (users' report): LeapLoader knows dumps by CRC-32 and players
  had other versions. The user's two collection zips in D:\Downloads held 190 untested dumps
  (`native\carts3`); all were tested (`native\g9`): 126 added to gamenames.py / gamenames.rs
  (other versions, languages, prototypes; 201 names). Failures were prototypes, ROX protos (restart
  loop), Leapster POP LP7 (crash), Demo Herbst 2004 (skipped).
* **Full images** (how-it-works 4b'): sound clips to s.bin make room for saves; 22 games re-tested
  (`native\g12`). Full regression of all 267 dumps: `native\g13` (`run_all13.py`).

## Earlier: release prep (2026-10-26)
* **Release prep (2026-10-26), nothing committed yet:** `scripts/package-release.py` builds
  `LeapLoader-<ver>-windows-x64.zip` (LeapLoader.exe, nativescan.exe, arc-gnu\ binutils from Ribbit's
  tools, the research scripts mkcard imports, README.txt, LICENSE.txt, notices + binutils source note,
  TESTING-USB.txt; refuses unlisted files and home paths/emails; UTC zip times; Rust paths remapped).
  The app finds nativescan and `arc-gnu\` beside itself (sets NATIVESCAN / ARC_GNU), has a
  **Leapster 2 BIOS** setting (default: Ribbit's `bios_picked`), passes `mkcard --bios`; mkcard
  builds the menu **without music** (a `note` line) when the BIOS isn't 0.6 (CRC 0xFA94D9A7) or
  numpy/scipy are missing. Welcome sound ships pre-encoded (`assets/welcome.alaw`, no ffmpeg needed).
  Dev build: copy nativescan.exe beside `D:/leaploader-tmp/target-app/release/leaploader.exe` (the
  hard-coded dev path was removed: it was a build-machine path in the binary).
  Red "Use at your own risk / not tested on real hardware" box in the Card panel and About (user asked).
  User docs: README rewritten, `docs/manual/` (8 pages), `docs/compatibility.md`.
* **HINT + A + B: 77 of 77 go back** (VERIFIED-EMU, `D:\leaploader-tmp
ative\g8`, script
  `run_all8.py`): RAM-chip stub got the ButtonMPI 4 s fallback; both stubs pre-write PlayGame.lnk and
  restart with LC_Boot("ExtStorage") from the button task (how-it-works 3). Converter relocates
  0x100D handle lists (how-it-works 5): Cosmic Math, Letterpillar, Number Raiders, Word Chasers had
  never run past their first sound.

## Earlier (2026-10-25, late: saves in the stub, Cars, menu paging, console drums, USB, repo)
State in one place; details in the sections below and in how-it-works.md, games.md, usb-research.md.
* **Git**: private repo https://github.com/MotifMixes/LeapLoader (main). Commits by MotifMixes only
  (noreply email, +0000 dates, no Claude/Anthropic attribution: user's rule). README has Ribbit's AI
  disclaimer. Ignored: dumps and derived files (.gitignore), `missing-leapster-games.txt` (personal).
  `assets/welcome.mp3` is ElevenLabs-made (user: their plan allows shipping it). The menu song ships
  as notes only: `app/assets/menumusic.mid` (user: name it "menu music"; the rendered audio contains
  BIOS samples and is made on each PC). History rewritten once (2026-10-25) to drop the old name.
* **Saves (all games now)**: every game gets the RAM chip (`eestub.py`); the stub itself reads
  `save.dat` at install and writes it (hex, same format as before) after 10 quiet frames or at once
  on HINT + A + B (`__llEE(1)`). Flash-only games without a 0x1009 list get a copy of the resource
  directory with one (header 0x140 repointed). Old AS shim: `LL_AS_SHIM=1`. VERIFIED-EMU: save loads
  (marker bytes) and writes back in Cars and 1st Grade; 1st Grade title 4 s sooner (100.0 vs 104.0 s).
* **Cars HINT + A + B fixed** (VERIFIED-EMU): the AS save writer joined a 2 KB chip into 4096
  characters (~10 s, script killed before BT_StartSDMenu). Native writing fixed it.
* 77-game regression: done 2026-10-26, see START HERE.
* **Menu** (research/menugen.py, v0.1.0): "My Games: N", "Page n/m" in the footer, page arrows /
  D-pad left-right move whole pages (multiples of 4) and wrap (last <-> first), title in the app's
  purple (0xA090F0), only rows in view are visible (77 visible rows made a page turn ~0.5 s and fast
  taps queued). All VERIFIED-EMU.
* **Music**: clip rendered with a steep 3.85 kHz filter + EQ for Ribbit's interpolator + noise-shaped
  A-law (musicrender.py). **Drums, flute (073), bass (038) are played by the console's sequencer**
  (`--console drums,73,38`; key-0 drum hits and notes with no free voice stay in the clip). The guitar
  was tried there and taken off (user): on the sequencer it took voices from the bass from the
  prechorus on (29 bass notes fell back to the clip, which the user heard as the bass dropping out).
  The guitar is back to 031 "Gtr Harmonics" in the clip (user preferred it to Nylon 024), its notes
  played once without the sample loop, each for its whole sample whatever the note length
  (`--short 31`; the loop sounded like a stuck repeat; user: "as long as the sample"). The bass plays its soft notes (~0:40-0:50) at velocity 96 (`--floor 38:96`; user:
  "too quiet" there; VERIFIED-EMU that the console bass never stopped); clip
  loop on the 4 ms grid; sequence 6 ms early; volume curve measured (SEQ_VOLUME_CURVE). Sync
  VERIFIED-EMU (drums vs clip 5-7 ms, < 2 ms change over 2.5 loops).
* **Card**: `D:\leaploader-tmp\ribbitcard3\sdcard-new.img` = new menu + music (drums/flute/bass on the console),
  but the games are still the OLD conversions (built before the save changes). Not installed yet
  (Ribbit open). Rebuild games: mkcard into `tree` (both carts folders, `--console drums,73,38`),
  then `sdboot-emu --tree tree --script exp.txt`. Menu-only rebuild script: scratchpad `remenu.py`.
* **USB VERIFIED-EMU end to end** (Ribbit's emulated L2 USB + usbip-win2): find, C2 mount (UAC),
  J: appears, mkcard writes, eject (flush, dismount, C6); the written files are byte-exact in the
  saved card and it boots. Test copy: `D:\leaploader-tmp\usbtest`. Not tried: the GUI buttons.
* **Desktop app** `app\` (Rust, egui like Ribbit; written by a subagent): games list with tags and
  compatibility, Import Ribbit's Rom Folder, card build through mkcard.py, frog + USB-stick icon,
  build notification, GPL-3.0. Build: `cargo build --release --target-dir D:/leaploader-tmp/target-app`.
  Test settings: `D:\leaploader-tmp\app-test\data` (84 games). Incompatible games (done): they start
  switched off and are left out of the totals; the user can switch one on anyway, it then shows an
  amber "May be skipped" badge (`app\src\ui.rs`), and that choice is saved in settings.toml as the
  `try_anyway` list of game paths (`app\src\settings.rs`, `app\src\app.rs`). The list is kept A-Z by
  name (`App::sort_dumps`; user asked), tests pass; the running copy may be an older build.
* **USB** (user wants it working; no Leapster 2 here, outside testers will try it):
  * App side written (`app\src\usb.rs`, `app\TESTING-USB.md`): find "LeapFrog"/"2-SD" disks (read
    only; VERIFIED on this PC: other disks ignored), C2 mount via an elevated `--usb-helper`, wait for
    the volume, build onto it, flush, C6 eject; USB log for testers. Steps 2-3 UNTESTED (fake-device
    unit tests only). LFTools' method ported with credit (allowed: LeapLoader is GPL-3.0).
  * Ribbit side: the Ribbit Claude session (`ribbit-2c`; Ribbit's repo, don't edit it from here)
    emulates the Leapster 2's USB controller (Freescale USB-FS OTG) + USB/IP. When it works, run the
    app against it (usbip-win2: `usbip attach -r 127.0.0.1 -b 1-1`).
  * Research: `docs\usb-research.md` (controller registers, descriptors, BOT/SCSI dispatch, vendor
    C1-C6, GET MAX LUN = 1, C2 needed before READ). Harness: `sdboot-emu --usb-attached` / script
    `usb-attach`. Open: which BIOS code fills each LUN record (+0x64/+0x68/+0x08).
* **Ribbit**: commit "Voices: a paused voice reads as free in the status register" on main (not
  pushed); ribbit-gui rebuilt.
* **License**: LeapLoader GPL-3.0-or-later (`LICENSE`); Ribbit stays not GPL. LeapLoader has no git
  repo yet; nothing committed.

## Latest (2026-10-25, later): menu polish, HINT + A + B fixes, start-up time, Rust app started
* Menu (user asked): louder music (raw volume 127), long titles scroll at once and 2x faster, BIOS
  D-pad sounds on moves/arrows (lfh 29 / 27), tool keys and OK light up, CLR key on the keyboard,
  thin footer with only the version. VERIFIED-EMU (`D:\leaploader-tmp030	5*.txt`).
* HINT + A + B (user: "isn't showing up"): it never showed in some games. Fixed (VERIFIED-EMU) in
  Kindergarten, I Spy Challenger, Creature Create: prompt appended to the game's own movie table,
  native games poll the buttons through `__llEE` (how-it-works 3). **Cars still has none** (open).
* Start-up time (user: games load slower than normal): in 1st Grade the title comes ~4-5 s later
  with saves than without (VERIFIED-EMU, `D:\leaploader-tmp030is2.py`): the ActionScript save
  shim (the game reads its save memory through AS functions, byte by byte). Save loaders now avoid
  string methods (opcodes + hex table); that did not change the fresh-card case. Idea: give
  Flash-only games the RAM chip (eestub) too, so the BIOS natives stay native (needs a 0x1009
  directory entry where there is none). Not done.
* Full card rebuilt: `D:\leaploader-tmp
ibbitcard3\sdcard-new.img` (77 games). Not installed yet:
  Ribbit was running.
* Rust desktop app started (user asked; "look similar to Ribbit", Leapster 2 logo + USB styling) by
  a background agent in `app\` (egui like Ribbit; Build calls mkcard.py for now).

## Latest (2026-10-25, menu v0.3.0 session): read docs/how-it-works.md section 2
* **Menu v0.3.0** (user asked), all VERIFIED-EMU: real game names (`research/gamenames.py`, by dump
  CRC-32; folders keep their old names so saves stay); tool column with a search magnifier and page
  up/down arrows (D-pad left/right also page); Home now boots `Apps\LeapLoader\home.txt` (silent; the
  missing-file trick beeped 17 times); welcome sound +10 dB (`LF_SetRawVolume(127)` around its start);
  HINT+A+B prompt: "Let go to cancel" removed (it overlapped the bar).
* **Menu music rendered** (user: "my music sounds awful"; asked to render each instrument with all its
  notes at the highest quality and play one file): `research/musicrender.py` renders the MIDI with the
  BIOS instruments (stems at 48 kHz float, 13 tracks, 1401 notes; only track 031's stray chord at
  quarter 619 is left out), mixes to 8 kHz A-law and the menu plays it with LF_PlayAudioRaw: once from
  the start, then looping from **0:20.210** (user asked; `mkcard.py --music-loop 20.21`). Stems and
  previews: `D:\leaploader-tmp030\music` (contain BIOS samples: never commit). The user also said
  they would make a new song.
* **Ribbit fix** (not committed): a paused voice reads as free in the voice status register (the BIOS
  stops raw sounds with the pause command and then looked for a free voice in vain). Logged in Ribbit
  `docs/changes-from-leaploader.md`. `ribbit-gui.exe` still needs a rebuild (it was running: "Access
  is denied"); the harness `D:/leaploader-tmp/target-emu` is rebuilt.
* Full card: `D:\leaploader-tmp
ibbitcard3` (`tree`, `sdcard-new.img`, `script.txt`, `out\sheet.png`);
  not yet installed as Ribbit's card (ask). Tests: `D:\leaploader-tmp030` (`joins.py` checks the
  music joins against the ideal timeline; `t4.txt` music toggle, HINT+A+B, Home).

## Latest (2026-10-25, later session): read docs/how-it-works.md and docs/games.md
* **Ribbit fix** (user asked; "Leapster 2 suddenly slow"): rewind snapshots copied the ~680 MB SD card every
  0.5 s and queued without bound (29 GB). Now left out of rewind (save states keep it). Committed on Ribbit
  `main`, not pushed; Ribbit `docs/changes-from-leaploader.md`. Rebuilt `ribbit-gui.exe` runs at ~1.5 GB.
* **Welcome sound fixed** (user: "isn't as high quality as the narrator"): now 8 kHz A-law played with
  `LF_PlayAudioRaw` from the menu's own table 0x1006/5 (how-it-works 2), not a SWF sound: the player
  band-passes SWF sound to ~300-5500 Hz. VERIFIED-EMU (output = clip exactly; menu, search, game start
  OK). `ribbitcard2	ree` has the new SDMenu.bin and `sdcard-new.img` is re-exported (old menu:
  `SDMenu.bin.adpcm-welcome.bak`); **installed as Ribbit's card** (77 games, user asked; no backup, user said not needed). It is quieter over the music than the
  old SWF one (narrator level). Tests: `D:\leaploader-tmp\welcome2` (`run1.sh`, `runr.sh`).
* **Penguins replaced (2026-10-25, user's `penguins.zip`)**: new dump in Ribbit `roms\penguins.zip` (checksum OK; copy in
  `native\carts2`); old `.bin` (bit errors) moved to `D:\leaploader-tmp\penguins-old`. Runs from SD to name entry, saves.
  **On Ribbit's SD card** (rebuilt with 77 games, user asked; 76-game card backed up as
  `D:\leaploader-tmp\ribbitcard\sdcard-76games.backup-2026-10-25.img`, its tree as `tree76`). Menu music source:
  `app/assets/menumusic.mid`.
* **Menu v0.2.0** (asked; how-it-works 2), all VERIFIED-EMU with 77 titles: **Home** goes back to the
  console (restart via `BT_StartSDGame` of a missing file: logo, Sign In); **Pause** opens Options (Search,
  Resume, Music On/Off, Sort A-Z / Recent, Leapster Home, About); **search keyboard** drawn by us in the
  console's name-entry layout (the BIOS one cannot be borrowed; user chose the look-alike); settings in
  `SDMenu\LeapLoader.txt`; **welcome sound** `assets/welcome.mp3` (user's, "Welcome to LeapLoader. Select a
  game.", ships with LeapLoader), now A-law via LF_PlayAudioRaw (see above; was SWF ADPCM). Key finding: string methods are very
  slow on the player and a script over ~6 s freezes it (how-it-works 2). Full card with this menu:
  `D:\leaploader-tmp\ribbitcard2\tree` (not yet on Ribbit's card: ask first). Test trees/scripts:
  `D:\leaploader-tmp\welcome` (`t77` = all titles, one game; `m4.txt`..`m9.txt`), `homepause`.
* **77 of 77 Leapster dumps run from SD** (was 76) (VERIFIED-EMU; all 77 convert): the 39 old ones + 38 the user
  downloaded (moved from `D:\Downloads` into Ribbit's `roms`, extracted to `D:\leaploader-tmp\native\carts2`).
* **Story Explorers works** (asked "find a way to get story explorers to work"): pool mode, how-it-works 6.4
  (`research/avm1patch.py` patches its 25 GetURL2 loads; natives llL/llU load movies from `m.bin` into a
  3.1 MiB pool by level; LF_PlayLFC clips from `s.bin` via LL_PlayLFC). Tested to the first activity;
  test states and scripts in `D:\leaploader-tmp\se` (`after*.state`, `script*.txt`; `cart\` = the
  original cartridge run for comparison).
* **All five 16 MiB games work** (`research/bigimage.py`, `streamstub.py`):
  Schoolhouse Rock America Rock + Grammar Rock (videos via wrapped PEG natives), Talking Words
  Factory + Letter Factory (stories via the `llZ` native that replaces `lfh`).
* **Every running game has saves and HINT + A + B**: games without room get the all-native chip
  (`research/nativechip.py`: trampolines on the game's natives, malloc'd zeroed chip, `save.bin`,
  ButtonMPI poll hook for HINT + A + B without a prompt).
* **LeapFrog's own SD menu** works with all games (`mkcard.py --menu LSTR-...lfp`): 6 per page,
  pages with its arrows, HINT + A + B returns to it ("Back to the SD Menu"). Full card built at
  `D:\leaploader-tmp\vanilla\tree` (76 games, rebuilt with the final converter).
* Converter fixes: fonts by table (Bratz), self-pointing bitmaps (Scooby Arcade, Diego),
  resource handles left alone (Diego, Rock the World), main movie = 0x2000 id 1 (TWF), dump repair
  (Cars Supercharged `LBK` marker), checksum mismatch converted with a note (Ni Hao).
* `missing-leapster-games.txt`: the wiki's list vs the user's dumps (2 missing).
* **Ribbit's SD card rebuilt** (user approved): LeapLoader menu + music + 76 games (Penguins added later: 77),
  built in `D:\leaploader-tmp\ribbitcard` (tree, `script.txt`: sdboot-emu `card` + `export`), boot
  tested (menu, 2nd Grade name screen). Old card backed up there (`sdcard-fa94d9a7.backup-2026-10-25.img`).
  mkcard needs `NATIVESCAN=D:/leaploader-tmp/target-nativescan/release/nativescan.exe` and Windows paths.
* Ribbit v1.5.1's macOS package: built on GitHub Actions (user asked; upload off so the local Linux
  package stayed) and attached to the release by hand.
* Not done: real hardware; full
  save/load test. BIOS narrator voices exported (see below).

Read this first in a new session. Background detail: `docs/research-report.md` (Phase 1) and
`docs/sd-boot-proof.md` (Phase 2a; its "no saves", "one game" and "native code refused" limits are out of date).

## Ground rules from the user
- **License: LeapLoader is GPL-3.0-or-later** (user, 2026-10-25; `LICENSE` at the root, canonical
  gnu.org text). Ribbit is NOT GPL and stays as it is. LFTools (GPL-3.0) is used for protocol facts only.
- No commit, push, publish or release without explicit approval. (The folder is not a git repo yet.)
- When the GitHub repo exists, push by **Ribbit's rules**: no Claude/Anthropic attribution anywhere (no
  Co-Authored-By, no "Generated with Claude Code" in commits, PRs, tags, releases; this overrides the default
  attribution reminder); commit/tag times in UTC (+0000); GitHub noreply email only; no personal info or
  build-machine paths; no dumps or anything derived from them; Actions only for macOS (without asking only if the
  repo is public); edit sources with Edit/Python, never PowerShell Get/Set-Content. Claude memory `github-push-rules`.
- No ROM/BIOS dumps, or anything derived from them, in Git, releases or test fixtures. Keep them in `local/` (git-ignored).
- Never format, repartition or erase a drive automatically, never assume which drive is the SD card,
  and never overwrite unrelated files without asking (e.g. Ribbit's SD card image: back it up and ask first).
- Don't claim a feature works unless it was tested. Label findings VERIFIED-EMU, VERIFIED-HW or UNVERIFIED.
- Work in milestones and stop for approval after each one.
- Keep the live `--view` window off unless asked ("don't show me, get this working").
- Build on this PC, not GitHub Actions. Keep parallel emulator/build runs modest (the PC lags at full load;
  2026-10-25 ran 14 emulators at once, which is too many).
- The C: drive is nearly full (~1.6 GB free). Put large files on D: (`D:\leaploader-tmp\`).
- Ribbit (`..\Ribbit`) may be edited to fix emulation accuracy. Log every change in
  Ribbit `docs/changes-from-leaploader.md` (Ribbit has no CLAUDE.md; its rules live in Claude's Ribbit project
  memory). **No Ribbit changes made yet.**

## Done 2026-10-25: BIOS narrator voice export (user asked: "export all the internal talking voice samples", narrator only)
- **`local/bios-voices/`: 755 narrator clips** "<handle> - <words>.wav" (8 kHz) + `index.tsv` (handle, seconds,
  Whisper text). LeapFrog's audio: never commit. "If you see your name..." = **0x2159**, "...touch it with a pen" = 0x22C9.
- Source: `research/biosvoices.py` (SD-menu movie plays `LF_PlayLFC(lfh(0x2000+k))`, table 0x1006/4, 836 clips;
  recordings `D:/leaploader-tmp/voices/lfc_0..2`; A-law effect tables in `raw_a`/`raw_b`, not exported).
- Removed to `D:/leaploader-tmp/voices/not-narrator` (81): 0x2000-0x2033 character shouts (Dragon Land / Creativity
  Castle), 0x232F-0x2343 the villain Sagras, 0x2327-0x232E identical 0.07 s empty clips. Chosen by transcript +
  pitch (`D:/leaploader-tmp/voices/pitch.tsv`; narrator ~150-230 Hz, characters 280-500 Hz) because Resemblyzer
  similarity (`similarity.tsv`) tracks clip length more than voice.
- Kept but not checked by ear: short phonics sounds 0x2213-0x2252 (Whisper text there is often wrong, e.g. "you",
  "Thank you" for quiet consonants; some names are misheard words) and the grunts 0x2234-0x2240.

## Notes: 16 MiB games plan (done since, see Latest)
- 16 MiB games (asked "get those 15mb games working"): Schoolhouse Rock = 6 VP6 AVIs (0x1006/14, 8.7 MiB) + song
  audio (0x1006/15, 2.4 MiB); Talking Words Factory = 9 story SWFs (0x1006/7 #0-8, 14.7 MiB, stream sound +
  animation). Plan: keep those as SD files, load each into a RAM slot just before use (native loader via BIOS
  FAT read, hooked before the AS play/getURL(lfh) calls; TWF two alternating slots). No code yet.

## Where things are
| Path | What |
|---|---|
| `research/sdboot-emu/` | Rust emulation harness on Ribbit's crates. Build: `cargo build --release --target-dir D:/leaploader-tmp/target-emu` (the `target-dev` copy is older). Flags: `--bios --cart --tree DIR --card-format factory\|mbr-fat16\|mbr-fat32\|bare-fat16 --script FILE --out DIR --shot-every MS --view --log PC --trace PC --dump`. Script commands: `run tap btn hold release shot say wait play save load card ls cat power b008 trace export`, plus **`audio`** (start recording the 8 kHz voice output) / **`audio FILE.wav`** (write it and list the sounds with times; while PCM channel 1 ran, also the real 32 kHz DAC stream to `FILE-32k.wav`: the 8 kHz file then holds 4-sample averages of it), **`voices`** (print the voice engine's start/end/volume), and **`mem ADDR [WORDS]`** (dump RAM; `gp`, `+N` and `@` = load word, e.g. `mem gp+4@+0x88@ 6`). Stray reads report "pc 00000000" for every bus master: the pc is not recorded, also with `RIBBIT_JIT=0`. |
| `research/sdpack.py` | Converts a cart dump (0x8000_0000) to an SD image (0x3C80_0000). Header/LEAP/sub-entry words; 0x1006 tables incl. null slots, a **second address array** right after the first (every game's sound table 5; Batman's 9), **instrument banks** (table 2 with handles 0x2000: 20-byte zones {start, end, loop lo16, loop lo16, f32, lo key, hi key, level}, start/end relocated, walk ends at hi key 0x7F), **fonts** (first word 0x0101_0100: every word pointing into the same font), the long **0x1005 save descriptor** form (+0x18 == 0: functions/data at +0x1C..+0x28); native code via nativescan's list (`NATIVESCAN=` env var to the exe). Save size = descriptor **+0x14** (0x100/0x200/0x800; +0x18 was wrong). Saves: Flash-only games get the AS shim (renamed natives); native games get the RAM save chip (eestub). Save code goes after the image end, else into the biggest 0xFF padding run no known pointer reaches (4 KiB margins, start or end of the run). Picks the movie table holding the main handle (Cars has two). Refuses images over 8 MiB. |
| `research/nativescan/` | Rust (Ribbit's ARC decoder). Finds every absolute address in native code and data: named natives from 0x1000 pairs and 0x1009 tables {0x100, 0, count<<16, pairs} (pairs may lie before the blob), speculative recursive descent (a path hitting illegal code or running out of step drops its entry), weak entries (data pointers, unreached stretches) only at plausible function starts (push_s, st.aw [sp,-4], sub sp, mov blink, or after an unconditional return/jump), switch tables `ld.as rX,[table,rY]` (bound: `brhs N` = N, `cmp N` = N+1), INI blocks (0x1000 header +12: "INI" records {RAM addr, len, data}, negative len = zero fill; constructor pointers), 0x1009 pair lists wherever they are, data sections far from the code (clusters of 8+ long-immediate targets above base+0x2000, e.g. NASCAR's C++ data at 0x803E_4xxx), native data around the code only inside native blobs (0x1005 descriptors end at their size). Left alone: masks (and/or/xor... 0x8000_0000), words pointing into 0xFF padding (16-bit pairs like 0x806B806A). Opaque = 512+ bytes of entropy > 5.6. Prints `VERDICT ok` (all named functions decode) or doubt. `--relocs FILE`, `--verbose`, `NS_TRACE=<entry>`, `NS_NEAR=<addr>`. Build: `cargo build --release --target-dir D:/leaploader-tmp/target-nativescan`. |
| `research/eestub.py` | ARC stub (assembled with Ribbit `tools/arc-gnu`, `-mcpu=arc600`) = cartridge save chip in RAM for native games. Added as an extra 0x1009 resource with native `__llEE()`: first call copies the BIOS EEPROM function table and points `[[gp+4]+0x88]` (RAM 0x3C00_01D4, was 0x4013_3420) at it; read (+0xC), write (+8), checksummed read (+4) and write (+0: data then ~sum) serve **devices 1-3** from a buffer (device 0 = the console's own memory, flash-emulated, passed through); returns the changed range as lo*65536+hi+1 (0 = none), as a double via the player interface `([[gp+4]+0x64]+0x40)()` -> object, vtable +0x1C(ctx, lo, hi). |
| `research/saveshim.py` | AS save shim for Flash-only games (LF_*CartridgeMemory natives renamed to same-length `_level0:__ll..` paths; now also floats: 4-byte IEEE single, as BIOS 0x400A_060C/07C0). `build_ee_loader`/`build_ee_flusher`: the AS side of the RAM chip: loads `save.dat` in 64-char lines (erased lines skipped) through `LF_WriteCartridgeMemoryBytes`, keeps a hex copy, refreshes the changed range each frame, writes the file after 10 quiet frames (or at once when leaving with HINT+A+B). |
| `research/ingame.py` | Hold **HINT+A+B** 2.5 s in a game to go back to the menu (overlay movie handle 0x8000FF00, _level999). |
| `research/menugen.py` | LeapLoader menu v0.2.0 (Home, Pause options, search keyboard, settings file, welcome sound: how-it-works 2). Older notes: v0.1.0. Choosing a game: the glow blinks, the BIOS's name-select sound plays (`LF_PlayAudioRaw(lfh(28))` = LPSR_BROM_MenuSelect_6, as the sign-in screen's chooseName; 355 ms), then BT_StartSDGame after 10 frames (VERIFIED-EMU). Optional background music (`music=` sequence): `LF_PlayBgMIDI(lfh(0x8000), true)`. |
| `research/sndgen.py` | Audio file -> 8 kHz A-law for LF_PlayAudioRaw (`load_alaw`, the welcome sound), or -> SWF ADPCM DefineSound/StartSound (11025 Hz; the player band-passes it to ~300-5500 Hz). `python sndgen.py IN OUT.wav` = ADPCM round trip to listen to. |
| `assets/welcome.mp3` | The user's welcome sound, played when LeapLoader's menu starts (ships with LeapLoader). |
| `research/seqgen.py` | MIDI -> LeapFrog sequence (see "Music"). `arrange(path)` fits any MIDI to 5 voices. |
| `research/swfgen.py` | SWF/AVM1 builder and `pack_rib` (menu images; `sequences=` adds table 0x1006/6, `raw_sounds=` table 0x1006/5 (A-law, (start, end) pointer pairs), both with handles from 0x8000; directory sub-entries must be in **ascending resource id** order or the BIOS does not find them). |
| `research/mkcard.py` | Builds the card tree. `--menu leaploader\|FILE.lfp\|SDMenu.bin`, **`--music SONG.mid`**. Games that cannot save are kept with "NO SAVES: reason". |
| `research/icongen.py`, `pixelfont.py`, `biosbank2sf2.py`, `tools/` | Icons; font; BIOS instrument SoundFont (`local/Leapster2-BIOS-0.6.sf2`); `tools/avm1.py` (AVM1 disassembler: `list`, `dump OFFSET`), `sparsefat.py`, `tags.py`/`tags2.py` (resource listing; tags2 reads the base from the header), `leapdir.py`, `bstrings.py`. |
| `LSTR-0x00130001-000000.lfp`, `local/lfp/`, `local/sdimg/` | LeapFrog's SD menus and the factory card (never commit). |
| `local/*preview.wav` (menu music) | Emulator recording of the menu music (contains BIOS samples: never commit). |
| Ribbit `roms\bios\leapster2\152-12206_0.6.bin` | BIOS 0.6 (CRC fa94d9a7). All work targets this BIOS. Ribbit `roms\*.zip`: the user's 37 dumps (extracted copies: `D:\leaploader-tmp\native\carts\`). |
| `%APPDATA%\Ribbit\saves\sdcard-fa94d9a7.img` | Ribbit SD card (RBSPARSE): factory format, LeapLoader menu + music, 76 games (2026-10-25; backup of the old one in `D:\leaploader-tmp\ribbitcard`). |
| `D:\leaploader-tmp\` | Work files: `native\run_all.py` (boots every dump from SD in the emulator, 14 at a time: lower that), results `native\run5.txt`, `native\g\<game>\` (tree, emu.txt, screenshots), `native\sheet5.png`; `lfpmenu\menu.state` (home screen right after tapping the SD icon: `load` it, then `card`); `music\` (menu music tests); `native\ee_ispy\` (save chip tests); `ext\LFTools` (GPL tool, reference only); `ext\gist\leapfrog.md` (sequence format). |

## Status (all VERIFIED-EMU, BIOS 0.6, unless marked)
- **Base flow works:** SD icon -> our menu -> game -> saves -> HINT+A+B back (factory/MBR FAT16/32/bare FAT16).
- **Games: 35 of 37 dumps convert and boot from SD** (run 5, `D:\leaploader-tmp\native\run5.txt`; first 64 s
  each: title/name screens/menus reached). The 2 others are 16 MiB (Schoolhouse Rock, Talking Words Factory;
  ~15 MB of data each vs the 8 MiB SD load area): not feasible without a streaming loader.
  `disprin`/`prinfrog` in Ribbit's roms are LeapPad dumps, not Leapster.
- **Clean** (no stray cartridge-window access, no failed save-chip command): 1st Grade, Animal Genius, Cosmic Math,
  Creature Create, Fairies, Cars 2, Cars, Dora x3, I-Spy, Kindergarten, Learning with Leap, Letterpillar, NASCAR,
  Number Raiders, Outwit, Scooby-Doo, SpongeBob x2, Star Wars Jedi Reading, Batman, tspbeeswax.
- **Open problems:**
  1. **Star Wars Jedi Reading shows a black screen with the RAM save chip** (fine with saves off and with the
     old AS shim). Stub installs correctly; the 10-frame write debounce did not fix it. Bisect next (stub vs AS
     loader vs 2 KB chip vs the extra 0x1009 resource).
  2. **No room for the save chip** (8 MiB images packed full): Pet Pals x2 (42 KB free, needs 162 KB: the main
     movie copy), Princess Enchanted (9 KB), Princess Worlds (2.7 KB). Their native code still reads the empty
     cartridge chip -> garbled player names, no saves. Plan for Pet Pals: a tiny boot movie as the main movie
     that loads a service movie (chip install + save load + flush + HINT watcher) into _level998, which then
     loads the real main movie into _level0 (no main-movie copy). Princess games: no space at all.
  3. Small stray reads left (1-56 each): Ratatouille x2 (font 0x807823BC), Madagascar, Foster's, Letters on the
     Loose, Numbers on the Run, Sonic X, Spider-Man, Thomas, Star Wars Jedi Math (one read at 0x83C00044).
     Find what holds each address (resource owner script in this session's history: search the image for the
     word, then which resource contains it).
  4. Saves for native games: mechanism VERIFIED-EMU (save.dat -> chip: a marker byte arrived; chip -> card:
     I-Spy's formatted 568 bytes written), but no game-level save/reload proven (scripted taps could not
     confirm a name in I-Spy). Loading a save costs a few seconds at boot (I-Spy).
- **Nothing has been tested on real hardware yet.**

## Key findings this session
- Native code: LeapFrog's SD downloads are separate builds linked at 0x3C80_0000 (no runtime relocation to copy).
- EEPROM: BIOS device table at [0x3C7F_ADF0] (12 bytes/device, size at +0x10+dev*12); device 0 is flagged
  0xFF = emulated in flash (the console's own memory); devices 1-3 have chip id 0 -> I2C chip 0x20 = the
  cartridge's (routine 0x400B_7840; NeedToInterceptEEpromAccess 0x400B_702C). From SD there is no chip, so every
  native/LF_ cartridge-memory access fails (real hardware too) -> leftover RAM shown as names.
- Save descriptor 0x1005/3: {0x100, 1, 4, 0x2000, 0x64, size}, long form adds 0, fn, data, fn, fn.
- Sound hardware: 5 pitched voices for music (8-note chord test: only the last 5 tracks sound).

## Music (VERIFIED-EMU)
- Format (BLiNXthetimesweeperGOD gist "LeapFrog Sequencer (Leap-Font)", confirmed against BIOS table 0x1006/6):
  bytes `02 00`, u16 track count, per track u16 LE offset + u16 BE id; track = one voice: `00-7F d` note
  (0 = rest), `88 v` volume, `89 p` program (BIOS instrument 0-127), `8E n`/`8F 00` loop, `FF 00` end;
  duration 1 byte < 0x80, else (0x80|d>>8, d&0xFF). **1 tick = 4 ms.** Pitches verified (C4/E4/G4).
- Play: `LF_PlayBgMIDI(lfh(handle), wait[, volume])`; `lfh` only converts the number; table chosen by the API.
- The user's song `app/assets/menumusic.mid` (13 tracks named by BIOS program number, 95 BPM)
  is in the menu: 69.5 s loop, 1401 notes, 607 dropped and 195 cut to fit 5 voices (melody/bass/drums/velocity
  priority; drums auto = track span > 5 octaves -> 124). Track 031's stray chord at quarter 619 is left out.
  Waiting on the user: how the preview sounds (which parts to keep), and whether to rebuild Ribbit's SD card.

## Desktop app requirement: the console's storage over USB (SCSI), from the user 2026-10-25
"make sure internal storage units can be accessed in the desktop app as well with SCSI commands".
- BIOS 0.6 is a USB mass-storage device with **two LUNs** (VERIFIED-FW, INQUIRY data at 0x4014_EC58 and
  0x4014_EC7C): `LeapFrog` / `Leapster 2-RAM 1.00` and `LeapFrog` / `Leapster 2-SD   1.00`, removable.
  The RAM LUN holds copies of the internal flash (Cffs) archives (`ConnectCopyCffsArchivesToRamDisk`).
- Vendor CDBs (10 bytes, from GPL-3.0 github.com/lfhacks/LFTools via `sg_raw`): **`C2` mount, `C1` lock,
  `C6` eject**. UNVERIFIED: BIOS handler not found (probably a jump table near 0x400B_A000-0x400B_F000).
- Plan (Rust): find the device by INQUIRY, send CDBs directly (Windows `IOCTL_SCSI_PASS_THROUGH_DIRECT`,
  Linux `SG_IO`); after `C2` the SD LUN mounts as FAT. Only touch identified Leapster 2 devices, confirm first.
  Use LFTools' protocol facts only, not its code.

## Using LeapLoader in Ribbit
Run `..\Ribbit\target\release\ribbit-gui.exe`: Leapster 2, BIOS 0.6, no cartridge, a named
player, arcade icon top right. Keys: arrows = D-pad, Z = A, X = B, H = Hint, Enter = Pause, Backspace = Home,
mouse = stylus (click the screen first). **Open:** "i can't use the controls in ribbit" (which screen/keys?).

## Next steps
1. User feedback on the music and on the rebuilt Ribbit card.
2. Star Wars Jedi Reading black screen with the RAM chip (open problem 1).
3. Boot-movie approach for Pet Pals (open problem 2); stray reads (3); a game-level save/reload test (4).
4. Then: the Rust desktop app (incl. SCSI), real-hardware tests, update `docs/sd-boot-proof.md`.
