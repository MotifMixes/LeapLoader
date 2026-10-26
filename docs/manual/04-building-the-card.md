# Building the card

The right of LeapLoader's window, **Card**, says which menu goes on the card, where the card is built, and how much room it takes.

The box at its top is a reminder: the card is for the Leapster 2 only (the first Leapster and the L-MAX have no SD card), and in a game you hold **HINT + A + B** (about 2.5 seconds) to save and go back to the menu. See [On the Leapster 2](05-on-the-leapster-2.md#back-to-the-menu-hint--a--b).

## The menu

Under **Menu**, choose the menu the Leapster 2's SD icon opens:

| Menu | What you get |
|---|---|
| **LeapLoader (Recommended)** | LeapLoader's own menu: the games' box names, 4 to a page, search, music. See [On the Leapster 2](05-on-the-leapster-2.md#leaploaders-menu) |
| **LeapFrog's SD menu** | LeapFrog's own menu: 6 game buttons a page, no music, no search |

LeapFrog's menu is not included with LeapLoader. To use it, click **Import .lfp…** and choose your own LeapFrog package for it (for example `LSTR-0x00130001-000000.lfp`). If the output folder already holds LeapFrog's menu from an earlier card, LeapLoader can use that one.

HINT + A + B goes back to whichever menu is on the card.

## The output folder

Under **Output folder**, click **Choose…** and pick where the card is built:

- **the SD card's drive** (with the card in the PC's card reader): the card is ready when the build ends; or
- **any folder**: then copy what is in it (the `Leapster` folder) to the root of the SD card.

The **📂** button (**Show the folder**) opens the folder in File Explorer.

LeapLoader writes only its `Leapster` folder there. It adds its games and menu and replaces the ones it built before; other files are left alone. It never formats the card.

### "This folder isn't empty"

If the folder holds other files (an SD card usually does), LeapLoader asks before it builds there. **Build here** goes ahead; **Cancel** stops. Nothing outside the `Leapster` folder is changed either way.

## Building

**On the card** shows how many games are switched on and about how much room they take (about the size of the dumps, plus the menu).

Click **Build card (N games)**. If the button can't be clicked, the words under it say why (no games yet, none chosen, no output folder, or the research folder wasn't found).

While it builds, a bar shows **Converting games… n of N**, then **Making the menu…**. **Stop** ends the build; what was written so far stays in the output folder, so build again before you use the card.

When it ends, LeapLoader says **Card built: N games**, and each row's badge shows **On the card** or **Skipped**. Point at a **Skipped** badge to see why the game was left off.

To change the card later, change the list and build again into the same place. Saves stay: a game's `save.dat` or `save.bin` is not overwritten. A game you take off the list is left out of LeapLoader's menu, but its folder (with its saves) stays on the card; delete the folder yourself if you want the room back.

## The build log

**View › Build log** shows what the converter says while it builds:

- green lines, `ok …`: a game put on the card, and the folder it went to;
- red lines, `skip …`: a game left off, and why;
- `note  menu without music: …`: the menu was built without music, and why (see [Settings](07-settings.md#leapster-2-bios));
- an error, if the build stopped.

**Copy** copies the whole log, for a bug report.

## What is on the card

| On the card | What it is |
|---|---|
| `Leapster\System\SDMenu\SDMenu.bin` | The menu the SD icon opens |
| `Leapster\Apps\<Game>\game.bin` | The game, converted to run from the SD card |
| `Leapster\Apps\<Game>\meta.inf`, `icon.swf` | The game's details and its button, for the console |
| `Leapster\Apps\<Game>\save.dat` or `save.bin` | The game's saves, made the first time it saves |

Games of 16 MiB keep some extra files in their folder (videos or stories), loaded when the game needs them.
