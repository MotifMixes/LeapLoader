# LeapLoader

LeapLoader converts your own Leapster cartridge dumps so they run from an SD card on a Leapster 2, with a menu to
pick a game, working saves, and HINT + A + B to go back to the menu. No game or BIOS files are included: you need
your own dumps. So far it has been tested only in the [Ribbit](https://github.com/MotifMixes/Ribbit) emulator, not
on real hardware. LeapLoader is licensed under the GPL-3.0-or-later (see [LICENSE](LICENSE)).

**→ [Compatible games](docs/compatibility.md)**: the 75 games LeapLoader works with, and how far each was tested

**→ [User guide](docs/manual/01-welcome.md)**: every button and screen, step by step

> [!IMPORTANT]
> ## This project was made with AI
>
> **LeapLoader is written almost entirely by an AI coding assistant** (Anthropic's Claude, through Claude Code),
> working under my direction: I choose what to work on, test it, supply the hardware references and decide what
> goes in. The code, the research notes in `docs/` and most of the documentation were produced by the AI.
>
> I know many people in emulation and open source don't want to use AI-written software or contribute to it, for
> reasons I respect: questions about licensing and where training data comes from, code quality, and the work of
> people who reverse-engineer hardware by hand. If that's you, no hard feelings, and I'd rather you know up front
> than find out later. Please judge the project by its results and its sources: every hardware claim in `docs/` is
> labelled with how sure it is (VERIFIED, EVIDENCE, HYPOTHESIS, UNKNOWN) and where it comes from, and the tests are
> there to check the behaviour.
>
> LeapLoader is not affiliated with or endorsed by LeapFrog Enterprises. LeapFrog and Leapster are their trademarks.

> [!WARNING]
> **Nothing has been tested on a real Leapster 2 yet.** Every result so far comes from the Ribbit emulator's
> Leapster 2 (BIOS 0.6). Copy your SD card's files somewhere before you try a card, and please report what happens.

## What you need

* A **Leapster 2** with an SD card. The first Leapster and the Leapster L-MAX have no SD card slot and can't use
  LeapLoader.
* **Windows 10 or 11** (64-bit). Other systems are not offered yet.
* **Python 3.8 or newer**, started as `python`: get it from [python.org](https://www.python.org/downloads/) and tick
  **Add python.exe to PATH** in the installer. LeapLoader builds the card with Python scripts that come with it.
* Dumps of **your own Leapster cartridges** (`.bin`, plain or zipped). Which games work:
  [compatibility list](docs/compatibility.md).
* For the menu's music (optional): the Python packages numpy and scipy (`python -m pip install numpy scipy`) and a
  dump of your own **Leapster 2 BIOS 0.6** (152-12206). Without them the menu works, silently.

## Download and use

1. Open the **[latest release](https://github.com/MotifMixes/LeapLoader/releases/latest)** and, under *Assets*,
   download `LeapLoader-…-windows-x64.zip`. (The *Source code* files are for developers.)
2. Unzip it (right-click, **Extract All…**) and keep the `LeapLoader` folder together: `LeapLoader.exe` uses
   `nativescan.exe`, `arc-gnu\` and `research\` beside it. There is nothing to install.
3. Copy everything on your Leapster 2's SD card to the PC, in case something goes wrong. LeapLoader never formats
   anything.
4. Run **`LeapLoader.exe`** and add your games: **+ Add roms…**, **📁 Add a folder…**, or, if you use Ribbit,
   **🐸 Import Ribbit's Rom Folder**. Games LeapLoader knows show **Compatible** and are switched on; the others
   show **Incompatible** and stay off. Click a row to switch a game on or off.
5. On the right, keep **Menu: LeapLoader (Recommended)**, and under **Output folder** click **Choose…** and pick the
   SD card's drive (in the PC's card reader). Any folder works too: then copy its `Leapster` folder to the root of
   the card.
6. Click **Build card (N games)** and wait until it says **Card built**. **View → Build log** shows what happened to
   each game.
7. Put the card in the Leapster 2, turn it on and **sign in as a player** (not Guest). Tap the **SD icon** at the top
   right of the home screen: LeapLoader's menu opens.
8. Pick a game with the D-pad and **A** (or tap it). **Pause** opens the options: search, music on or off, sort,
   back to the Leapster's home screen.
9. **To go back to the menu from a game, hold HINT + A + B** for about 2.5 seconds. Most games show a prompt with a
   bar that fills; some show nothing, so just keep holding. The game saves first, then the console restarts into
   LeapLoader's menu.

Your progress is saved on the card, in each game's folder. Building the card again keeps the saves.

**Over USB (beta):** LeapLoader can also build the card while it stays in the console, through the Leapster 2's USB
cable (**Leapster 2 over USB**, bottom right). This has not been tried on a real console. See the
[guide](docs/manual/06-usb.md), and please send the USB log.

**Something wrong?** See [When something goes wrong](docs/manual/08-troubleshooting.md). Send the build log
(**View → Build log**, **Copy**) with your report.

## You need your own dumps

LeapLoader includes **no games and no BIOS**, and none will be accepted into this repository. Dump your own
cartridges (and, for the menu music, your own Leapster 2's BIOS). LeapLoader recognises a game by its dump's CRC-32;
a dump it doesn't know shows as Incompatible.

## Build from source (developers)

Players don't need this: download a release instead. The desktop app is in `app/` (Rust 1.88+, egui, as Ribbit's):

```sh
cd app
cargo test
cargo build --release
```

The card itself is built by the Python scripts in `research/` (`mkcard.py` and what it imports), which the app runs.
`python -I scripts/package-release.py` makes the Windows release zip.

## Documentation

* [User guide](docs/manual/01-welcome.md) and [compatible games](docs/compatibility.md)
* [How it works](docs/how-it-works.md): the card, the menus, HINT + A + B, saves, converting a cartridge, games
  over 8 MiB
* [Games](docs/games.md): per-game research notes
* [SD boot proof](docs/sd-boot-proof.md) and [research report](docs/research-report.md)
* [USB research](docs/usb-research.md) and [testing over USB](app/TESTING-USB.md)
