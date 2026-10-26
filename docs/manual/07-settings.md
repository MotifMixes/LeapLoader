# Settings

**File › Settings…** sets where LeapLoader finds the tools that build the card. In the release folder they are all found by themselves, so most people never need to change anything here.

| Setting | What it is | Usually |
|---|---|---|
| **Research folder** | The folder with LeapLoader's Python scripts (`mkcard.py`) | The `research` folder beside `LeapLoader.exe`. Click it to choose another; **×** finds the one next to the program again |
| **Python** | The command that starts Python | `python`. Type the full path of `python.exe` here if Python isn't on the PATH |
| **nativescan** | A helper the converter uses | `nativescan.exe` beside `LeapLoader.exe`. Click it to choose another; **×** goes back to the default |
| **Leapster 2 BIOS** | Your Leapster 2's BIOS dump, for the menu music | Found from the Ribbit emulator's settings, if you use Ribbit. Else **(none: no menu music)** |

The settings are kept in `%APPDATA%\LeapLoader\settings.toml`.

## Python

LeapLoader starts Python by itself while it builds; you never have to run a script. If the build says it **could not start python**, Python isn't installed or isn't on the PATH: see [Getting started](02-getting-started.md#python), or type the full path of `python.exe` in **Python** (for example `C:\Users\you\AppData\Local\Programs\Python\Python312\python.exe`).

## Leapster 2 BIOS

LeapLoader's menu plays music with the Leapster 2's own instruments, which are in its BIOS. LeapLoader includes no BIOS, so for the music it needs:

1. a dump of your own **Leapster 2 BIOS 0.6** (152-12206), and
2. the Python packages **numpy** and **scipy**: open a Command Prompt and type `python -m pip install numpy scipy`.

If you use the Ribbit emulator, LeapLoader uses the Leapster 2 BIOS picked there. Otherwise click the button next to **Leapster 2 BIOS** and choose the file. **×** goes back to the one picked in Ribbit.

Without either of them the menu works, without music. The [build log](04-building-the-card.md#the-build-log) then says why, for example:

- `note  menu without music: Python is missing numpy (pip install numpy scipy)`
- `note  menu without music: no Leapster 2 BIOS given (--bios)`
- `note  menu without music: … is not the Leapster 2 BIOS 0.6 (152-12206)`: another BIOS version was chosen. Only 0.6 is supported.

The BIOS file itself doesn't go on the card. The music made from it does, and it holds the BIOS's instrument sounds, so keep your card for your own use.
