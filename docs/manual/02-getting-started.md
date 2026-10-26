# Getting started

This page takes you from the download to your first card.

## Installing

There is nothing to install, and you don't need Python or any other tool: the download is the finished app, with everything it uses.

| System | Download | Then |
|---|---|---|
| Windows 10 or 11 (64-bit) | `LeapLoader-…-windows-x64.zip` | Unzip it (right-click, **Extract All…**) and run **LeapLoader.exe** in the `LeapLoader` folder. |
| Linux x86-64 | `LeapLoader-…-linux-x64.tar.gz` | Unpack it (`tar -xzf LeapLoader-…-linux-x64.tar.gz`) and run `./leaploader` in the `LeapLoader` folder. |
| macOS 11 or later, Apple silicon | `LeapLoader-…-macos-arm64.zip` | Unzip it and drag **LeapLoader.app** to Applications. The first time, see [below](#the-first-time-on-macos). |
| macOS 11 or later, Intel | `LeapLoader-…-macos-x64.zip` | The same. |

Downloads are on the [releases page](https://github.com/MotifMixes/LeapLoader/releases/latest). The Linux version is built on Ubuntu 22.04: it runs on systems with glibc 2.35 or later. macOS is new and less tested than Windows and Linux.

On Windows and Linux, unpack the whole folder and keep its files together. LeapLoader uses the files beside it:

| In the folder | What it is |
|---|---|
| `LeapLoader.exe` (Linux: `leaploader`) | The app |
| `nativescan.exe` (Linux: `nativescan`) | A helper the converter uses |
| `arc-gnu` | Tools the save code is built with |
| `research` | The Python scripts that build the card |
| `python` | LeapLoader's own Python, which runs those scripts. It doesn't change any Python you may have |
| `README.txt`, `TESTING-USB.txt` | Short notes, and how to test [over USB](06-usb.md) |
| `LICENSE.txt`, `THIRD-PARTY-NOTICES.txt` | The licence (GNU GPL v3 or later) and the notices for the parts LeapLoader uses |

On macOS the same files are inside **LeapLoader.app**.

### The first time on macOS

LeapLoader isn't signed with an Apple Developer ID, so macOS stops it the first time. Right-click (or Control-click) **LeapLoader.app** in Applications, choose **Open**, then **Open** again. After that it starts as usual.

If macOS says LeapLoader "is damaged and can't be opened", open Terminal and type this once:

```sh
xattr -dr com.apple.quarantine /Applications/LeapLoader.app
```

## Your first card

1. Copy everything on your Leapster 2's SD card to a folder on the computer, in case something goes wrong. LeapLoader never formats anything, but it hasn't been tried on a real console yet.
2. Start LeapLoader. The first time, it shows a note, **This project was made with AI**, which ends with **Use at your own risk** in red: read it and click **Continue**. It isn't shown again.
3. Add your games: **+  Add roms…** for some dumps, or **📁  Add a folder of dumps…** for every dump in a folder. If you use the Ribbit emulator, **🐸  Import Ribbit's Rom Folder** adds the dumps from its games folder. See [Choosing games](03-choosing-games.md).
4. Games LeapLoader knows show **Compatible** and are switched on. The others show **Incompatible** and stay off.
5. On the right, under **Menu**, leave **LeapLoader (Recommended)** chosen.
6. LeapLoader's menu needs your **Leapster 2 BIOS 0.6** dump for its music. If you use Ribbit, LeapLoader finds the one picked there. If not, the **Card** panel says so: click **Choose your Leapster 2 BIOS…** and pick the file. See [Settings](07-settings.md#leapster-2-bios).
7. Under **Output folder**, click **Choose…** and pick the SD card's drive (put the card in the computer's card reader first). You can also pick any folder and copy what LeapLoader makes there to the root of the SD card afterwards.
8. Click **Build card (N games)**. A bar shows how far it has got. When it's done, LeapLoader says **Card built: N games**.
9. Eject the card (on Windows, **Safely Remove Hardware**; on Linux and macOS, eject it in the file manager or Finder), put it in the Leapster 2, turn it on and sign in. Tap the SD icon on the home screen, then pick a game with the D-pad and **A**. See [On the Leapster 2](05-on-the-leapster-2.md).
10. **In a game, hold HINT + A + B** for about 2.5 seconds to save and go back to LeapLoader's menu. Most games show a prompt with a bar; some show nothing, so keep holding. See [Back to the menu](05-on-the-leapster-2.md#back-to-the-menu-hint--a--b).

## Where your things are kept

LeapLoader's settings (your list of games, the output folder and so on) are kept in its data folder, not next to the program:

| System | Data folder |
|---|---|
| Windows | `%APPDATA%\LeapLoader` (paste it into File Explorer's address bar) |
| Linux and macOS | `~/.config/leaploader` |

The USB log and `leaploader.log` (what LeapLoader did at its last start, for [reports](08-troubleshooting.md#reporting-a-problem)) are saved there too.

The games' saves are on the SD card, in each game's folder (see [Saves](05-on-the-leapster-2.md#saves)).
