# Getting started

This page takes you from the download to your first card.

## Installing

There is nothing to install: the download is the finished app.

| System | Download | Then |
|---|---|---|
| Windows 10 or 11 (64-bit) | `LeapLoader-…-windows-x64.zip` | Unzip it and run **LeapLoader.exe** in the `LeapLoader` folder. |

Downloads are on the [releases page](https://github.com/MotifMixes/LeapLoader/releases/latest). Other systems are not offered yet.

Unzip the whole folder (right-click the zip, **Extract All…**) and keep its files together. LeapLoader uses the files beside it:

| In the folder | What it is |
|---|---|
| `LeapLoader.exe` | The app |
| `nativescan.exe` | A helper the converter uses |
| `arc-gnu\` | Tools the save code is built with |
| `research\` | The Python scripts that build the card |
| `README.txt`, `TESTING-USB.txt` | Short notes, and how to test [over USB](06-usb.md) |
| `LICENSE.txt`, `THIRD-PARTY-NOTICES.txt` | The licence (GNU GPL v3 or later) and the notices for the parts LeapLoader uses |

## Python

LeapLoader builds the card with Python scripts, so the PC needs **Python 3.8 or newer**, started as `python`.

1. Download Python from [python.org](https://www.python.org/downloads/).
2. In the installer, tick **Add python.exe to PATH** before you click **Install Now**.
3. To check: open a Command Prompt and type `python --version`. It should print `Python 3.…`.

For the menu's music (optional), also type `python -m pip install numpy scipy` there. See [Settings](07-settings.md#leapster-2-bios) for the BIOS the music needs too.

## Your first card

1. Copy everything on your Leapster 2's SD card to a folder on the PC, in case something goes wrong. LeapLoader never formats anything, but it hasn't been tried on a real console yet.
2. Start **LeapLoader.exe**.
3. Add your games: **+  Add roms…** for some dumps, or **📁  Add a folder of dumps…** for every dump in a folder. If you use the Ribbit emulator, **🐸  Import Ribbit's Rom Folder** adds the dumps from its games folder. See [Choosing games](03-choosing-games.md).
4. Games LeapLoader knows show **Compatible** and are switched on. The others show **Incompatible** and stay off.
5. On the right, under **Menu**, leave **LeapLoader (Recommended)** chosen.
6. Under **Output folder**, click **Choose…** and pick the SD card's drive (put the card in the PC's card reader first). You can also pick any folder and copy what LeapLoader makes there to the root of the SD card afterwards.
7. Click **Build card (N games)**. A bar shows how far it has got. When it's done, LeapLoader says **Card built: N games**.
8. Take the card out (use Windows' **Safely Remove Hardware** first), put it in the Leapster 2, turn it on and sign in. Tap the SD icon on the home screen, then pick a game with the D-pad and **A**. See [On the Leapster 2](05-on-the-leapster-2.md).
9. **In a game, hold HINT + A + B** for about 2.5 seconds to save and go back to LeapLoader's menu. Most games show a prompt with a bar; some show nothing, so keep holding. See [Back to the menu](05-on-the-leapster-2.md#back-to-the-menu-hint--a--b).

## Where your things are kept

LeapLoader's settings (your list of games, the output folder and so on) are kept in `%APPDATA%\LeapLoader` (paste it into File Explorer's address bar), not next to the program. The USB log is saved there too.

The games' saves are on the SD card, in each game's folder (see [Saves](05-on-the-leapster-2.md#saves)).
