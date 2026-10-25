# LeapLoader research report (Phase 1)

Date: 2026-10-24. Scope: what the Ribbit project (`..\Ribbit`, 238 commits, last
`e97cea0`) already knows about the **Leapster 2**, plus new firmware analysis done for this report, and what
that means for loading cartridge dumps onto a real Leapster 2 from an SD card.

## Confidence labels

These are the same labels Ribbit uses, so the two projects can be read side by side.

| Label | Meaning |
|---|---|
| **VERIFIED-FW** | Read from a Leapster 2 BIOS dump (disassembly or data), with addresses given so it can be checked again. Static analysis only: it describes what the code does, not that hardware behaves that way. |
| **VERIFIED-EMU** | Observed by running the BIOS in Ribbit. |
| **SOURCED** | Stated by one outside source (MAME, Wikipedia, a seller listing). Not checked. |
| **HYPOTHESIS** | Consistent with the evidence, not proven. |
| **UNKNOWN** | No usable information. |

**Nothing in this report has been tested on a real Leapster 2.** No one on this project has yet launched a
game from SD on real hardware.

---

## 0. Summary

1. **All three known Leapster 2 BIOSes include a developer "load a game from SD into RAM and boot it"
   path** (VERIFIED-FW). It reads a control file named `PlayGame.lnk`, which holds the path of an image. It
   copies that file to RAM at `0x3C80_0000` and registers it as a fourth content source, alongside the
   BIOS, the cartridge and the NAND. The original Leapster and L-MAX BIOSes do not have it.
2. The stock menu can switch to that path: its launch function, given the target `"ExtStorage"`, sets
   the boot selector to "SD" and restarts the console, with no other check (VERIFIED-FW). **We don't know yet
   how a retail unit reaches that call**, whether through a hidden menu, a "trap door" movie, a flag in the
   menu's Flash script (`iLoadFromSD`) or a cartridge.
3. **A raw cartridge `.bin` will almost certainly not work as is.** A cartridge image is built to sit at
   `0x8000_0000`. Its header records that base address, and all its internal pointers are absolute
   (VERIFIED-FW on two dumps). Copied to `0x3C80_0000`, those pointers would still aim at the cartridge slot.
   Making it work needs a **relocation** step, which only fits games without native ARC code. RAM also
   limits the image to **at most 8 MiB**, so 16 MiB cartridges are out.
4. **Hardware split.** Early units (BIOS 0.6 / "Connected" B5) have a full-size SD slot with a factory card
   in it. Later CIP3 units (BIOS m9) have **internal NAND and no SD driver** (VERIFIED-FW; slot SOURCED).
   On CIP3 units "SD" means internal flash that a PC can reach only over LeapFrog's USB protocol, which is
   unknown.
5. **No Leapster 2 flash cartridge or SD loader exists that we could find.** The Linux/emulator hacks on
   the web are for the LeapsterGS/Explorer, which are unrelated ARM hardware.
6. **Recommended strategy:** prove the stock BIOS's SD path end to end **in Ribbit first**. Ribbit already
   emulates the Leapster 2's SD controller, FAT volume and boot selector. Build LeapLoader's "prepare" step
   around what that proof shows. Then test on an SD-slot (0.6/B5) unit. See §7.

---

## 1. What Ribbit has already established

Sources: `docs/hardware-research.md`, `docs/open-questions.md`, `docs/compatibility.md`,
`crates/ribbit-memory/src/{cartridge,known,known_carts,image,map}.rs`, `crates/ribbit-core/src/io/{sd,fat,
nand,spiflash,usb}.rs`, MAME `leapster.cpp`/`leapster.xml` (copy in `tools/ref/mame-master-leapster`).

| Area | Finding | Status |
|---|---|---|
| CPU | ARCtangent-A5 (ARCompact ISA), little-endian, XY/DSP extension, MQX RTOS | SOURCED (MAME) and VERIFIED-EMU (Ribbit runs the BIOSes) |
| Content model | Games are Flash 5 SWF movies played by a Flash player **in the BIOS**. Some titles (e.g. Sonic X) also carry their own native ARC code | VERIFIED-FW / VERIFIED-EMU |
| Cartridge bus | 60-pin edge: 16-bit data, A0-A23, CE, OE, **WE**, Byte; a 24LC02B I²C EEPROM on two pins | SOURCED (MAME pinout) |
| Cartridge window | Image mapped linearly at `0x8000_0000`, 4/8/16 MiB (34/228/8 MAME entries) | VERIFIED |
| Cartridge directory | `"LEAP"` magic, u16 version, u16 count, `{tag,count,ptr}` table, tag `0x1003` = text metadata (part number, title, toolchain, build date) | VERIFIED on SpongeBob only |
| Identification | CRC32 + SHA-1 of MAME's 136-entry software list (`known_carts.rs`), BIOS table (`known.rs`) | Works (Ribbit's tests) |
| Leapster 2 BIOSes | 0.6 (`152-12206`), CIP3 m9 (`152-12659`), Connected B5 (`152-12076`), all 8 MiB; the user has all three (SHA-1 match MAME) | VERIFIED |
| Leapster 2 RAM | 16 MiB at `0x3C00_0000-0x3CFF_FFFF` (BIOS RAM test up to `0x3D00_0000`) | VERIFIED-FW/EMU |
| Boot selector | `0x0180_B008` bits 1-2: `00` system menu, `01` cartridge, `10` **SD developer load**, `11` USB. Bits survive a restart | VERIFIED-FW/EMU |
| SD host controller | `0x0180_E400-E408` plus descriptor format, card detect at `0x0180_00EC` bit 6, CMD0/8/55/41/2/3/17/24 | VERIFIED-FW/EMU (`io/sd.rs`) |
| SD volume | FAT, **no partition table** (boot sector at sector 0). B5 formats a card that lacks `b:\Leapster` as FAT32, label `Leapster SD`, serial `0x1BAD_CAFE` | VERIFIED-FW/EMU (`io/fat.rs`) |
| CIP3 storage | 1 Gbit NAND at `0xE000_0000` with a flash file system under FAT; no SD driver | VERIFIED-FW/EMU (`io/nand.rs`) |
| SPI flash | Internal SPI flash on GPIO, holds touch calibration at `0x1000` (B5: `0x0000`) | VERIFIED-FW/EMU |
| USB | Device controller at `0x0180_F000`, driver `UsbMPI`, 8 KiB on-chip RAM at `0x0400_0000`; not modelled | VERIFIED-FW (existence only) |
| Cartridge compatibility | Original-Leapster and L-MAX cartridges run on the emulated Leapster 2 (first screens) | VERIFIED-EMU (not hardware) |

Correction for Ribbit: `roms/bios/leapster2_1004/1006/1008.bin` are **original-Leapster** UK v2.1, German
v2.1 (bad dump) and Spanish v1.0 BIOSes. Their SHA-1s match MAME's `leapster` set, and MAME uses those odd
file names. They are not Leapster 2 BIOSes.

## 2. Findings that apply specifically to the Leapster 2

Everything in §1 marked Leapster 2 above, plus these results from this report's analysis (BIOS 0.6
unless stated; disassembled with Ribbit's `disasm` example):

### 2.1 Content headers ("RIB" stores): VERIFIED-FW

The BIOS's "System RIB Mgr" looks for content at five fixed header addresses (table at `0x4010_140C`):

| Slot | Header address | Content | Gate (`0x4005_2930`) |
|---|---|---|---|
| 1 | `0x4000_0100` | BIOS | header check |
| 2 | `0x8000_0100` | cartridge | cartridge present (straps bit 26), then header check |
| 3 | `0xC000_0100` | unknown | `0x0180_1018` bit 2, then header check |
| 4 | `0xE000_0100` | NAND / external | header check |
| 5 | **`0x3C80_0100`** | **SD image copied to RAM** | **none: returns "valid" at once** (`0x4005_2994`) |

Header layout (BIOS, SpongeBob and Schoolhouse Rock all agree):

```
+0x00  "Copyright LeapFrog" padded with spaces/NUL to 0x18
+0x18  u32 0x00010100        byte +0x19 must be 1
+0x1C  u32 base address      0x8000_0000 on cartridges, 0x4000_0000 on the BIOS
+0x20  u32 end address
+0x24  u32 (pointer)
+0x28  u32 pointer to the checksum word
```

The header check (`0x4005_28A4`): 18-byte signature match, version byte = 1. Then, **unless straps bit 21
is set**, it sums one word every `0xF94` bytes from base to end and compares the sum with the checksum word.
This is a simple checksum, **not a signature or cryptographic authentication**. Slot 5 skips the check
entirely.

**Checksum verified on real dumps (2026-10-24):** the sum of the 32-bit words at `base, base+0xF94, …` while
the address is ≤ `end`, modulo 2³², equals the stored word in all five images tested: SpongeBob, Schoolhouse
Rock, and the BIOSes 0.6, B5 and m9. In every one the checksum word sits at `end+4`, and `+0x24` points to
`end+8`. LeapLoader can therefore check a dump's integrity independently of MAME's hash list, and rebuild the
checksum after relocation.

The `"LEAP"` resource directory has **two layouts**: at file offset 0 (SpongeBob, 2003) or reached through a
pointer at `+0x140` (`0x144`) after the RIB header (Schoolhouse Rock, the BIOS). Ribbit's parser
handles only the first. LeapLoader's analyser must handle both.

### 2.2 The SD-to-RAM boot path: VERIFIED-FW

1. **Selecting it.** The menu's launch native (`0x4005_3498`) compares its argument with `"BaseROM"`,
   `"TheCartridge"`, `"ExtStorage"` and `"USBConnect"`. For `"ExtStorage"` it writes
   `(B008 & ~6) | 4` and restarts (`0x4005_3532`), with no precondition.
2. **At boot** (`0x4004_0844`), `0x4005_35D4` decodes B008. Value 4 jumps (table `0x4004_0858`) to
   `0x4004_087C`, which calls **`CopyGameFromSdFatToRam`** (`0x4004_0260`):
   * initialises the SD card ("SD Card Inserted with %d sectors"), FAT (`Fat32SubInit`), and picks the
     non-volatile FAT volume resource (type `0x1005_0008`, "volatile=0");
   * builds a "fixed filename" for **`PlayGame.lnk`** through the package-path code (`0x400D_E2E4`, the same
     code that handles `meta.inf` packages: System/Application/CCLImage/CartLTM). **The exact directory is
     computed at run time and still UNKNOWN**;
   * reads up to **260 bytes** from it, cuts trailing CR/LF/space/tab: this is the **game path**;
   * opens that path (`"rb"`) and copies it in 512-byte blocks to **`0x3C80_0000` with no size limit**;
   * logs "File '%s' successfully read %d bytes" and "CopyGameFromSdFatToRam succeeded" (or "failed!!!").
3. On success the boot code registers a new content store (`0x4004_08A2-0x4004_0908`) and runs the usual
   start-up scan again (`0x4004_04F0`), now including slot 5.
4. Related names: boot tasks `BT_StartSDMenu` / `SD_CheckSDMenu`, default image **`SDMenu\SDMenu.bin`**
   (`LC_Boot.cpp`: "controlFile %s", "gamepath %s", "got SDMenu name"), `"iLoadFromSD"` inside the menu's Flash
   movies, and "BaseROMApp: Trap door activated" / "TrapDoor Movie" / "Cartridge/Promjet Movie" (PromJet is a
   ROM-emulator development tool).
5. **Present on all three Leapster 2 BIOSes:** the same strings plus `0x3C80_0000` copy targets (B5
   `0x4003_FAB2`, m9 `0x4004_03F4`) and the slot-5 entry (B5 `0x400F_E2E0`, m9 `0x4010_4FF4`). The slot-5
   "no check" jump was read on 0.6 only. **Absent from** original-Leapster US v2.1 and L-MAX v2.2.

### 2.3 Limits implied by the code: HYPOTHESIS where noted

* **Size:** RAM ends at `0x3D00_0000`, so an image may be at most **8 MiB** (`0x80_0000`). The copy has no
  bound check, so a larger file would run past the end of RAM (behaviour UNKNOWN). BIOS state lives just below
  `0x3C80_0000` (e.g. `0x3C7F_ACBC`, `0x3C7F_D354`), which suggests the top 8 MiB is reserved for this
  (HYPOTHESIS). That rules out the 8 MAME-listed 16 MiB cartridges.
* **Addresses:** content is found through absolute pointers in the header and the `LEAP` directory. A
  cartridge dump's pointers aim at `0x8000_xxxx`. Unless the RIB manager relocates (no sign that it does,
  UNKNOWN), an SD image must be **built or relocated for base `0x3C80_0000`**.
* **Native code:** titles with their own ARC code (Sonic X) have absolute addresses inside the code.
  Relocating them safely without relocation records is not realistic. Flash-only titles are the plausible
  first targets (HYPOTHESIS).
* **Saves:** cartridge saves live in the cartridge's I²C EEPROM. An SD-loaded game has none, and what the
  BIOS does then is UNKNOWN.

## 3. What is known about loading games onto real hardware

* **Normal path:** cartridge only. The BIOS maps it at `0x8000_0000`, checks the header checksum (slot 2) and
  starts its Flash content. VERIFIED-EMU.
* **LeapFrog Connect downloads:** the Leapster 2 stores downloaded content and logs on its SD card or NAND
  (package/`meta.inf` code, `profile.log`). SOURCED (Wikipedia) and VERIFIED-FW (code exists). How
  downloaded content is launched, and in what format, is UNKNOWN.
* **SD developer load:** §2.2. Present in firmware. **Never observed running**, in Ribbit or on hardware.
* **No public Leapster 2 homebrew, flash cartridge or SD loader found.** Searches found only the
  LeapsterGS Linux port (different hardware) and general flash-cart articles.

## 4. Can the Leapster 2 access an SD card?

* **0.6 and B5 units: yes.** A full-size SD slot (SOURCED: MAME "USB 1.1 (client only) + full-sized SD slot";
  Wikipedia), a working SD driver (VERIFIED-FW/EMU), and a card fitted at the factory. The base system
  refuses to start without one: "SD Card Error: Not Inserted. Please call Customer Service" (VERIFIED-EMU).
  It reads a FAT volume with **no partition table**.
* **CIP3 (m9) units: no SD driver**, internal NAND instead (VERIFIED-FW). Only a PC talking LeapFrog's USB
  protocol could write that storage.
* **Physical access:** one eBay seller's listing (SOURCED, unverified) says SD units have serial numbers
  ending **"BG"** and internal-memory units **"AG"**, that the slot is **inside the battery compartment**,
  and that replacement cards must be **non-SDHC**. The SDHC limit fits the 1 GiB card Ribbit modelled, but the
  B5 driver does send CMD8 and set HCS (HYPOTHESIS: SDHC addressing may still be wrong). To be checked on the
  user's unit.

## 5. Can the stock firmware launch games stored on SD?

**The mechanism exists, but it is not proven.** Confirmed: switching to the path, the copy to RAM and
registering the store (VERIFIED-FW). Unknown:

1. How a retail unit reaches `launch("ExtStorage")`: a menu path, a hidden trap door, `iLoadFromSD`, or
   only from a cartridge's or developer tool's own Flash.
2. The directory `PlayGame.lnk` must be in (resolved at run time).
3. Whether the image must be a complete RIB store with base `0x3C80_0000`, what else the scan needs, and
   what gets launched (its main movie? `SDMenu`?).
4. Whether B008 bit 2 stays set after an SD boot (a loop risk) and how the console returns to normal.

Every item can be settled in Ribbit (emulated SD card plus UART log) before risking real hardware.

## 6. What additional hardware or software might be needed

| Unit | Likely needs | Status |
|---|---|---|
| 0.6/B5 (SD slot) | A non-SDHC SD card (≤ 2 GB) formatted FAT without a partition table, LeapLoader's prepared image plus `PlayGame.lnk`, and **a way to trigger "ExtStorage"** | HYPOTHESIS until §5 is answered |
| 0.6/B5, no stock trigger | A small **trigger cartridge** (custom PCB with flash and an EEPROM) whose Flash movie calls the launch native, or whatever trap door the BIOS checks | HYPOTHESIS. The cartridge bus is simple parallel ROM, so a custom cart is feasible but none exists |
| CIP3 (m9) | Reverse engineering the USB protocol (not modelled), or a hardware change. **Not a target for the first release** | UNKNOWN |
| Any unit, a different approach | A true SD flash cartridge (an MCU or CPLD serving the 16-bit ROM bus from SD-loaded SRAM/flash, plus EEPROM emulation). Works for every title and every board, but is a hardware project | Feasible on paper; does not exist |

Firmware modification is **not** required for the SD path, and nothing here needs reflashing the BIOS.

## 7. Most realistic implementation strategy

1. **Phase 2a, in Ribbit (no hardware risk).** Put a `PlayGame.lnk` on Ribbit's virtual SD card (or log its
   resolved path with `logtrace`), force B008 = 4, and read the UART log. Find out the control-file path,
   what the scan accepts at `0x3C80_0100`, and what starts. First try a **Flash-only 4 MiB title relocated to
   base `0x3C80_0000`**, then a raw dump as the expected-failure control.
2. **Phase 2b, find the trigger.** Trace callers of the launch native with `"ExtStorage"`, the trap-door
   movie conditions and `iLoadFromSD` in the menu SWFs.
3. **Phase 2c, real hardware.** On a BG/SD unit: back up the factory card **sector by sector first**, then
   copy the files and follow the trigger.
4. **Only then** build LeapLoader's "Prepare" step as a *verified* relocator/packager with a compatibility
   verdict per title (Flash-only, ≤ 8 MiB, relocation proven), and the SD-card writer for that layout.
5. If no software trigger exists, the fallback is the **trigger cartridge** (Approach B hardware). If the SD
   path proves unusable, fall back to Approach C: LeapLoader prepares images for a custom flash cartridge.

LeapLoader's host-side pieces don't depend on the outcome and can safely be built early: import, analysis
(both `LEAP` layouts, RIB header, checksum verification, MAME matching), duplicate detection, and safe
removable-drive handling.

## 8. Outstanding questions and experiments

| # | Question | Experiment |
|---|---|---|
| E1 | Directory of `PlayGame.lnk` | Ribbit: `logtrace` on "fixed filename='%s'" with B008 = 4 |
| E2 | What the scan needs from a slot-5 store; is a raw dump rejected? | Ribbit: load raw and relocated images; UART log; break at `0x4004_04F0` |
| E3 | Retail trigger for `"ExtStorage"` | Disassembly: callers of `0x4005_3498`; SWF ActionScript for `iLoadFromSD` / trap door |
| E4 | Does B008 = 4 persist (boot loop)? How to exit? | Ribbit restart model; then hardware |
| E5 | Native-code titles: which cartridges contain ARC code? | Scan dumps for code outside SWF/data regions |
| E6 | Size limit beyond 8 MiB | Code reading of the RAM allocator; Ribbit |
| E7 | Saves for SD-loaded games | Ribbit: watch EEPROM accesses with no cartridge |
| E8 | User's unit: BIOS version, serial suffix, slot location, card size and type | Physical inspection; read the factory card's image on a PC |
| E9 | SDHC support | Real hardware with SD and SDHC cards |
| E10 | ~~Header checksum algorithm~~ **Resolved:** matches on 2 cartridges and 3 BIOSes (§2.1). Still to do: run it on every cartridge dump the user has | LeapLoader's analyser |

## Sources

* Ribbit repository and its BIOS dumps (local; not redistributed).
* MAME `src/mame/leapfrog/leapster.cpp`, `hash/leapster.xml` (BSD-3-Clause / CC0).
* [Wikipedia: Leapster](https://en.wikipedia.org/wiki/Leapster) (Leapster 2 SD slot; later units use onboard memory).
* [eBay listing note on Leapster 2 SD vs internal-memory units](https://www.ebay.co.uk/p/132041799) (single seller, unverified).
* [Hackaday: Linux on a LeapsterGS](https://hackaday.com/2013/11/08/linux-on-a-leapster-for-classic-video-game-emulation/) (different hardware; excluded).
