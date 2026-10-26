# When something goes wrong

## LeapLoader's log

LeapLoader writes what it does to `leaploader.log` in its data folder:

| System | Data folder |
|---|---|
| Windows | `%APPDATA%\LeapLoader` (paste it into File Explorer's address bar) |
| Linux and macOS | `~/.config/leaploader` |

The log is written again at each start, so it describes the last time LeapLoader ran. Please send it with any report, especially if LeapLoader didn't start or closed by itself: copy it before you start LeapLoader again.

## LeapLoader doesn't start, or closes by itself

If LeapLoader can't start, it shows an error message that says why and names `leaploader.log`. Send the log with what the message said.

LeapLoader 0.1.0 could open, hang a moment and close on some PCs, without a word: a graphics driver crashed while the window was being set up. From 0.2.0, LeapLoader tries several ways to draw its window, one after the other (on Windows: Vulkan, DirectX 12, OpenGL, then drawing in software; on Linux and macOS: the system's usual way, then OpenGL), and remembers a way that crashed, so the next start skips it. If it closed once, start it again.

- On Windows, it keeps the way that crashed in `gpu-setup-crashed.txt` in its data folder. Delete that file to make LeapLoader try every way again (after a graphics driver update, for example). An update of LeapLoader does too.
- To make LeapLoader draw in software straight away (Windows), set the environment variable `LEAPLOADER_SOFTWARE_GPU` to `1`: open a Command Prompt in the `LeapLoader` folder and type `set LEAPLOADER_SOFTWARE_GPU=1`, then `LeapLoader.exe`.

On macOS, the first start needs **Open** from the right-click menu; see [Getting started](02-getting-started.md#the-first-time-on-macos).

## The Build card button can't be clicked

The words under it say why. With **LeapLoader (Recommended)** as the menu, it says "Choose your Leapster 2 BIOS 0.6 dump first" when LeapLoader has no Leapster 2 BIOS yet: click **Choose your Leapster 2 BIOS…** and pick your BIOS 0.6 dump. See [Settings](07-settings.md#leapster-2-bios).

## The build stops: "the menu music can't be made"

The menu's music is made with your Leapster 2 BIOS, and the file chosen can't be used. The rest of the line says why:

- **is not the Leapster 2 BIOS 0.6 (152-12206)**: the file is another BIOS version, or a damaged dump. Only 0.6 works. Choose another file in **File › Settings… › Leapster 2 BIOS**.

Music can be switched off on the console: **Pause › Music: On / Off** in the menu. It can't be left off the card.

## "LeapLoader's research folder was not found"

LeapLoader can't find its `research` folder. Keep the release folder together: the program needs `research`, `python`, `nativescan` and `arc-gnu` beside it. If you started LeapLoader from inside the zip, unzip all of it first (right-click the zip, **Extract All…**). You can also choose the folder in **File › Settings… › Research folder**.

## A game shows "Incompatible" or "May be skipped"

LeapLoader doesn't know that dump (see [Choosing games](03-choosing-games.md#compatible-and-incompatible)). It may be a game not tested yet, another version of a listed game, a damaged dump, or another console's file. You can switch it on and try it; if it is **Skipped** when the card is built, point at the badge to see why.

If the game is in the [compatibility list](../compatibility.md) but your dump shows Incompatible, your dump is different from the one tested. Dumping the cartridge again may help, as a damaged dump has a different CRC-32.

## A game was skipped

After a build, point at its **Skipped** badge, or look for its `skip …` line in **View › Build log**: it says why. **Copy** in the build log copies the whole log, to send with a report.

## The SD icon on the Leapster 2 stays grey, or does nothing

- Sign in as a player with a name. The SD icon doesn't work for **Guest**.
- Check that the card has the `Leapster` folder at its root (not inside another folder). If you built into a folder on the computer, copy the `Leapster` folder itself to the root of the card.
- Check that the build ended with **Card built**.

## HINT + A + B doesn't go back

Hold all three buttons together, and keep holding for about 2.5 seconds (until the bar fills, where there is one). Some games show no prompt at all: hold them anyway. On screens without a prompt (name entry, videos) it can take about 4 seconds.

## Leapster 2 over USB doesn't work

Click **Save USB log** (or **Copy USB log**) and send it, with what happened at each step. See [Leapster 2 over USB](06-usb.md#if-something-goes-wrong). It works on Windows and Linux only; macOS can't do this yet.

## Update now doesn't work

See [Updating](09-updating.md). Where LeapLoader can't update itself, the updates window says why, and **Download** opens the release page so you can update by hand.

## For developers: another Python

A release package runs the card build with its own Python. If you typed another Python in **File › Settings… › Python** and the build says it **could not start** it, or that it is missing numpy or scipy, empty the field to go back to the one that comes with LeapLoader. Another Python must be 3.8 or newer, with numpy and scipy installed for all users: LeapLoader starts it without the user's own package folder, so a pip "user installation" isn't seen.

## Reporting a problem

Please say:

- what you did and what happened,
- which game, and whether it happened in the emulator or on a real Leapster 2 (and its BIOS version, if you know it),
- your system (Windows version, Linux distribution, or macOS version) and LeapLoader's version (**Help › About LeapLoader**),
- `leaploader.log` from the data folder (see [above](#leaploaders-log)),
- the build log (**View › Build log**, **Copy**), and the USB log if it was over USB.

Reports from real Leapster 2 consoles are especially welcome: nothing has been tested on one yet.
