# Games: what works (2026-10-25)

Every row is **VERIFIED-EMU** only (research/sdboot-emu with Leapster 2 BIOS 0.6): the game was
converted (`mkcard.py`), booted from the SD card through the LeapLoader menu, and screenshots at
40/48/56/64 s show its title, sign-in, name entry or menu. **Nothing has been tried on real
hardware.** "Saving works" below means the save path is in place and the save file is written;
a full save → power off → load test has not been done for any game.
How the save kinds, HINT + A + B and big images work: [how-it-works.md](how-it-works.md).

Totals: **77 Leapster dumps (39 + 38 downloaded 2026-10-25): 77 convert, 77 run, 77 go back with HINT + A + B**
(2026-10-26 regression `D:\leaploader-tmp
ative\g8`, 74 of them twice in a row; no BIOS assert in any run).
**Correction 2026-10-26:** Cosmic Math, Letterpillar, Number Raiders and Word Chasers did NOT run before
2026-10-26: they asserted at their first sound (unrelocated 0x100D handle lists, how-it-works 5) and the
"name entry" seen in their screenshots was the console's own. They now reach gameplay. Save kinds below
are from before 2026-10-25: every game now gets the RAM chip (`save.dat`) unless it has no room (native chip, `save.bin`). `disprin`/`prinfrog`
are LeapPad dumps, not Leapster. Penguins of Madagascar runs since the user's new dump (2026-10-25; the old one had bit errors).

Names: the menu shows the box names from `research/gamenames.py` (by dump CRC-32), e.g. `letrfactry.bin`
= The Letter Factory, `storexplor.bin` = Story Explorers, `dispixcoll.bin` = Pixar Pals.

Save kinds: **AS shim** = Flash-only game, `save.dat` (4a); **RAM chip** = native-code game with
room, `save.dat` (4b); **native chip** = native-code game without room, `save.bin` (4c).
HINT + A + B: **prompt** = on-screen prompt with a progress bar; **native** = no prompt, hold 2.5 s.
Strays = reads of the empty cartridge window in the test run (0 is the goal).

## Original 39 dumps

| Game | MiB | Saves | HINT+A+B | Strays | Notes |
|---|---|---|---|---|---|
| 1st Grade | 8 | AS shim | prompt | 0 | |
| Animal Genius | 8 | RAM chip | prompt | 0 | |
| Cosmic Math | 4 | RAM chip | prompt | 0 | |
| Creature Create | 8 | RAM chip | prompt | 0 | |
| Disney Fairies (ES) | 8 | RAM chip | prompt | 0 | |
| Cars 2 | 8 | RAM chip | prompt | 0 | |
| Cars | 8 | RAM chip | prompt | 0 | two movie tables; HINT + A + B works since the stub writes saves natively (2026-10-25; how-it-works 3) |
| Ratatouille (EN, and USA dump) | 8 | RAM chip | prompt | 0 | |
| Disney Princess: Enchanted Learning | 8 | native chip | native | 0 | |
| Disney Princess: Worlds of Enchantment | 8 | native chip | native | 0 | |
| Dora: Camping Adventure / Piñata Party / Wildlife Rescue | 8/4/8 | RAM chip | prompt | 0 | |
| Madagascar | 8 | RAM chip | prompt | 0 | |
| Foster's Home for Imaginary Friends | 8 | RAM chip | prompt | 19 | reads at 0x8001_7DE8, owner not found yet |
| I Spy Challenger | 8 | RAM chip | prompt | 0 | |
| Kindergarten | 8 | RAM chip | prompt | 0 | |
| Learning with Leap | 8 | AS shim | prompt | 0 | |
| Letterpillar | 4 | RAM chip | prompt | 0 | |
| Letters on the Loose | 8 | RAM chip | prompt | 0 | |
| NASCAR | 8 | RAM chip | prompt | 0 | |
| Number Raiders | 4 | RAM chip | prompt | 0 | |
| Numbers on the Run | 8 | RAM chip | prompt | 0 | |
| Outwit | 8 | RAM chip | prompt | 0 | |
| Pet Pals (USA, and Adopt-a-Pal) | 8 | native chip | native | 0 | needs the chip to start zeroed (with 0xFF it shows junk names) |
| **Schoolhouse Rock: America Rock** | **16** | RAM chip | prompt | 0 | videos + songs on the card (`v0-v5.bin`); music video plays |
| Scooby-Doo Spooky Snacks | 4 | RAM chip | prompt | 0 | |
| Sonic X | 8 | RAM chip | prompt | 0 | |
| Spider-Man | 8 | RAM chip | prompt | 0 | |
| SpongeBob Saves the Day | 8 | AS shim | prompt | 0 | |
| SpongeBob Through the Wormhole | 4 | RAM chip | prompt | 0 | |
| Star Wars Jedi Math | 8 | RAM chip | prompt | 0 | |
| Star Wars Jedi Reading | 8 | RAM chip | prompt | 0 | earlier: black with the RAM chip; recheck by hand |
| **Talking Words Factory** | **16** | RAM chip | prompt | 0 | 8 stories on the card (`m1-m8.bin`); a story plays |
| The Batman: Multiply, Divide and Conquer (DE) | 8 | RAM chip | prompt | 0 | |
| Thomas & Friends | 8 | RAM chip | prompt | 0 | |
| Top-Secret Personal Beeswax (tspbeeswax) | 8 | RAM chip | prompt | 0 | |

## 38 downloaded 2026-10-25

| Game | MiB | Saves | HINT+A+B | Strays | Notes |
|---|---|---|---|---|---|
| 2nd Grade | 8 | RAM chip | prompt | 0 | fixed by the font rule |
| Adibou: À la recherche de Robitoc (FR) | 8 | RAM chip | prompt | 0 | |
| The Backyardigans | 8 | native chip | native | 0 | |
| The Batman: Strength in Numbers | 8 | RAM chip | prompt | 0 | |
| Bratz World | 8 | RAM chip | prompt | 0 | was garbled letters: its font starts 0x0650_0100 (font rule) |
| Cars Supercharged | 8 | RAM chip | prompt | 0 | dump repaired: 24-byte `LBK…` marker at 4 MiB removed |
| Clifford: Reading | 8 | native chip | native | 0 | |
| Crayola Art Adventure | 8 | RAM chip | prompt | 0 | |
| Digging for Dinosaurs | 8 | RAM chip | prompt | 0 | HINT+A+B → vanilla menu VERIFIED-EMU |
| Disney-Pixar Collection | 8 | RAM chip | prompt | 4 | |
| Disney Fairies (EN) | 8 | RAM chip | prompt | 4 | |
| Finding Nemo | 8 | native chip | native | 0 | |
| Get Puzzled! | 8 | RAM chip | prompt | 0 | |
| Go Diego Go! Animal Rescuer | 8 | native chip | native | 0 | was white: 571 resource handles had been "relocated" (handle rule); native HINT+A+B VERIFIED-EMU |
| I Spy Treasure Hunt | 8 | RAM chip | prompt | 0 | |
| The Incredibles | 8 | RAM chip | prompt | 0 | |
| Letter Factory | **16** | RAM chip | prompt | 0 | 7 stories on the card (`m*.bin`) |
| Math Baseball | 8 | AS shim | prompt | 0 | |
| Math Missions | 8 | RAM chip | prompt | 0 | |
| Mr. Pencil's Learn to Draw & Write | 8 | RAM chip | prompt | 0 | |
| My Amusement Park | 8 | RAM chip | prompt | 0 | |
| Ni Hao Kai-lan: Beach Day | 8 | RAM chip | prompt | 0 | checksum never written (FFFFFFFF); converted anyway |
| Oui-Oui (Noddy, FR) | 8 | RAM chip | prompt | 0 | |
| Penguins of Madagascar | 8 | RAM chip | prompt | 0 | new dump (checksum OK) reaches name entry; the old dump was damaged (~900k bytes differ, mostly single-bit) and stayed black |
| Phonics Lesson One | 8 | AS shim | prompt | 0 | |
| Reading with Phonics: Mole's Huge Nose | 8 | RAM chip | prompt | 0 | |
| Rock the World (L-Max) | 8 | RAM chip | prompt | 0 | was black: handles up to 0x8000_1A1F (handle rule) |
| Schoolhouse Rock: Grammar Rock | **16** | RAM chip | prompt | 0 | videos on the card; "A noun's a special kind of word" plays |
| Scooby-Doo Arcade | 2 | RAM chip | prompt | 0 | bitmaps with self pointers (table 13); reaches a game screen; 22,400 reads at 0x0F80_35A8 + writes to 0 remain (a bad image copy) |
| Scooby-Doo! Et les nombres fous (FR) | 4 | RAM chip | prompt | 0 | |
| Story Explorers | 16 | RAM chip | prompt | 0 | **pool mode** (how-it-works 6.4): 70 movies in `m.bin`, 2282 sound clips in `s.bin`; story + narration + first activity tested; later stories not reached |
| Tangled | 8 | RAM chip | prompt | 0 | |
| Toy Story 3 | 8 | RAM chip | prompt | 8 | |
| Up | 8 | RAM chip | prompt | 0 | |
| WALL-E (and Dec 2007 prototype) | 8 | native chip | native | 0 | |
| Wolverine and the X-Men | 8 | RAM chip | prompt | 0 | |
| Word Chasers | 4 | RAM chip | prompt | 0 | |

## Open
* Scooby-Doo Arcade's bad image copy,
  Foster's/Toy Story 3/Disney-Pixar Collection/Fairies EN small stray reads.
* A real save → power off → load test, per save kind.
* Sound of the Schoolhouse Rock songs while their videos play (only the picture is checked).
* Real hardware: nothing yet; loading a 2-3 MB story/video file may take a few seconds there.
