# Settings

**File › Settings…** sets where LeapLoader finds the tools that build the card, and your Leapster 2 BIOS. In the release folder the tools are all found by themselves, so most people only ever need the BIOS here, if LeapLoader didn't find it.

| Setting | What it is | Usually |
|---|---|---|
| **Research folder** | The folder with LeapLoader's Python scripts (`mkcard.py`) | The `research` folder beside the program. Click it to choose another; **×** finds the one next to the program again |
| **Python** | The Python that runs those scripts | Empty: **the one that comes with LeapLoader**. Only for developers who want another Python |
| **nativescan** | A helper the converter uses | `nativescan` beside the program. Click it to choose another; **×** goes back to the default |
| **Leapster 2 BIOS** | Your Leapster 2 BIOS dump, for LeapLoader's menu music | Found from the Ribbit emulator's settings, if you use Ribbit. Else **Choose… (needed for the menu)** |

The settings are kept in `settings.toml` in LeapLoader's data folder: `%APPDATA%\LeapLoader` on Windows, `~/.config/leaploader` on Linux and macOS.

## Leapster 2 BIOS

LeapLoader's menu always has music, played with the Leapster 2's own instruments, which are in its BIOS. LeapLoader includes no BIOS, so it needs a dump of your own **Leapster 2 BIOS**.

If you use the Ribbit emulator, LeapLoader uses the Leapster 2 BIOS picked there. Otherwise click **Choose… (needed for the menu)** next to **Leapster 2 BIOS** and choose the file (or **Choose your Leapster 2 BIOS…** in the **Card** panel, which does the same). **×** goes back to the one picked in Ribbit.

Until a BIOS is chosen, **Build card** can't be clicked while **LeapLoader (Recommended)** is the menu. **LeapFrog's SD menu** has no music and needs no BIOS.

Any Leapster 2 BIOS works: 0.6 (152-12206), the Leapster Connected's B5 (152-12076) or CIP3 m9 (152-12659). They have the same instruments, and the menu comes out the same. It doesn't have to be the BIOS of the console you'll play on. If the file chosen is another BIOS, or a damaged dump, the build stops and the [build log](04-building-the-card.md#the-build-log) says:

- `the menu music can't be made: … is not a Leapster 2 BIOS (0.6 152-12206, Connected B5 152-12076 or CIP3 m9 152-12659)`

The BIOS file itself doesn't go on the card. The music made from it does, and it holds the BIOS's instrument sounds, so keep your card for your own use.

## Python

LeapLoader builds the card with Python scripts, and it brings its own Python for them (the `python` folder beside the program, with the numpy and scipy packages the music needs). You never have to install Python or run a script.

Leave **Python** empty. It is for developers who want LeapLoader to use another Python: type its command or the full path of its program there. That Python needs numpy and scipy, installed for all users (LeapLoader starts Python without the user's own package folder).
