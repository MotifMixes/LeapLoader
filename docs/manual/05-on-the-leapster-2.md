# On the Leapster 2

> Everything on this page has been seen in the Ribbit emulator's Leapster 2 (BIOS 0.6, and the Connected's B5), not yet on a real console.

## Starting the menu

1. Put the SD card in the Leapster 2 and turn it on.
2. **Sign in as a player** with a name. The SD icon doesn't work for **Guest**.
3. On the home screen, the **SD icon** (the arcade cabinet at the top right) is now in colour. Tap it.
4. The console shows "Loading…" and starts the menu on the card.

LeapLoader's menu says "Welcome to LeapLoader. Select a game." and plays its music, made with the instruments of your Leapster 2 BIOS (see [Settings](07-settings.md#leapster-2-bios)). **Pause › Music: Off** turns it off.

If you built the card with **LeapFrog's SD menu**, the SD icon opens that one instead, with its own buttons.

## LeapLoader's menu

The heading shows **My Games** and how many there are. The games are listed 4 to a page by their box names; the footer shows **Page n/m**. A long name scrolls while it is selected.

| To | Do |
|---|---|
| Move up and down the list | D-pad up / down |
| Turn a page | D-pad left / right, or tap the up / down arrows on the right. From the last page it goes round to the first |
| Start a game | **A**, or tap the game |
| Search | Tap the magnifying glass on the right, or **Pause › Search** |
| Open the options | **Pause** |
| Go back to the console's home screen | **Home**, or **Pause › Leapster Home** |

Starting a game restarts the console into it, as if its cartridge were in.

## Options (Pause)

**Pause** opens the options. Choose with the D-pad and **A**, or tap one. **B** or **Pause** goes back to the list.

| Option | Does |
|---|---|
| **Search** | Opens the search keyboard (below) |
| **Resume** | Back to the list |
| **Music: On** / **Music: Off** | Turns the menu's music on or off |
| **Sort: A-Z** / **Sort: Recent** | Lists the games A-Z, or the ones played last first |
| **Leapster Home** | Back to the console's home screen |
| **About** | LeapLoader's version and how many games are on the card |

The music and sort choices, and the games played last, are kept on the card (`Leapster\System\SDMenu\LeapLoader.txt`), so they stay the next time.

## Search

The search keyboard is laid out like the console's name entry: the letters A to Z, a full stop and a space, then delete, **CLR** and **OK**.

- Choose a key with the D-pad and press **A**, or tap it.
- **B** deletes the last letter. **CLR** clears the text.
- **OK** searches. **Pause** cancels.

The search finds the text anywhere in a name: "ZZ" finds Get Puzzled!. The list then shows only those games, with **Search: …** at the top, or **No games found.** An empty search shows every game again.

## Back to the menu: HINT + A + B

In a game, **hold HINT + A + B** together to save and go back to the menu:

- **Most games** show a prompt, "Back to the LeapLoader menu", with a bar. Keep holding until the bar fills (about 2.5 seconds). Let go before that to stay in the game.
- **Some games** show no prompt (the [compatibility list](../compatibility.md) says which: "Yes, no prompt"). Hold the three buttons for about 2.5 seconds anyway.

The game writes its save, and the console restarts into the menu on the card. On a card with LeapFrog's menu the prompt says "Back to the SD Menu".

On some screens the game can't show its prompt (name entry, videos). Keep holding there: after about 4 seconds LeapLoader takes you back to the menu anyway.

## NES and Game Boy

The emulators are the **blue buttons** in the menu. Each opens a list of the games in its folder on the card (`NES`, or `GB` and `GBC`), drawn like LeapLoader's menu: Up/Down choose, Left/Right change page, **A** or a touch starts a game, **PAUSE** or the magnifying glass searches, **HOME** goes back to LeapLoader's menu.

In a game: the D-pad is the D-pad, **A** is the console's B button and **B** its A button, **PAUSE** is Start, **HINT** is Select, and the volume buttons set the volume. **HINT + A + B** held 2.5 s (a bar fills) goes back to the emulator's list, and so does **HOME + PAUSE** held 2 s. Battery saves are written next to the game (`GAME.sav`).

## Saves

Each game saves as it would on its cartridge, but into a file in its folder on the card: `save.dat` or `save.bin`, made the first time it saves. Holding HINT + A + B writes any save still waiting before it leaves the game.

To keep your progress safe, go back to the menu with HINT + A + B before you turn the console off, or at least wait a moment after the game saves. Loading a save after turning off has been checked in only a few games so far.

To start a game afresh, delete its `save.dat` or `save.bin` on the computer (keep a copy if you might want it back).
