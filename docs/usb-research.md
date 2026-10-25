# Leapster 2 USB: BIOS research for Ribbit's USB emulation (2026-10-25)

For the Ribbit session that emulates the Leapster 2's USB device (LeapLoader's desktop app will
talk to the emulated console through Ribbit's USB/IP server). BIOS 0.6 (`152-12206_0.6.bin`,
CRC fa94d9a7). Labels: VERIFIED-EMU (seen in an emulator trace), VERIFIED-FW (read in the BIOS
code), HYPOTHESIS (my reading, not checked).

How the traces were made: LeapLoader's harness `research/sdboot-emu` has `--usb-attached` and a
script command `usb-attach`. Both take Ribbit's USB stub out (`m.io.usb = None`, again after every
console restart), so every access to 0x0180_F000-0x0180_F3FF is unmapped, reads 0 and is listed at
the end of the run. The bus does not record the PC of unmapped accesses (it prints 00000000), so
PCs below come from the disassembly. Script used: `D:\leaploader-tmp\usbre\b.txt` (load the
home-screen state, `usb-attach`, run 30 s); log `D:\leaploader-tmp\usbre\b.log`.

## 0. The controller is a Freescale/NXP "USB OTG FS" core (HYPOTHESIS, strong)

Every register the BIOS touches and every value it writes fits the full-speed USB OTG controller
Freescale used in ColdFire (MCF5222x/MCF5225x) and Kinetis chips ("USBOTG", publicly documented in
those reference manuals), at base 0x0180_F000 with 4-byte register spacing:

| Address | Kinetis name | BIOS use (sections 2-4, 9) |
|---|---|---|
| F000 | PERID | byte read at init |
| F004 | IDCOMP | byte read at init |
| F008 / F00C | REV / ADDINFO | not seen |
| F010 | OTGISTAT (w1c) | cleared with 0xFF at init; the handler acks it |
| F014 | OTGICR | 0, then 0x8D (bits 7, 3, 2, 0: on Kinetis IDEN, LINESTATEEN, SESSVLDEN, AVBUSEN; check the manual) |
| F018 | OTGSTAT | bit 2 tested by the attach check (B_SESS / VBUS-valid style bit; 0 = attached here) |
| F01C | OTGCTL | 0x34 at init, 0x30, 0, then 1 / 0 / 2 pulses (DP/DM pull-ups: DPHIGH 0x80, DPLOW 0x20, DMLOW 0x10, OTGEN 0x04) |
| F080 | ISTAT (w1c) | USBRST 0x01, ERROR 0x02, SOFTOK 0x04, TOKDNE 0x08, SLEEP 0x10, RESUME 0x20, ATTACH 0x40, STALL 0x80 |
| F084 | INTEN | 0x40 (ATTACH) in the core init; **0x9F** after a bus reset (STALL, SLEEP, TOKDNE, SOFTOK, ERROR, USBRST) |
| F088 / F08C | ERRSTAT / ERREN | |
| F090 | STAT | which endpoint/direction/odd bank the finished token was (read after TOKDNE) |
| F094 | CTL | 3 (USBENSOFEN + ODDRST) during the reset, then 1 (USBENSOFEN); 0x0B in 0x400C_3CFE (HOSTMODEEN 0x08: the OTG host path?) |
| F098 | ADDR | 0 on reset; the SET_ADDRESS value later |
| F09C / F0B0 / F0B4 | BDTPAGE1-3 | base of the Buffer Descriptor Table (512-byte aligned: the 512-aligned allocation in 0x400C_54CE) |
| F0A0 / F0A4 | FRMNUML/H | |
| F0A8 | TOKEN | (host mode) |
| F0AC | SOFTHLD | 0x4A written in the core init |
| F0C0 + 4n | ENDPTn | endpoint control (EPHSHK, EPTXEN, EPRXEN, EPCTLDIS, EPSTALL) |
| F100.. | USBCTRL, OBSERVE, CONTROL, USBTRC0 | not seen yet |

**Bus reset handler 0x400C_6086** (VERIFIED-FW; r15 = core base F080): ISTAT = 8 four times (pops
the 4-deep STAT/TOKDNE FIFO, the documented way), ISTAT = 0xFF, ADDR = 0, CTL = 3, clears the
software endpoint records, writes EP0's buffer descriptors (`0x0040_0080` = byte count 64 << 16
| OWN 0x80) for both banks, CTL = 1, INTEN = 0x9F.

**Buffer descriptors** (VERIFIED-FW 0x400C_5FA4 / 0x400C_5E74; Kinetis format): the table at
[ctx+0x10]: 32 bytes per endpoint, 16 per direction (RX 0, TX 1), 8 per odd/even bank: word 0 =
control (OWN 0x80, DATA1 0x40, DTS 0x08, byte count in bits 16-25; the controller writes the PID
into bits 2-5 when it gives the BD back), word 1 = buffer address. 0x400C_5FA4(ctx, dir, ep) sets
0x40 or 0x42 (DATA1, + 2 = ?) | OWN and calls 0x400C_5E74(bd address, ep record) to fill it.

So Ribbit can model it after the public Kinetis description: the host side (USB/IP) puts a SETUP
or OUT packet into the RX BD the BIOS armed (clear OWN, set PID and count, DMA the bytes into
RAM), pushes STAT and raises ISTAT.TOKDNE; for IN it takes the bytes from the TX BD the BIOS armed.

## 1. Two register blocks

| Block | Base | Who uses it |
|---|---|---|
| "Glue" (Ribbit's io/usb.rs today) | 0x0180_F000 | init 0x400C_03F2, attach check 0x400B_CB0C, debug dump 0x400B_E4DE |
| Device core | **0x0180_F080** | init 0x400C_3CFE, endpoint setup 0x400C_54CE, handler 0x400C_04B0 |

* `0x400C_67DC(n)` returns 0x0180_F080 for controller n = 0, else 0 (VERIFIED-FW). Every
  driver path takes the base from it: glue = base - 0x70 (0x0180_F010), base - 0x80 (0x0180_F000).
* `0x400C_67BC(n)` returns 15 for n = 0, else 0 (VERIFIED-FW): HYPOTHESIS, the interrupt number,
  passed with the handler to `0x400B_EC24(irq, handler, ctx)` -> `0x400F_1DA0` (OS attach).
* The interrupt controller is at 0x017F_FFA0 (+0xE0, +0xE4 written in 0x400B_EC50/EC60; 0x0180_0064
  read): HYPOTHESIS, enable/ack. Ribbit's intc model should already know which line 15 is.

## 2. Glue block 0x0180_F000-0x0180_F01C: the sequence (VERIFIED-EMU, all reads returned 0)

Init (0x400C_03F2, VERIFIED-FW for the code):
```
W F014 = 0x00        ; disable
W F010 = 0xFF        ; clear all pending (write-1-to-clear: the handler writes back what it read)
W F01C = 0x34
  (handler 0x400C_04B0 registered on irq 15)
R F018 -> bit 7 decides a flag at [ctx+8]+0x94 (1 if bit 7 clear)
W F014 = 0x8D        ; enable: bits 0, 2, 3, 7
```
Then (trace order): `R F018, R F01C, W F01C=0x30, R F01C, W F01C=0x00, R F018, R F014, W F014=0,
R F000 (byte), R F004 (byte), R F01C, W F01C=1, R F01C, W F01C=0, R F018 (byte, the attach check),
R F01C, W F01C=2`. After that nothing more in 30 s: the BIOS waits for an interrupt.

* Attach check 0x400B_CB0C: returns `(F018 >> 2 & 1) ^ 1`: **F018 bit 2 = 0 means a host is
  attached** (Ribbit's stub reads bit 2 = 1 = no cable).
* F01C bits 0-1 pulsed 1, 0, then 2 around the attach check: HYPOTHESIS, the D+ pull-up / soft
  connect (the device "appears" on the bus when the BIOS sets it).
* F000/F004 byte reads: meaning unknown (chip id/revision?).

## 3. The interrupt handler 0x400C_04B0 (VERIFIED-FW code; meanings HYPOTHESIS)

ctx = {[0] glue+0x10 = 0x0180_F010, [4] core = 0x0180_F080, [8] driver state}.
```
r3  = [F010]            ; glue status
r13 = [F014] & r3       ; enabled and pending
[F010] = r13            ; acknowledge (write 1 to clear)
bit 6 -> 0x400C_0234    ; then events through 0x400B_F430 (post to UsbTask)
...
r2 = [F080]             ; core status, bit 6 tested several times (-> 0x400B_F430, 0x400C_3A70)
bit 0 of [F080]:
  r13 = [F080] & [F084] ; core status & core enable
  [F080] = r13          ; acknowledge
  -> 0x400C_5648        ; HYPOTHESIS: endpoint / transfer service
then [F010] & [F014] again (loop while pending)
```
So the core block mirrors the glue: **F080 = status (write 1 to clear), F084 = enable**.

## 4. Device core init 0x400C_3CFE (VERIFIED-FW; runs when the attach goes further)

```
W F0C0 = 0        ; base + 0x40
W F094 = 0
W F084 = 0        ; core interrupt enable off
W F080 = 0xFF     ; clear core status
W F098 = 0
  (0x400C_37B8: more setup)
W F094 = r17      ; (a value computed before)
W F0AC = 0x4A
W F084 = 0x40     ; enable core bit 6
W F094 = 0x0B
```
Endpoint setup 0x400C_54CE: `[obj] = F080, [obj+4] = F0C0`; buffers of 512 bytes allocated with
`0x400B_EA20(size, 512)` and aligned (`(-p & 0x1FF) + p`): HYPOTHESIS, F0C0.. is the per-endpoint
register area (F0C0 + 0x20 x n?), buffers in RAM (or the 8 KiB at 0x0400_0000), addresses written
there. Not traced yet: this path did not run because nothing raised the interrupt.

## 5. Strings and entry points (VERIFIED-FW addresses)

| What | Address |
|---|---|
| `[UsbDvrInit]` | used at 0x400B_E460 |
| `---Fly Usb OTG Service--` (the USB core is "Fly"? an OTG controller) | 0x400B_E214 |
| `[[[ RESET EP0 ]]]` | 0x400B_D9A2 |
| `[[[ SERVICE SUSPEND ]]]` | 0x400B_DA6E |
| `[[[ CH 9 SET DESCRIPTOR ]]]` (chapter 9 = standard requests) | 0x400B_D2F8 |
| `endpointBuffDescTbl Addresses:` (debug dump of the endpoint buffer table) | 0x400E_4A9C |
| `USB: Attach Event iuc=%d`, `USB: Detached`, `USB: Suspend Event`, `USB: SOF` | UsbTask, 0x4013_3B9C.. |
| `ConnectDoUsbAttached(%d)` | 0x400D_9EA8 |
| `USB Attach Reboot.` (boot select 11) | 0x4004_0972 |
| `UsbMPI: can't find device info rsrc` (kUsbRsrcDeviceInfoDescriptor) | 0x400B_9B54 |

The driver keeps its state around 0x3C7F_AE00-0x3C7F_AF04 (0x3C7F_AE7C and 0x3C7F_AE1C used most;
0x3C7F_AF04 = "in interrupt" flag set by the handler).

## 6. What the PC should see (VERIFIED-FW data)

Mass storage with two removable LUNs. INQUIRY data (36 bytes each):
* 0x4014_EC58: `00 80 00 01 1F 00 00 00 "LeapFrog" "Leapster 2-RAM  1.00"` (copies of the internal
  flash archives: `ConnectCopyCffsArchivesToRamDisk`).
* 0x4014_EC7C: `00 80 00 01 1F 00 00 00 "LeapFrog" "Leapster 2-SD   1.00"`.
Neither address is referenced as a 32-bit constant: the SCSI code builds the pointer (table or
base + offset). Vendor CDBs (LFTools, facts only): `C2` mount, `C1` lock, `C6` eject; their
handler is not found yet.

## 7. USB descriptors (VERIFIED-FW data)

Two sets, both VID 0x0F63 (LeapFrog), 64-byte EP0, one configuration of 32 bytes: one interface,
class 08 (mass storage), subclass 06 (SCSI transparent), protocol 0x50 (Bulk-Only), EP 0x81 bulk
IN and EP 0x01 bulk OUT, self-powered (0xC0), bMaxPower 0.

| Set | Device descriptor | Notes |
|---|---|---|
| A, 0x4014_D2C4 | `12 01 10 01 00 00 00 40 63 0F 00 11 01 00 01 02 03 01`: USB 1.1, PID 0x1100, bcdDevice 0x0001 | strings at 0x4014_D2F8: LANGID 0x0409, "LeapFrog ", "Leapster 2", "BAD STRING Index". Pointer table at 0x4014_D354 {device, config, 0, 0x3C7F_C25C, ...}: HYPOTHESIS, the boot/USB-attach-reboot driver |
| B, 0x4014_EB48 | `12 01 00 02 00 00 00 40 63 0F 00 08 02 00 01 02 00 01`: USB 2.0, PID 0x0800, bcdDevice 0x0002, no serial string | then a device qualifier (`0A 06 00 02 ...`), the full-speed config (bulk 64), an other-speed config (`09 07`, bulk 512): high-speed capable. Strings: "LeapFrog Enterprises Inc.", "Leapster 2", "BETA", "Your name here", "BAD STRING Index". The INQUIRY data follows right after (0x4014_EC58): **set B is the mass-storage one** (HYPOTHESIS, as the usage is not traced) |

Neither set B address is a code constant (the driver takes base + offset).

## 8. Bulk-Only transport and the SCSI dispatch (VERIFIED-FW code)

* **CBW handler 0x400B_C4A4:** a 31-byte OUT packet whose first word is 0x43425355 ("USBC") is a
  command: CSW signature "USBS" (0x53425355) written to 0x3C7F_CC1C (= 0x3C7F_CC00 + 0x1C), the
  tag copied to 0x3C7F_CC20, then **0x400B_C28C(ctx, ?, cbw)** dispatches. The CSW (13 bytes from
  0x3C7F_CC1C) goes out through 0x400C_50C8(ctx, 1, buf, 13); the next CBW is armed with
  0x400C_4F8C(ctx, 1, buf, 31). Driver state struct at 0x3C7F_AE1C (+0x30 = data phase pending,
  +0x34 = buffer).
* **Dispatch 0x400B_C28C** on CDB[0] (CBW byte 15). Opcodes not listed (incl. 0x55, 0x5A) go to
  0x400B_B884 (the same function as MODE SENSE(6); HYPOTHESIS, it also builds "not supported"):

| Opcode | Command | Handler |
|---|---|---|
| 0x00 | TEST UNIT READY | 0x400B_C128 |
| 0x03 | REQUEST SENSE | 0x400B_C8EC |
| 0x12 | INQUIRY | 0x400B_B7E0 |
| 0x1A | MODE SENSE(6) | 0x400B_B884 |
| 0x1B | START STOP UNIT | 0x400B_BC04 |
| 0x1E | PREVENT ALLOW MEDIUM REMOVAL | 0x400B_C1E4 |
| 0x23 | READ FORMAT CAPACITIES | 0x400B_CA38 |
| 0x25 | READ CAPACITY(10) | 0x400B_B950 |
| 0x28 | READ(10) | 0x400B_BCA8 |
| 0x2A | WRITE(10) | 0x400B_BE98 |
| 0x2F | VERIFY(10) | 0x400B_C0D4 |
| 0xC0-0xCE | LeapFrog vendor commands | **0x400B_BA0C** |

* **Vendor handler 0x400B_BA0C:** LUN = CBW byte 13, per-LUN state at **0x3C7F_CC2C + LUN x 112**
  (+0x60 ready flag, +0x64 / +0x68 must both be non-zero for a mount, +0x6C state); jump table on
  CDB[0] - 0xC1 (0x400B_BA7C):

| CDB[0] | Handler | What it does (code read; names from LFTools / UsbTask strings: HYPOTHESIS) |
|---|---|---|
| **0xC1** "lock" | 0x400B_BA94 | LUN state (+0x6C) = 3 |
| **0xC2** "mount" | 0x400B_BA9C | if +0x68 and +0x64 are set: +0x60 = 1, state = 2 (else nothing) |
| 0xC3 | 0x400B_BAB2 | queries by CDB[1] (table 0x400B_BAC8): 1 = a 4-byte word from 0x0180_AFBC + 0x64 masked to 30 bits, 2 = 0x400B_EDA0 (1 byte), 3 = 0x400B_EB94 (a buffer and its length), 7 = 0x400B_EBD0 (1 byte); sent as data-in through 0x400C_50C8 |
| 0xC4 | 0x400B_BB72 | by CDB[1] (table 0x400B_BB88): 3 = store a value at 0x3C7F_AE48 and set 0x3C7F_AE44 = 1, 7 = 0x400B_BBBA (not read yet; probably "set serial number", UsbTask string) |
| 0xC5 | 0x400B_BB66 | posts UsbTask event 4 (0x400B_9A10(4)) |
| **0xC6** "eject" | 0x400B_BB6E | posts UsbTask event 5 (0x400B_9A10(5)): HYPOTHESIS, "Safe Detach IOCTL" |

Other UsbTask events seen in the CBW path: 7 and 8 (0x400B_C596 / 0x400B_C5B6, after copying up to
17 / 1 bytes from the command to 0x3C7F_BBC8). The task's strings: "Clear Logs IOCTL", "Safe Detach
IOCTL", "Set Serial Number ... Verified".

## 8b. EP0 control requests (VERIFIED-FW code)

* **SETUP handler 0x400B_B674:** the 8-byte setup packet is at 0x3C7F_AE1C + 0x50 (bmRequestType
  +0x50, bRequest +0x51, ...). Type bits (bmRequestType & 0x60): 0 = standard, jump table on
  bRequest 0-12 at 0x400B_B6EC; 0x20 = class -> 0x400B_B7A6; 0x40 = vendor -> 0x400B_B7B4.
* **Class requests 0x400B_B604:** bRequest **0xFE GET MAX LUN** answers one byte = **1**, i.e. two
  LUNs, 0 and 1 (byte written to the buffer at [0x3C7F_AE1C+0x34], sent with 0x400C_50C8(ctx, 0,
  buf, 1)); **0xFF Bulk-Only Mass Storage Reset** answers a zero-length status; anything else
  stalls (0x400C_5428).
* Data out of EP0: 0x400C_50C8(ctx, ep 0, buf, len) (len capped at wLength, e.g. GET_STATUS at
  0x400B_B5CA caps at 2), then the status stage is armed with 0x400C_4F8C(ctx, 0, 0, 0).
* LUN order (HYPOTHESIS until the INQUIRY handler is read): LUN 0 = "Leapster 2-RAM", LUN 1 =
  "Leapster 2-SD" (the order of the two INQUIRY blocks).

## 8c. Per-LUN behaviour (VERIFIED-FW code)

Per-LUN record at 0x3C7F_CC2C + LUN x 112: +0x04 sector size, +0x08 **media driver ops table**
(+0x10 = read function), +0x0C LBA, +0x10 block count, +0x14 / +0x18 transfer bookkeeping, +0x44 /
+0x48 chunk sizes, **+0x60 ready (set only by C2 "mount")**, +0x64 / +0x68 must both be non-zero
for C2 to work (HYPOTHESIS: medium present and its size, set when the storage registers itself
for USB: `CFat32MPI::SetReadyForUsb`, the Cffs RAM disk), +0x6C state (2 mounted/busy, 3 after C1).

* **INQUIRY 0x400B_B7E0:** if the CBW asks for data in (flags bit 7) it sends 36 bytes from
  **0x3C7F_BBDC + LUN x 36** (a RAM copy of the INQUIRY blocks; HYPOTHESIS: copied from 0x4014_EC58,
  EC7C in that order, so LUN 0 = RAM disk, LUN 1 = SD), then sets the residue (0x3C7F_CC24 =
  length - 36) and status 0 (0x3C7F_CC28 = 0 means passed).
* **READ(10) 0x400B_BCA8:** if the LUN's +0x60 ready flag is 0, it sends 4 zero bytes and fails
  the command (0x3C7F_CC28 = 1). **So a host reads nothing until it has sent C2 (mount) for that
  LUN**, which fits LFTools' use of C2. When ready: state = 2, LBA from CDB[2-5] (0x400B_AE28,
  big-endian), count from CDB[7-8] (0x400B_AE5C), then reads through the ops table's +0x10 in
  chunks of [+0x48] and sends with 0x400C_50C8(ctx, 1, buf, n).
* Status/residue globals: 0x3C7F_CC28 = CSW status (0 passed, 1 failed), 0x3C7F_CC24 = residue;
  the CSW is assembled at 0x3C7F_CC1C.

For an emulated host that wants to see the SD card: GET MAX LUN (1), INQUIRY on LUN 0 and 1, then
the vendor CDB `C2` on LUN 1, then TEST UNIT READY / READ CAPACITY / READ(10). Whether C2 needs
anything in CDB[1..] is not read yet (the C2 handler only checks the LUN record).

## 9. Next steps (mine)

1. INQUIRY handler 0x400B_B7E0: confirm it picks 0x4014_EC58 / EC7C by LUN (GET MAX LUN = 1: done).
2. Who fills each LUN record (+0x08 ops, +0x64/+0x68): the FAT32 / Cffs code around
   `CFat32MPI::SetReadyForUsb` (string 0x4013_8DD4) and `ConnectDoUsbAttachedCopies`.
3. Trace further once Ribbit's model raises the controller's interrupts (I can't edit Ribbit).
