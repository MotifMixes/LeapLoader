# Homebrew for LeapLoader

LeapLoader puts homebrew apps (native programs for the Leapster 2) on the SD card next to the games.
The menu on the console shows them as **blue buttons with a white check** (games are green), and the
desktop app lists them in blue. An app goes
back to the LeapLoader menu, and it saves, like every game does: **HINT + A + B held 2.5 s**.

Status: VERIFIED-EMU (Ribbit emulator, BIOS 0.6, 2026-10-29) with the SDK example and the NES,
SNES and Game Boy emulator ports (`image=` packages, kept outside this repo: SNES uses snes9x2002,
which is non-commercial only). Not yet tested on a real console. Package format version 1.

## The emulators LeapLoader comes with

From 0.2.4 the desktop app brings two homebrew packages and puts them on its list the first time it
starts (taken off, they stay off): **NES** (QuickNES) and **Game Boy** (gnuboy, for `.gb` and `.gbc`).
They are built from [LeapLoader-Emulators](https://github.com/MotifMixes/LeapLoader-Emulators) (GPL 2;
`app/assets/emulators`, written to the app's data folder at start, `app/src/emulators.rs`), as `code=`
packages, so the card build adds the approval fields of a game on the card. Their games go in the card's
`NES`, `GB` and `GBC` folders. SNES and GBA ports exist but are not released.

## A package

A folder with `app.txt`:

```
app.txt     key=value lines (# comments):
              name=Hello Homebrew   the title in the menus
              id=HelloLL            the folder on the card: 1-16 of A-Z a-z 0-9 _ -
              code=code.bin         an SDK build (below), or
              image=game.bin        a ready Leapster 2 SD image (starts "LEAP", at most 8 MiB)
              author=, version=     shown in the desktop app (version)
code.bin    (or game.bin)
files/      optional: copied into b:\Leapster\Apps\<id>\ (data files; any size)
card/       optional: copied to the card's top level; files already there are kept
            (e.g. an empty folder for the user's own files)
```

Add it like a game: in the desktop app with **Add a folder…** (the package, or a folder holding
packages) or by dropping it on the window; with `research/mkcard.py OUT DUMPS... PACKAGE`.
A `code=` package is wrapped into `game.bin` when the card is built, with the approval fields of a
cartridge game on the same card, so a card with an SDK app needs at least one game.

## The SDK (`sdk/`, zlib licence)

```
sdk/leaploader.h     the API
sdk/leaploader.c     its code (BIOS calls through the service tables: BIOS 0.6 and B5)
sdk/entry.S          the start of code.bin: the native __llapp() the card's movie calls
sdk/link.ld          code at 0x3C81_0000, heap from the end of .bss to 0x3CFF_0000
sdk/example/         hello.c + build.sh: builds example/package/ (app.txt + code.bin)
```

Build with ARC GCC (GNU toolchain for ARC, `-mcpu=arc600`); `ARC=<prefix> sh sdk/example/build.sh`.
Rules: `-mno-sdata` and no newlib (the BIOS owns `gp`; `leaploader.c` has memset, memcpy, strlen),
link `-nostdlib ... -lgcc`, `objcopy -O binary -j .text -j .rodata -j .data`.

Write `int main(void)`; returning from it goes back to the menu. The API:

| Call | Does |
|---|---|
| `ll_keys()` | buttons held (`LL_UP` ... `LL_HINT`, `LL_HOME`, `LL_PAUSE`, `LL_VOLUP/DN`) |
| `ll_menu_combo(keys, before)` | call once a frame: HINT + A + B for 2.5 s calls `before()` (save there), then the menu |
| `ll_to_menu()` | back to the LeapLoader menu now |
| `ll_screen`, `ll_pixel`, `ll_fill`, `ll_show()` | 160 x 160, 12-bit colour (0xRGB), two pixels in three bytes (g0b0, r0r1, g1b1); draw in `ll_screen` (RAM), `ll_show()` copies it to the LCD |
| `ll_ticks()`, `ll_wait_frame()` | 16 MHz clock; wait for the next 1/60 s |
| `ll_awake()` | someone is playing: call while buttons are held (else the console powers off when idle) |
| `ll_fopen/fread/fwrite/fseek/fclose` | the BIOS's files; `b:\` is the SD card; fseek whence 0/1/2 |
| `ll_app_path("x.dat")` | `b:\Leapster\Apps\<id>\x.dat` (the app's folder, from `PlayGame.lnk`) |
| `ll_load_save(buf, n)`, `ll_write_save(buf, n)` | `save.bin` in the app's folder |
| `ll_alloc(n)` | memory from the heap (most of the 8 MiB the app doesn't use) |

Facts behind it (docs/how-it-works.md): the BIOS loads `game.bin` at 0x3C80_0000 (at most 8 MiB);
the card builder puts `code.bin` at offset 0x1_0000 and the image's 0x1009 resource points at its
native list; the main movie's first frame calls `__llapp()`, which never returns. While the app
runs, `b:\Leapster\PlayGame.lnk` holds the path of its `game.bin`. Going back to the menu writes the
menu's path there and calls `LC_Boot("ExtStorage")`, which restarts the console into it.
Drawing straight into VRAM (0x0300_0000) went black after button presses in the emulator, so the
SDK draws in RAM and copies each frame with uncached word stores.

Not in the SDK yet: sound (see the NES port's PCM code, `pcm_start`/`pcm_isr`), touch, a font.
`sdk/instruments.h` lists the Leapster instrument numbers (bank 0 of the community Leap-Font
soundfont; the `89 p` program command of a LeapFrog sequence), for when the SDK gets music.
