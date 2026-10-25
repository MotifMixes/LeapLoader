"""Prototype (research): a cartridge save chip for SD-booted games with native code.

Booted from SD there is no cartridge, so the BIOS's EEPROM device 1 (the cartridge's save
chip; device 0 is the console's own memory, emulated in flash) gets no answer: every read
fails, and games show leftover RAM where their saved names should be (I-Spy, Pet Pals,
Animal Genius: VERIFIED-EMU). Native code reaches the chip directly through the BIOS EEPROM
interface, so the ActionScript save shim (saveshim.py) cannot catch it.

This stub replaces that interface. BIOS 0.6 keeps a pointer to the EEPROM function table at
[[gp+4] + 0x88] in RAM (0x3C00_01D4 -> 0x4013_3420, VERIFIED-EMU); the table holds
  +0x00 write with checksum (data, then ~sum at addr+len)     0x400B_8268
  +0x04 read with checksum (returns 0 if the sum is wrong)    0x400B_8158
  +0x08 write(dev, addr, len, buf) -> 1 ok / 0                0x400B_8454
  +0x0C read(dev, addr, len, buf) -> 1 ok / 0                 0x400B_837C
  +0x10 size(dev), +0x14 manufacturing mode
The stub's native __llEE() installs a copy of the table whose four data functions serve
devices 1-3 from a RAM buffer (erased, 0xFF) and pass device 0 to the BIOS. In BIOS 0.6's device
table ([0x3C7F_ADF0], 12 bytes per device) only device 0 is marked 0xFF (emulated in flash: the
console's own memory); the others have chip id 0, which the I2C routine (0x400B_7840) turns into
chip 0x20, the cartridge's (VERIFIED-EMU: Princess games use a computed device number). Each call
returns the range changed since the previous call as lo * 65536 + (hi + 1), or 0 if none, so
ActionScript can save it to the card (saveshim.build_ee_loader). The chip's size is the
game's 0x1005/3 descriptor's (+0x14: 0x100, 0x200 or 0x800 bytes); addresses wrap at it.

The returned number also has KEYS_FLAG (2^29) added while HINT + A + B are all held, read from the
BIOS's ButtonMPI ([[gp+4] + 0x7C], GetButtonState at +4, as nativechip.py): some games take the
button events for themselves and the ActionScript listener of the HINT + A + B watcher never hears
them (Cars, VERIFIED-EMU), so the flusher passes this on to the watcher (saveshim, ingame). (A
second native of its own was never found by the player, in a resource of its own or not.)
"""
import os
import subprocess
import tempfile

TOOLS = os.environ.get("ARC_GNU", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Ribbit", "tools", "arc-gnu"))
NATIVE_NAME = "__llEE"
KEYS_FLAG = 1 << 29
# ButtonMPI GetButtonState word 0 = pressed buttons: A, B, HINT (as nativechip.COMBO)
COMBO = 0x4000 | 0x2000 | 0x1000_0000
QUIET = 10  # calls (one a frame) without changes before the save file is written
SYSTEM_DEVICE = 0  # the console's own memory (flash-emulated); every other device is the cartridge chip

SOURCE = r"""
    .cpu    arc600
    .equ    FOPEN, 0x400F0830
    .equ    FREAD, 0x400F0890
    .equ    FWRITE, 0x400F09C8
    .equ    FCLOSE, 0x400F06A0
    .equ    DTOI, 0x400EF75C
    .text
    .global _start
_start:

; ---- 0x1009 resource: {0x100, 0, count << 16, pairs}, then the (name, function) pair
blob:
    .word   0x100, 0, 0x00010000, pairs
pairs:
    .word   name, llee
name:
    .asciz  "__llEE"
    .align  4

; ---- native __llEE(ctx, command): install once (and read the save file); write the save file
; after QUIET calls without changes, or at once when command is 1; return KEYS_FLAG while
; HINT + A + B are held, else 0
llee:
    push_s  blink
    push_s  r13
    push_s  r14
    push_s  r15
    mov_s   r13, r0
    mov     r0, 0
    bl      arg_int
    mov     r15, r0
    ld      r1, [gp, 4]
    ld      r2, [r1, 0x88]
    mov     r3, fake_table
    breq    r2, r3, 1f
    mov     r5, orig_table
    st      r2, [r5]
    ld      r4, [r2, 0x10]
    st      r4, [r3, 0x10]
    ld      r4, [r2, 0x14]
    st      r4, [r3, 0x14]
    mov     r4, fk_wchk
    st      r4, [r3, 0]
    mov     r4, fk_rchk
    st      r4, [r3, 4]
    mov     r4, fk_write
    st      r4, [r3, 8]
    mov     r4, fk_read
    st      r4, [r3, 12]
    st      r3, [r1, 0x88]
    ; the save file, once (a game that puts its own table back gets ours again, not the file)
    mov     r5, loaded
    ld      r4, [r5]
    brne    r4, 0, 1f
    mov     r4, 1
    st      r4, [r5]
    bl      load
1:
    ; changes since the last call: something to write, quiet calls counted from 0
    mov     r5, dirty_lo
    ld      r6, [r5]
    ld      r7, [r5, 4]
    mov     r4, pending
    brhi    r6, r7, 4f
    mov     r6, 0xffff
    st      r6, [r5]
    mov     r6, 0
    st      r6, [r5, 4]
    mov     r6, 1
    st      r6, [r4]
    mov     r6, 0
    st      r6, [r4, 4]
    b       5f
4:
    ld      r6, [r4, 4]
    add     r6, r6, 1
    st      r6, [r4, 4]
5:
    ld      r6, [r4]
    breq    r6, 0, 6f
    ld      r6, [r4, 4]
    brhs    r6, QUIET, 7f
    brne    r15, 1, 6f
7:
    mov     r6, 0
    st      r6, [r4]
    bl      persist
6:
    mov     r14, 0
    ; KEYS_FLAG while HINT + A + B are held (ButtonMPI GetButtonState(buf): word 0 = pressed)
    sub     sp, sp, 16
    ld      r1, [gp, 4]
    ld      r1, [r1, 0x7c]
    ld      r1, [r1, 4]
    mov     r0, sp
    jl      [r1]
    ld      r2, [sp]
    add     sp, sp, 16
    and     r2, r2, COMBO
    cmp     r2, COMBO
    bne     13f
    or      r14, r14, KEYS_FLAG
13:
    ; the player's return-value interface: ([[gp+4]+0x64]+0x40)() -> object; vtable +0x1C(ctx, double)
    ld      r1, [gp, 4]
    ld      r1, [r1, 0x64]
    ld      r1, [r1, 0x40]
    jl      [r1]
    ld      r3, [r0, 0]
    ld      r3, [r3, 0x1c]
    ; r14 (0 <= n < 2^31) as a double in r1 (low word), r2 (high word)
    mov     r1, 0
    mov     r2, 0
    breq    r14, 0, 2f
    mov     r4, 31                  ; exponent: shift left until bit 31 is set
5:
    bbit1   r14, 31, 6f
    asl     r14, r14, 1
    sub     r4, r4, 1
    b       5b
6:
    asl     r14, r14, 1             ; drop the leading 1: 32 fraction bits
    add     r4, r4, 1023
    asl     r2, r4, 20
    lsr     r5, r14, 12
    or      r2, r2, r5
    asl     r1, r14, 20
2:
    mov_s   r0, r13
    jl      [r3]
    pop_s   r15
    pop_s   r14
    pop_s   r13
    pop_s   blink
    j_s     [blink]

    .align  4
; ---- argument r0 of the native whose context is r13, as an integer (as streamstub.py)
arg_int:
    st.aw   blink, [sp, -4]
    st.aw   r15, [sp, -4]
    mov     r15, r0
    ld      r1, [gp, 4]
    ld      r1, [r1, 0x64]
    ld      r1, [r1, 0x40]
    jl      [r1]
    ld      r3, [r0, 0]
    ld      r3, [r3, 8]
    mov     r0, r13
    mov     r1, r15
    jl      [r3]
    mov     r2, DTOI
    jl      [r2]
    ld.ab   r15, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

    .align  4
; ---- read the save file (hex, two characters a byte, as saveshim's AS loader read it) into the
; chip; a missing or short file leaves the rest erased
load:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    st.aw   r15, [sp, -4]
    sub     sp, sp, 64
    mov     r0, path
    mov     r1, mode_r
    mov     r2, FOPEN
    jl      [r2]
    mov     r13, r0
    breq    r13, 0, 9f
    mov     r14, mem
    mov     r15, mem + SIZE
1:
    mov     r0, sp
    mov     r1, 1
    mov     r2, 64
    mov     r3, r13
    mov     r4, FREAD
    jl      [r4]
    cmp     r0, 64
    bne     8f
    mov     r2, sp
    mov     r3, 32
2:
    ldb     r4, [r2]
    or      r4, r4, 0x20            ; ('0'-'9' keep their codes; 'A'-'F' -> 'a'-'f')
    sub     r4, r4, 48
    brls    r4, 9, 3f
    sub     r4, r4, 39
3:
    ldb     r5, [r2, 1]
    or      r5, r5, 0x20
    sub     r5, r5, 48
    brls    r5, 9, 4f
    sub     r5, r5, 39
4:
    asl     r4, r4, 4
    or      r4, r4, r5
    stb     r4, [r14]
    add     r14, r14, 1
    add     r2, r2, 2
    sub     r3, r3, 1
    brne    r3, 0, 2b
    brlo    r14, r15, 1b
8:
    mov     r0, r13
    mov     r1, FCLOSE
    jl      [r1]
9:
    add     sp, sp, 64
    ld.ab   r15, [sp, 4]
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

    .align  4
; ---- write the whole chip to the save file, as hex (64 characters at a time)
persist:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    st.aw   r15, [sp, -4]
    sub     sp, sp, 64
    mov     r0, path
    mov     r1, mode_w
    mov     r2, FOPEN
    jl      [r2]
    mov     r13, r0
    breq    r13, 0, 9f
    mov     r14, mem
    mov     r15, mem + SIZE
1:
    mov     r2, sp
    mov     r3, 32
    mov     r6, hexdig
2:
    ldb     r4, [r14]
    lsr     r5, r4, 4
    ldb     r5, [r6, r5]
    stb     r5, [r2]
    and     r4, r4, 15
    ldb     r4, [r6, r4]
    stb     r4, [r2, 1]
    add     r14, r14, 1
    add     r2, r2, 2
    sub     r3, r3, 1
    brne    r3, 0, 2b
    mov     r0, sp
    mov     r1, 64
    mov     r2, 1
    mov     r3, r13
    mov     r4, FWRITE
    jl      [r4]
    brlo    r14, r15, 1b
    mov     r0, r13
    mov     r1, FCLOSE
    jl      [r1]
9:
    add     sp, sp, 64
    ld.ab   r15, [sp, 4]
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

; ---- read(dev, addr, len, buf)
fk_read:
    breq    r0, SYSTEM_DEVICE, 9f
    breq    r2, 0, 8f
    mov     r6, mem
3:
    and     r4, r1, MASK
    ldb     r5, [r6, r4]
    stb     r5, [r3]
    add     r1, r1, 1
    add     r3, r3, 1
    sub     r2, r2, 1
    brne    r2, 0, 3b
    mov     r0, 1
    j_s     [blink]
8:
    mov     r0, 0
    j_s     [blink]
9:
    mov     r4, orig_table
    ld      r4, [r4]
    ld      r4, [r4, 12]
    j       [r4]

; ---- write(dev, addr, len, buf)
fk_write:
    breq    r0, SYSTEM_DEVICE, 9f
    breq    r2, 0, 8f
    and     r9, r1, MASK
    mov     r6, mem
3:
    and     r4, r1, MASK
    ldb     r5, [r3]
    add     r8, r6, r4
    stb     r5, [r8]
    add     r1, r1, 1
    add     r3, r3, 1
    sub     r2, r2, 1
    brne    r2, 0, 3b
    sub     r10, r1, 1
    and     r10, r10, MASK
    mov     r4, dirty_lo
    ld      r5, [r4]
    brls    r5, r9, 11f
    st      r9, [r4]
11:
    ld      r5, [r4, 4]
    brhs    r5, r10, 12f
    st      r10, [r4, 4]
12:
    mov     r0, 1
    j_s     [blink]
8:
    mov     r0, 0
    j_s     [blink]
9:
    mov     r4, orig_table
    ld      r4, [r4]
    ld      r4, [r4, 8]
    j       [r4]

; ---- read with checksum: len bytes, then ~(their sum) at addr+len; 1 if it matches
fk_rchk:
    breq    r0, SYSTEM_DEVICE, 9f
    breq    r2, 0, 8f
    mov     r6, mem
    mov     r7, 0
3:
    and     r4, r1, MASK
    ldb     r5, [r6, r4]
    stb     r5, [r3]
    add     r7, r7, r5
    add     r1, r1, 1
    add     r3, r3, 1
    sub     r2, r2, 1
    brne    r2, 0, 3b
    and     r4, r1, MASK
    ldb     r5, [r6, r4]
    not     r5, r5
    extb    r5, r5
    extb    r7, r7
    mov     r0, 0
    brne    r5, r7, 7f
    mov     r0, 1
7:
    j_s     [blink]
8:
    mov     r0, 0
    j_s     [blink]
9:
    mov     r4, orig_table
    ld      r4, [r4]
    ld      r4, [r4, 4]
    j       [r4]

; ---- write with checksum
fk_wchk:
    breq    r0, SYSTEM_DEVICE, 9f
    breq    r2, 0, 8f
    and     r9, r1, MASK
    mov     r6, mem
    mov     r7, 0
3:
    and     r4, r1, MASK
    ldb     r5, [r3]
    add     r8, r6, r4
    stb     r5, [r8]
    add     r7, r7, r5
    add     r1, r1, 1
    add     r3, r3, 1
    sub     r2, r2, 1
    brne    r2, 0, 3b
    and     r4, r1, MASK
    not     r7, r7
    add     r8, r6, r4
    stb     r7, [r8]
    mov     r10, r4                 ; the checksum byte is the last changed
    mov     r4, dirty_lo
    ld      r5, [r4]
    brls    r5, r9, 11f
    st      r9, [r4]
11:
    ld      r5, [r4, 4]
    brhs    r5, r10, 12f
    st      r10, [r4, 4]
12:
    mov     r0, 1
    j_s     [blink]
8:
    mov     r0, 0
    j_s     [blink]
9:
    mov     r4, orig_table
    ld      r4, [r4]
    ld      r4, [r4, 0]
    j       [r4]

    .align  4
orig_table:
    .word   0
dirty_lo:
    .word   0xffff                  ; changed range (lo > hi: none)
dirty_hi:
    .word   0
fake_table:
    .word   0, 0, 0, 0, 0, 0
loaded:
    .word   0                       ; the save file has been read
pending:
    .word   0                       ; changes not written yet
quiet:
    .word   0                       ; calls since the last change (pending + 4)
hexdig:
    .ascii  "0123456789abcdef"
path:
    .asciz  "PATH"
mode_r:
    .asciz  "rb"
mode_w:
    .asciz  "w"
    .align  4
mem:
    .fill   SIZE, 1, 0xff
"""


def build(address, size=256, path="b:\\save.dat"):
    """The stub assembled for `address` (a word-aligned RAM address in the SD image) with a
    `size`-byte chip kept in the file `path` (a BIOS path: b:\\Leapster\\Apps\\<game>\\save.dat)."""
    if size & (size - 1) or not 32 <= size <= 0x10000:
        raise ValueError("chip size must be a power of two")
    src = (SOURCE.replace("SYSTEM_DEVICE", str(SYSTEM_DEVICE)).replace("COMBO", str(COMBO))
           .replace("KEYS_FLAG", str(KEYS_FLAG)).replace("MASK", str(size - 1)).replace("SIZE", str(size))
           .replace("QUIET", str(QUIET)).replace("PATH", path.replace("\\", "\\\\")))
    exe = lambda n: os.path.join(TOOLS, f"arc-elf32-{n}.exe")
    with tempfile.TemporaryDirectory() as t:
        s, o, e, b = (os.path.join(t, n) for n in ("stub.s", "stub.o", "stub.elf", "stub.bin"))
        open(s, "w").write(src)
        for cmd in ([exe("as"), "-mcpu=arc600", "-o", o, s],
                    [exe("ld"), "-EL", "-Ttext", f"{address:#x}", "-e", "_start", "-o", e, o],
                    [exe("objcopy"), "-O", "binary", "-j", ".text", e, b]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"{os.path.basename(cmd[0])}: {r.stderr.strip()}")
        return open(b, "rb").read()


if __name__ == "__main__":
    data = build(0x3CF0_0000)
    print(f"{len(data)} bytes")
