# Choosing games

The left of LeapLoader's window is the games list: a row for each dump you added. The rows are kept in A-Z order by name.

## Adding games

| Button | What it adds |
|---|---|
| **+  Add roms…** (also **File › Add roms…**) | The dumps you choose: `.bin` files, or `.zip` files with a dump in them |
| **📁  Add a folder…** (also **File › Add a folder of dumps…**) | Every `.bin` and `.zip` in a folder |
| **🐸  Import Ribbit's Rom Folder** | Every `.bin` and `.zip` in the Ribbit emulator's games folders. Shown only when LeapLoader finds Ribbit's settings on this computer; point at the button to see which folders |

LeapLoader remembers the list for next time. **File › Clear the list** empties it (your dumps stay where they are).

## The rows

Each row shows the game's name, its tags (region, edition, version, as Ribbit shows them), the dump's size and where the file is. Point at the file's path to see its CRC-32.

The badge on the right says what LeapLoader thinks of the dump:

| Badge | Meaning |
|---|---|
| **Compatible** (green, with a check mark) | A game LeapLoader knows: it converts and runs from the SD card (tested in the Ribbit emulator) |
| **Incompatible** (red, with a cross) | A dump LeapLoader doesn't know. It starts switched off |
| **May be skipped** (amber) | An incompatible dump you switched on anyway |
| **On the card** | After a build: the game was put on the card |
| **Skipped** | After a build: the game was left off. Point at the badge to see why |
| **Homebrew** (blue) | An app for the Leapster 2 rather than a game dump, such as the NES and Game Boy emulators LeapLoader comes with |

**NES** and **Game Boy** are on the list from the start: they are emulators that come with LeapLoader. Leave them on and build the card, then copy your own `.nes` files into the card's `NES` folder and `.gb` / `.gbc` files into `GB` and `GBC`. Take them off the list if you don't want them; they won't come back.

The heading says how many games are on the card, for example **12 of 75 on the card**, and how many dumps are incompatible.

## Compatible and incompatible

LeapLoader knows a game by its dump's CRC-32 (a fingerprint of the whole file), not by the file's name. The [compatibility list](../compatibility.md) has every game it knows.

A dump shows **Incompatible** when it isn't one of those: a game not tested yet, another version or region of a listed game, a damaged dump, or another console's file (a LeapPad dump, for example). You can switch it on anyway: LeapLoader then tries to convert it, but it may be left off the card, and if it does go on, it may not work.

## Switching games on and off

Only the games switched on go on the card. A game switched off is greyed out.

- **Click a row** to switch that game on or off.
- **Enable all** switches every compatible game on. It leaves the incompatible ones off: switch each of those on by itself.
- **Disable all** switches every game off.
- The **×** at the end of a row takes that dump off the list.

## Selecting several games

- **Ctrl+click** rows to select them, one by one. Selected rows have a purple edge.
- **Shift+click** selects every row from the last one you clicked to this one.
- **Ctrl+A** selects every row.

While rows are selected, the buttons above the list change:

| Button | Does |
|---|---|
| **Enable** | Switches the selected games on |
| **Disable** | Switches them off |
| **Remove** (or `Delete`) | Takes them off the list |
| **×** (or `Esc`) | Unselects them |

Nothing can be changed in the list while a card is being built.
