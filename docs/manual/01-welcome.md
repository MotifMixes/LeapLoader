# Welcome to LeapLoader

LeapLoader puts your own Leapster cartridge games on an SD card for the **Leapster 2**. On the console, the SD icon on the home screen then opens LeapLoader's menu: pick a game and it starts as if its cartridge were in. Your progress is saved on the card, and holding **HINT + A + B** in a game saves and goes back to the menu.

LeapLoader runs on Windows 10 and 11 (64-bit).

> **LeapLoader has not been tested on a real Leapster 2 yet.** Everything has been checked in the [Ribbit](https://github.com/MotifMixes/Ribbit) emulator only. Copy your SD card's files somewhere before you start, and please report what happens on your console.

## What you need

LeapLoader comes with **no games and no BIOS**. You need:

- a **Leapster 2** with an SD card in it (the first Leapster and the Leapster L-MAX have no SD card slot and can't use it),
- dumps of your own **Leapster cartridges** (`.bin` files, plain or zipped),
- **Python** 3.8 or newer on the PC: LeapLoader builds the card with Python scripts (see [Getting started](02-getting-started.md#python)).

For the menu's music you also need two Python packages and a dump of your Leapster 2's BIOS. They are optional: without them the menu works, silently. See [Settings](07-settings.md#leapster-2-bios).

Which games work: the [compatibility list](../compatibility.md).

## Made with AI

LeapLoader is written almost entirely by an AI coding assistant (Anthropic's Claude), under the direction of its author, who chooses what to work on, tests it, supplies the hardware references and decides what goes in.

LeapLoader is not affiliated with or endorsed by LeapFrog Enterprises.

## The pages of this guide

- [Getting started](02-getting-started.md): from the download to your first card.
- [Choosing games](03-choosing-games.md): adding dumps, compatible and incompatible games, switching them on and off.
- [Building the card](04-building-the-card.md): the menu, the output folder, the build log.
- [On the Leapster 2](05-on-the-leapster-2.md): the SD icon, LeapLoader's menu, saves and HINT + A + B.
- [Leapster 2 over USB](06-usb.md): building the card while it stays in the console (beta).
- [Settings](07-settings.md): Python, the research folder, the BIOS for the menu music.
- [When something goes wrong](08-troubleshooting.md).
