# Welcome to LeapLoader

LeapLoader puts your own Leapster cartridge games on an SD card for the **Leapster 2**. On the console, the SD icon on the home screen then opens LeapLoader's menu: pick a game and it starts as if its cartridge were in. Your progress is saved on the card, and holding **HINT + A + B** in a game saves and goes back to the menu.

LeapLoader runs on Windows 10 and 11 (64-bit), Linux (x86-64) and macOS 11 or later. macOS is new and less tested.

> **LeapLoader has not been tested on a real Leapster 2 yet.** Everything has been checked in the [Ribbit](https://github.com/MotifMixes/Ribbit) emulator only. Copy your SD card's files somewhere before you start, and please report what happens on your console.

## What you need

LeapLoader comes with **no games and no BIOS**. You need:

- a **Leapster 2** with an SD card in it (the first Leapster and the Leapster L-MAX have no SD card slot and can't use it),
- dumps of your own **Leapster cartridges** (`.bin` files, plain or zipped),
- a dump of your own **Leapster 2 BIOS** (0.6 152-12206, the Connected's B5 152-12076 or CIP3 m9 152-12659), for LeapLoader's menu: it plays its music with the BIOS's instruments, and none are included. If you use the Ribbit emulator, LeapLoader finds the BIOS picked there by itself. See [Settings](07-settings.md#leapster-2-bios).

Nothing else: there is nothing to install. The download brings everything LeapLoader uses, its own Python included.

Which games work: the [compatibility list](../compatibility.md).

## Made with AI

LeapLoader is written almost entirely by an AI coding assistant (Anthropic's Claude), under the direction of its author, who chooses what to work on, tests it, supplies the hardware references and decides what goes in. The first time you start LeapLoader it says so in a note, **This project was made with AI**; click **Continue** to go on.

LeapLoader is not affiliated with or endorsed by LeapFrog Enterprises.

## The pages of this guide

- [Getting started](02-getting-started.md): from the download to your first card.
- [Choosing games](03-choosing-games.md): adding dumps, compatible and incompatible games, switching them on and off.
- [Building the card](04-building-the-card.md): the menu, the output folder, the build log.
- [On the Leapster 2](05-on-the-leapster-2.md): the SD icon, LeapLoader's menu, saves and HINT + A + B.
- [Leapster 2 over USB](06-usb.md): building the card while it stays in the console (beta; Windows and Linux).
- [Settings](07-settings.md): the BIOS for the menu music, the research folder, Python.
- [When something goes wrong](08-troubleshooting.md): and the log to send with a report.
- [Updating](09-updating.md): new versions from inside LeapLoader.
