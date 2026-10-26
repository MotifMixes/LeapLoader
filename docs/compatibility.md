# Compatible games

Which Leapster games LeapLoader can put on a Leapster 2's SD card, and how far each one has been tested.
Last updated 2026-10-26 (LeapLoader 0.2.0).

> [!WARNING]
> **Nothing has been tested on a real Leapster 2 yet.** Every result below comes from the
> [Ribbit](https://github.com/MotifMixes/Ribbit) emulator, with the Leapster 2 BIOS 0.6 (152-12206). A game that
> works there will very probably work on the console, but it has not been seen. Copy your SD card's files
> somewhere before you try a card, and please report what happens.

## At a glance

- **201 dumps** are recognised: the 75 games in the first table (tested from 77 dumps: two were in the test set twice) and 126 more versions, languages and prototypes in [Other versions, languages and prototypes](#other-versions-languages-and-prototypes).
- **All 75 convert and start from the SD card** through LeapLoader's menu, in the emulator.
- **All 75 go back to the menu** with HINT + A + B in the automated test (2026-10-26: every dump, twice in a row
  for 74 of the 77). On screens where the game's prompt can't appear (name entry, videos) hold the buttons for
  about 4 seconds.
- Saves are written in every game. Loading a save back after turning the console off has been checked in only a few
  games so far (Cars, 1st Grade).

## How a game is recognised

LeapLoader knows a game by its dump: it works out the dump's CRC-32 (a fingerprint of the whole file) and looks it up
in its list. The file's name doesn't matter.

- A dump on the list shows as **Compatible** in LeapLoader and is switched on.
- Any other dump shows as **Incompatible** and starts switched off. That can be a game not tested yet, a different
  version or region of a listed game, a damaged dump, or another console's file. You can switch it on anyway (it then
  shows **May be skipped**); LeapLoader tries it, but it may be left off when the card is built. See the
  [user guide](manual/03-choosing-games.md#compatible-and-incompatible).

If your copy of a game listed here shows as Incompatible, it is a different dump from the one tested.

## Status levels

| Column | Value | Meaning |
|---|---|---|
| **Starts from SD** | **Yes** | Converted, started from LeapLoader's menu, and reached its own title, sign-in, name entry or menu |
| **HINT + A + B** | **Yes** | Holding HINT + A + B in the game saved and went back to LeapLoader's menu |
| | **Yes, no prompt** | The same, but the game shows no prompt: hold the three buttons for about 2.5 seconds |
| **Saves** | `save.dat` / `save.bin` | The file the game's progress is kept in, in its folder on the card. Both kinds work the same for you |
| **Hardware** | **Untested** | Not tried on a real Leapster 2 (every game, for now) |

How the test was done: each dump was converted with LeapLoader, the card was put in Ribbit's Leapster 2, the game was
started from LeapLoader's menu, and screenshots were taken 40 to 64 seconds after power-on. Then HINT + A + B was
held and the screen checked for the menu. Nothing was played through to the end.

## Games

**Size** is the size of the cartridge dump. Games of 16 MiB are too big for the console's memory in one piece:
LeapLoader keeps some of their videos or stories as extra files on the card, loaded when the game needs them.

| Game | Size | Starts from SD | HINT + A + B | Saves | Notes |
|---|---|---|---|---|---|
| 1st Grade | 8 MiB | Yes | Yes | `save.dat` | Saves load back after power-off (emulator) |
| 2nd Grade | 8 MiB | Yes | Yes | `save.dat` |  |
| Adibou: A la recherche de Robitoc | 8 MiB | Yes | Yes | `save.dat` | French |
| Animal Genius | 8 MiB | Yes | Yes | `save.dat` |  |
| The Backyardigans | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| The Batman: Multiply, Divide and Conquer (German) | 8 MiB | Yes | Yes | `save.dat` | German |
| The Batman: Strength in Numbers | 8 MiB | Yes | Yes | `save.dat` |  |
| Bratz World | 8 MiB | Yes | Yes | `save.dat` |  |
| Cars | 8 MiB | Yes | Yes | `save.dat` | Saves load back after power-off (emulator) |
| Cars 2 | 8 MiB | Yes | Yes | `save.dat` |  |
| Cars: Supercharged | 8 MiB | Yes | Yes | `save.dat` | The tested dump had a marker left by the dumping tool; LeapLoader removes it |
| Clifford the Big Red Dog: Reading | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Cosmic Math | 4 MiB | Yes | Yes | `save.dat` |  |
| Crayola Art Adventure | 8 MiB | Yes | Yes | `save.dat` |  |
| Creature Create | 8 MiB | Yes | Yes | `save.dat` |  |
| Digging for Dinosaurs | 8 MiB | Yes | Yes | `save.dat` | Also goes back to LeapFrog's SD menu |
| Disney Fairies | 8 MiB | Yes | Yes | `save.dat` |  |
| Disney Fairies (Spanish) | 8 MiB | Yes | Yes | `save.dat` | Spanish |
| Disney Princess: Enchanted Learning | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Disney Princess: Worlds of Enchantment | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Dora the Explorer: Camping Adventure | 8 MiB | Yes | Yes | `save.dat` |  |
| Dora the Explorer: Pinata Party | 4 MiB | Yes | Yes | `save.dat` |  |
| Dora the Explorer: Wildlife Rescue | 8 MiB | Yes | Yes | `save.dat` |  |
| Finding Nemo | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Foster's Home for Imaginary Friends | 8 MiB | Yes | Yes | `save.dat` |  |
| Get Puzzled! | 8 MiB | Yes | Yes | `save.dat` |  |
| Go, Diego, Go! Animal Rescuer | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| I Spy Challenger | 8 MiB | Yes | Yes | `save.dat` | The prompt comes about a second late |
| I Spy Treasure Hunt | 8 MiB | Yes | Yes | `save.dat` |  |
| The Incredibles | 8 MiB | Yes | Yes | `save.dat` |  |
| Junie B. Jones: Top-Secret Personal Beeswax | 8 MiB | Yes | Yes | `save.dat` |  |
| Kindergarten | 8 MiB | Yes | Yes | `save.dat` |  |
| Learning with Leap | 8 MiB | Yes | Yes | `save.dat` |  |
| Letterpillar | 4 MiB | Yes | Yes | `save.dat` |  |
| The Letter Factory | 16 MiB | Yes | Yes | `save.dat` | 7 story files stay on the card |
| Letters on the Loose | 8 MiB | Yes | Yes | `save.dat` |  |
| Madagascar | 8 MiB | Yes | Yes | `save.dat` |  |
| Math Baseball | 8 MiB | Yes | Yes | `save.dat` |  |
| Mr. Pencil's Learn to Draw & Write | 8 MiB | Yes | Yes | `save.dat` |  |
| My Amusement Park | 8 MiB | Yes | Yes | `save.dat` |  |
| NASCAR | 8 MiB | Yes | Yes | `save.dat` |  |
| Ni Hao, Kai-lan: Beach Day | 8 MiB | Yes | Yes | `save.dat` | The cartridge's own checksum doesn't match (it was never filled in); LeapLoader converts it anyway |
| Number Raiders | 4 MiB | Yes | Yes | `save.dat` |  |
| Numbers on the Run: Counting on Zero | 8 MiB | Yes | Yes | `save.dat` |  |
| Oui-Oui: Aventures au Pays des Jouets | 8 MiB | Yes | Yes | `save.dat` | French |
| Outwit! | 8 MiB | Yes | Yes | `save.dat` |  |
| The Penguins of Madagascar | 8 MiB | Yes | Yes | `save.dat` | An older, damaged dump of this game stayed on a black screen; a good dump works |
| Pet Pals | 8 MiB | Yes | Yes | `save.dat` | In the test set twice (the same dump under two file names); Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Phonics: Lesson One | 8 MiB | Yes | Yes | `save.dat` |  |
| Pixar Pals | 8 MiB | Yes | Yes | `save.dat` |  |
| Ratatouille | 8 MiB | Yes | Yes | `save.dat` | In the test set twice (the same dump under two file names) |
| Reading with Phonics: Mole's Huge Nose | 8 MiB | Yes | Yes | `save.dat` |  |
| Rock the World | 8 MiB | Yes | Yes | `save.dat` | L-MAX edition |
| Scholastic Math Missions | 8 MiB | Yes | Yes | `save.dat` |  |
| Schoolhouse Rock! America Rock | 16 MiB | Yes | Yes | `save.dat` | 6 video and song files stay on the card; a music video plays (its sound not checked yet) |
| Schoolhouse Rock! Grammar Rock | 16 MiB | Yes | Yes | `save.dat` | 6 video files stay on the card; a video plays (its sound not checked yet) |
| Scooby-Doo! Arcade | 2 MiB | Yes | Yes | `save.dat` | Reaches a game screen; one known fault in how a picture is copied is still being looked at |
| Scooby-Doo! Et les nombres fous ! | 4 MiB | Yes | Yes | `save.dat` | French |
| Scooby-Doo! Spooky Snacks | 4 MiB | Yes | Yes | `save.dat` |  |
| Sonic X | 8 MiB | Yes | Yes | `save.dat` |  |
| Spider-Man: The Case of the Sinister Speller | 8 MiB | Yes | Yes | `save.dat` |  |
| SpongeBob SquarePants: Saves the Day | 8 MiB | Yes | Yes | `save.dat` |  |
| SpongeBob SquarePants: Through the Wormhole | 4 MiB | Yes | Yes | `save.dat` |  |
| Star Wars: Jedi Math | 8 MiB | Yes | Yes | `save.dat` |  |
| Star Wars: Jedi Reading | 8 MiB | Yes | Yes | `save.dat` |  |
| Story Explorers | 16 MiB | Yes | Yes | `save.dat` | 2 files of stories and sounds stay on the card; tested to the first activity, later stories not reached yet |
| The Talking Words Factory | 16 MiB | Yes | Yes | `save.dat` | 8 story files stay on the card; a story plays |
| Tangled | 8 MiB | Yes | Yes | `save.dat` |  |
| Thomas & Friends: Calling All Engines | 8 MiB | Yes | Yes | `save.dat` |  |
| Toy Story 3 | 8 MiB | Yes | Yes | `save.dat` |  |
| Up | 8 MiB | Yes | Yes | `save.dat` |  |
| WALL-E | 8 MiB | Yes | Yes, no prompt | `save.bin` |  |
| WALL-E (Prototype) | 8 MiB | Yes | Yes, no prompt | `save.bin` | A prototype build from December 2007 |
| Wolverine and the X-Men | 8 MiB | Yes | Yes | `save.dat` |  |
| Word Chasers | 4 MiB | Yes | Yes | `save.dat` |  |

Every game: **Hardware: Untested.**

## Other versions, languages and prototypes

Added 2026-10-26 (LeapLoader 0.2.0): 126 more dumps, tested the same way (converted, started from the SD card,
HINT + A + B held twice). Many are the versions most people have: other USA dumps of games in the first table, and
their French, German and Spanish editions. If your copy of a game showed **Incompatible** in LeapLoader 0.1.0, it is
probably one of these.

| Game | Size | Starts from SD | HINT + A + B | Saves | Notes |
|---|---|---|---|---|---|
| A la conquete des nombres (France) | 4 MiB | Yes | Yes | `save.dat` |  |
| Batman, The - El poder de los numeros (Spain) | 8 MiB | Yes | Yes | `save.dat` |  |
| Batman, The - Multiply, Divide, and Conquer | 8 MiB | Yes | Yes | `save.dat` |  |
| Bob l'eponge - Heros d'un jour (France) | 8 MiB | Yes | Yes | `save.dat` |  |
| Bratz J2S (12-24-03) | 8 MiB | Yes | Yes | `save.dat` |  |
| Cars (Spain) | 8 MiB | Yes | Yes | `save.dat` |  |
| Cosmic Math (USA) (v1.1) | 4 MiB | Yes | Yes | `save.dat` |  |
| Didou - Dessine-Moi une Aventure ! (France) | 8 MiB | Yes | Yes | `save.dat` |  |
| Dis pourquoi Kirikou (France) | 8 MiB | Yes | Yes | `save.dat` |  |
| Disney Princesa - La magia de aprender (Spain) | 8 MiB | Yes | Yes | `save.dat` |  |
| Disney Princess - Enchanted Learning (1.8 Beta Prototype) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Disney Princess - Enchanted Learning (USA) (Beta) (2004-06-22) | 8 MiB | Yes | Yes | `save.dat` |  |
| Disney Princesse - La magie d'apprendre (France) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Disney Prinzessinnen - Zauberhaftes Lernen (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| Dora - Retter der Wildnis (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| Dora l'exploratrice - Au secours des animaux (France) | 8 MiB | Yes | Yes | `save.dat` |  |
| Dora L'exploratrice - Le pont casse (France) | 4 MiB | Yes | Yes | `save.dat` |  |
| Dora the Explorer - Wildlife Rescue (10-23-03 Prototype) | 8 MiB | Yes | Yes | `save.dat` |  |
| Findet Nemo (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| gCAR'Alpha1.01b'041206 | 8 MiB | Yes | Yes | `save.dat` |  |
| Grundschule 1 (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| Grundschule 2 - Musik in Gefahr (Germany) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Incredibles Animation Sample 1 (3-22-04) | 8 MiB | Yes | Yes | `save.dat` |  |
| Incredibles Animation Submission 2 (4-13-04) | 8 MiB | Yes | Yes | `save.dat` |  |
| Incredibles, The (USA) | 8 MiB | Yes | Yes | `save.dat` |  |
| Kindergarten (USA) (Beta) (2003-09-09) | 8 MiB | Yes | Yes | `save.dat` |  |
| La riviere des lapins ' L'atelier de peinture (France) | 4 MiB | Yes | Yes | `save.dat` |  |
| Lapin Malin - Danse avec les mots (France) | 8 MiB | Yes | Yes | `save.dat` |  |
| Learning With Leap (Promo Cart) | 8 MiB | Yes | Yes | `save.dat` |  |
| Lernen mit Leap (Germany) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Mit Bruno Bleistift lernst du Malen & Schreiben (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| Nihao Kai-Lan | 8 MiB | Yes | Yes | `save.dat` |  |
| Pet Pals (11-30-06 Prototype) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Ratatouille (France) | 8 MiB | Yes | Yes | `save.dat` |  |
| Ratatouille (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| Scooby-Doo! (USA) | 8 MiB | Yes | Yes | `save.dat` |  |
| Sonic X (USA) (Leapster2) | 8 MiB | Yes | Yes | `save.dat` |  |
| Spider-Man - L'affaire des mots mysteres (France) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Spider-Man - Schachmatt den Schildersaboteuren! (Germany) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Spider-Man - The Case of the Sinister Speller (USA) (L-MAX) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Spider-Man early prototype | 8 MiB | Yes | Yes | `save.dat` |  |
| Spongebob Schwammkopf - Zeitreise durch das Wurmloch (Germany) | 4 MiB | Yes | Yes | `save.dat` |  |
| Spongebob Schwammkopf hat alles im Griff (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| Spongebob Squarepants - Saves the Day (USA) (L-MAX) | 8 MiB | Yes | Yes | `save.dat` |  |
| SpongeBob SquarePants Saves the Day (USA) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Star Wars - Matematicas Jedi (Spain) (En) | 8 MiB | Yes | Yes | `save.dat` |  |
| Toy Story 3 (France) | 8 MiB | Yes | Yes | `save.dat` |  |
| Up (Spain) | 8 MiB | Yes | Yes | `save.dat` |  |
| Vorschule (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| Wall-E (Germany) | 8 MiB | Yes | Yes | `save.dat` |  |
| Wall-E (Spain) | 8 MiB | Yes | Yes | `save.dat` | Its sound clips stay on the card (`s.bin`): that made room for the saves |
| Weltraum-Mathe (Germany) | 4 MiB | Yes | Yes | `save.dat` |  |
| Woerterjaeger (Germany) | 4 MiB | Yes | Yes | `save.dat` |  |
| Zahlenjaeger (Germany) | 4 MiB | Yes | Yes | `save.dat` |  |

**Prototypes** (development builds), tested and working the same way:

- **Cars**: 13 builds
- **Cars (French)**: 12 builds
- **Cars (German)**: 10 builds
- **Cars: Supercharged**: 2 builds
- **Go, Diego, Go! Animal Rescuer**: 2 builds
- **NASCAR**: 8 builds
- **Numbers on the Run: Counting on Zero**: 10 builds
- **Ratatouille**: 8 builds
- **Ratatouille (German)**: 7 builds

Every game: **Hardware: Untested.**

## Not compatible

- **Original Leapster and Leapster L-MAX consoles**: they have no SD card slot, so they can't use a LeapLoader card.
  The games above are Leapster cartridges; the card is for the Leapster 2.
- **LeapPad and other LeapFrog systems' dumps**: not Leapster games. LeapLoader shows them as Incompatible.

## Report a result

If you try a card on a real Leapster 2, please say which games you tried, what happened, and your console's BIOS
version if you know it. A game that doesn't start, a save that doesn't come back, and HINT + A + B that doesn't go
back are all worth reporting.
