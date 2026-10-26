# When something goes wrong

## The build stops at once: "could not start python"

Python isn't installed, or Windows can't find it. Install it from [python.org](https://www.python.org/downloads/) with **Add python.exe to PATH** ticked, then start LeapLoader again. Or type the full path of `python.exe` in **File › Settings… › Python**. See [Getting started](02-getting-started.md#python).

Python 3.8 or newer is needed.

## "LeapLoader's research folder was not found"

LeapLoader can't find its `research` folder. Keep the release folder together: `LeapLoader.exe` needs `research\`, `nativescan.exe` and `arc-gnu\` beside it. If you started LeapLoader from inside the zip, unzip all of it first (right-click the zip, **Extract All…**). You can also choose the folder in **File › Settings… › Research folder**.

## The menu has no music

Open **View › Build log** and look for a line `note  menu without music: …`. It says what is missing:

- **Python is missing numpy** (or scipy): type `python -m pip install numpy scipy` in a Command Prompt, then build again. If pip says it made a "user installation", LeapLoader may not see the packages (it starts Python without the user's own package folder); run the Command Prompt as administrator and install them again.
- **no Leapster 2 BIOS given**: choose your Leapster 2 BIOS 0.6 dump in **File › Settings… › Leapster 2 BIOS**.
- **is not the Leapster 2 BIOS 0.6**: the file chosen is another BIOS version, or a damaged dump. Only 0.6 (152-12206) works.

Music can also be switched off on the console: **Pause › Music: On / Off** in the menu.

See [Settings](07-settings.md#leapster-2-bios).

## A game shows "Incompatible" or "May be skipped"

LeapLoader doesn't know that dump (see [Choosing games](03-choosing-games.md#compatible-and-incompatible)). It may be a game not tested yet, another version of a listed game, a damaged dump, or another console's file. You can switch it on and try it; if it is **Skipped** when the card is built, point at the badge to see why.

If the game is in the [compatibility list](../compatibility.md) but your dump shows Incompatible, your dump is different from the one tested. Dumping the cartridge again may help, as a damaged dump has a different CRC-32.

## A game was skipped

After a build, point at its **Skipped** badge, or look for its `skip …` line in **View › Build log**: it says why. **Copy** in the build log copies the whole log, to send with a report.

## The SD icon on the Leapster 2 stays grey, or does nothing

- Sign in as a player with a name. The SD icon doesn't work for **Guest**.
- Check that the card has the `Leapster` folder at its root (not inside another folder). If you built into a folder on the PC, copy the `Leapster` folder itself to the root of the card.
- Check that the build ended with **Card built**.

## HINT + A + B doesn't go back

Hold all three buttons together, and keep holding for about 2.5 seconds (until the bar fills, where there is one). Some games show no prompt at all: hold them anyway. On screens without a prompt (name entry, videos) it can take about 4 seconds.

## Leapster 2 over USB doesn't work

Click **Save USB log** (or **Copy USB log**) and send it, with what happened at each step. See [Leapster 2 over USB](06-usb.md#if-something-goes-wrong).

## Reporting a problem

Please say:

- what you did and what happened,
- which game, and whether it happened in the emulator or on a real Leapster 2 (and its BIOS version, if you know it),
- your Windows version,
- the build log (**View › Build log**, **Copy**), and the USB log if it was over USB.

Reports from real Leapster 2 consoles are especially welcome: nothing has been tested on one yet.
