"""Prototype (research): a save chip for SD-booted native games that have no room for the
ActionScript side of saves (eestub.py + saveshim.build_ee_loader need a copy of the main movie).

Same chip as eestub.py (the BIOS EEPROM table at [[gp+4]+0x88] replaced by a copy whose data
functions serve devices 1-3 from RAM), but entirely native, so it fits in ~1-2 KB of padding:
* installed by the first call to any of the game's named natives: every function pointer in the
  game's 0x1009 lists is pointed at a trampoline that installs the chip once, then jumps to the
  original function (each named native is how ActionScript enters the game's native code, so the
  chip is in place before that code can reach the EEPROM);
* the chip's memory comes from the BIOS's malloc, and is filled from the card file at install;
* every write saves the whole chip to the card file at once.
File calls are the BIOS 0.6 C library thunks SD_ReadText/SD_WriteText use (VERIFIED-FW):
fopen 0x400F_0830, fread 0x400F_0890 (buf, 1, n, f), fwrite 0x400F_09C8 (buf, n, 1, f),
fclose 0x400F_06A0, malloc 0x400F_1FDC. The file is binary (save.bin), not save.dat's hex text.
No HINT + A + B prompt for these games (that is ActionScript too).
"""
import os
import subprocess
import tempfile

TOOLS = os.environ.get("ARC_GNU", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Ribbit", "tools", "arc-gnu"))
EXE = ".exe" if os.name == "nt" else ""  # the binutils' file names on this system
FOPEN, FREAD, FWRITE, FCLOSE, MALLOC = 0x400F0830, 0x400F0890, 0x400F09C8, 0x400F06A0, 0x400F1FDC
SYSTEM_DEVICE = 0
# ButtonMPI GetButtonState word 0 = pressed buttons (GPIO bits inverted, as Ribbit's masks): A, B, HINT
COMBO = 0x4000 | 0x2000 | 0x1000_0000
HOLD_POLLS = 250  # 2.5 s at one poll per 10 ms

SOURCE = r"""
    .cpu    arc600
    .text
    .global _start
_start:
TRAMPS

; ---- r12 = index of the native that was called; install once, then go to it
common:
    mov     r11, installed
    ld      r11, [r11]
    brne    r11, 0, 2f
    st.aw   blink, [sp, -4]
    st.aw   r12, [sp, -4]
    st.aw   r0, [sp, -4]
    st.aw   r1, [sp, -4]
    st.aw   r2, [sp, -4]
    st.aw   r3, [sp, -4]
    st.aw   r4, [sp, -4]
    st.aw   r5, [sp, -4]
    st.aw   r6, [sp, -4]
    st.aw   r7, [sp, -4]
    bl      install
    ld.ab   r7, [sp, 4]
    ld.ab   r6, [sp, 4]
    ld.ab   r5, [sp, 4]
    ld.ab   r4, [sp, 4]
    ld.ab   r3, [sp, 4]
    ld.ab   r2, [sp, 4]
    ld.ab   r1, [sp, 4]
    ld.ab   r0, [sp, 4]
    ld.ab   r12, [sp, 4]
    ld.ab   blink, [sp, 4]
2:
    mov     r11, orig
    ld.as   r11, [r11, r12]
    j       [r11]

install:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    mov     r4, installed
    mov     r5, 1
    st      r5, [r4]
    mov     r0, SIZE
    mov     r1, MALLOC
    jl      [r1]
    mov     r13, r0
    cmp     r13, 0
    beq     9f
    mov     r4, memptr
    st      r13, [r4]
    mov     r2, SIZE
    mov     r3, r13
    mov     r5, FILL
1:
    stb     r5, [r3]
    add     r3, r3, 1
    sub     r2, r2, 1
    brne    r2, 0, 1b
    mov     r0, path
    mov     r1, mode_r
    mov     r2, FOPEN
    jl      [r2]
    mov     r14, r0
    breq    r14, 0, 3f
    mov     r0, r13
    mov     r1, 1
    mov     r2, SIZE
    mov     r3, r14
    mov     r4, FREAD
    jl      [r4]
    mov     r0, r14
    mov     r1, FCLOSE
    jl      [r1]
3:
    ld      r1, [gp, 4]
    ld      r2, [r1, 0x88]
    mov     r3, fake_table
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
    ; HINT + A + B: ButtonMPI ([[gp+4]+0x7C]) copied, its poll (+8, run every 10 ms) wrapped
    ld      r2, [r1, 0x7c]
    mov     r3, btn_table
    mov     r5, btn_orig
    st      r2, [r5]
    mov     r6, 16
    mov     r7, r3
    mov     r8, r2
5:
    ld      r4, [r8]
    st      r4, [r7]
    add     r7, r7, 4
    add     r8, r8, 4
    sub     r6, r6, 1
    brne    r6, 0, 5b
    mov     r4, btn_poll
    st      r4, [r3, 8]
    st      r3, [r1, 0x7c]
    bl      menu_lnk
9:
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

; ---- ButtonMPI poll wrapper: the original, then count how long HINT + A + B are held
btn_poll:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    sub     sp, sp, 16
    mov     r13, btn_orig
    ld      r13, [r13]
    ld      r1, [r13, 8]
    jl      [r1]
    mov     r14, r0
    mov     r0, sp
    ld      r1, [r13, 4]
    jl      [r1]
    ld      r2, [sp]
    mov     r3, btn_last
    st      r2, [r3]
    and     r2, r2, COMBO
    mov     r3, btn_hold
    ld      r4, [r3]
    cmp     r2, COMBO
    bne     1f
    add     r4, r4, 1
    b       2f
1:
    mov     r4, 0
2:
    st      r4, [r3]
    cmp     r4, HOLD
    bne     3f
    bl      go_menu
3:
    mov     r0, r14
    add     sp, sp, 16
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

; ---- back to the SD menu: LC_Boot("ExtStorage") (0x400F_0674) restarts into the PlayGame.lnk that
; menu_lnk wrote at install. No file is touched here, in the button task (eestub.py: while the game
; reads the card, BT_StartSDMenu's own .lnk write from this task failed and the console went home).
go_menu:
    st.aw   blink, [sp, -4]
    mov     r0, 0x400f78fc
    mov     r1, 0x400f0674
    jl      [r1]
    ld.ab   blink, [sp, 4]
    j       [blink]

    .align  4
; ---- PlayGame.lnk = the menu's path, as BT_StartSDMenu (0x4002_2C8C) and 0x4002_2AA8 write it
menu_lnk:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    sub     sp, sp, 0x170
    mov     r0, sp
    mov     r1, 0x64
    mov     r2, 0x3c7fb3d0
    mov     r3, 1
    mov     r4, 0x400f792c
    mov     r5, 0x400f16c8
    jl      [r5]
    add     r0, sp, 0x68
    mov     r1, 260
    mov     r2, 1
    mov     r3, 0x400f1724
    jl      [r3]
    add     r0, sp, 0x68
    mov     r1, 0x400f78f8
    mov     r2, FOPEN
    jl      [r2]
    mov     r13, r0
    breq    r13, 0, 1f
    mov     r0, sp
    mov     r1, 0x400e839c
    jl      [r1]
    mov     r1, r0
    mov     r0, sp
    mov     r2, 1
    mov     r3, r13
    mov     r4, FWRITE
    jl      [r4]
    mov     r0, r13
    mov     r1, FCLOSE
    jl      [r1]
1:
    add     sp, sp, 0x170
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

    .align  4
; ---- write the whole chip to the card file
persist:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    mov     r0, path
    mov     r1, mode_w
    mov     r2, FOPEN
    jl      [r2]
    mov     r13, r0
    breq    r13, 0, 1f
    mov     r0, memptr
    ld      r0, [r0]
    mov     r1, SIZE
    mov     r2, 1
    mov     r3, r13
    mov     r4, FWRITE
    jl      [r4]
    mov     r0, r13
    mov     r1, FCLOSE
    jl      [r1]
1:
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

; ---- read(dev, addr, len, buf)
fk_read:
    breq    r0, SYSTEM_DEVICE, 9f
    breq    r2, 0, 8f
    mov     r6, memptr
    ld      r6, [r6]
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
    mov     r6, memptr
    ld      r6, [r6]
3:
    and     r4, r1, MASK
    ldb     r5, [r3]
    add     r8, r6, r4
    stb     r5, [r8]
    add     r1, r1, 1
    add     r3, r3, 1
    sub     r2, r2, 1
    brne    r2, 0, 3b
    st.aw   blink, [sp, -4]
    bl      persist
    ld.ab   blink, [sp, 4]
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
    mov     r6, memptr
    ld      r6, [r6]
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
    mov     r6, memptr
    ld      r6, [r6]
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
    st.aw   blink, [sp, -4]
    bl      persist
    ld.ab   blink, [sp, 4]
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
installed:
    .word   0
memptr:
    .word   0
orig_table:
    .word   0
fake_table:
    .word   0, 0, 0, 0, 0, 0
btn_orig:
    .word   0
btn_hold:
    .word   0
btn_last:
    .word   0
btn_table:
    .fill   64, 1, 0
orig:
ORIGS
path:
    .asciz  "PATH"
mode_r:
    .asciz  "rb"
mode_w:
    .asciz  "w"
    .align  4
"""


def build(address, size, path, originals):
    """The chip assembled for `address` (word aligned, in the SD image): (code, [trampoline
    addresses]) for the native functions `originals` (their SD addresses), in the same order."""
    if size & (size - 1) or not 32 <= size <= 0x10000:
        raise ValueError("chip size must be a power of two")
    tramps = "".join(f"tramp{k}:\n    mov     r12, {k}\n    b       common\n" for k in range(len(originals)))
    origs = "".join(f"    .word   {v:#x}\n" for v in originals) or "    .word   0\n"
    src = (SOURCE.replace("FILL", hex(int(os.environ.get("LL_CHIP_FILL", "0"), 0))).replace("COMBO", f"{COMBO:#x}").replace("HOLD", str(HOLD_POLLS)).replace("TRAMPS", tramps).replace("ORIGS", origs).replace("PATH", path.replace("\\", "\\\\"))
           .replace("SYSTEM_DEVICE", str(SYSTEM_DEVICE)).replace("MASK", str(size - 1)).replace("SIZE", str(size)))
    for name, value in (("FOPEN", FOPEN), ("FREAD", FREAD), ("FWRITE", FWRITE), ("FCLOSE", FCLOSE), ("MALLOC", MALLOC)):
        src = src.replace(f"mov     r1, {name}\n", f"mov     r1, {value:#x}\n").replace(
            f"mov     r2, {name}\n", f"mov     r2, {value:#x}\n").replace(f"mov     r4, {name}\n", f"mov     r4, {value:#x}\n")
    exe = lambda n: os.path.join(TOOLS, f"arc-elf32-{n}{EXE}")
    with tempfile.TemporaryDirectory() as t:
        s, o, e, b, m = (os.path.join(t, n) for n in ("chip.s", "chip.o", "chip.elf", "chip.bin", "chip.map"))
        open(s, "w").write(src)
        for cmd in ([exe("as"), "-mcpu=arc600", "-o", o, s],
                    [exe("ld"), "-EL", "-Ttext", f"{address:#x}", "-e", "_start", "-o", e, o],
                    [exe("objcopy"), "-O", "binary", "-j", ".text", e, b]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"{os.path.basename(cmd[0])}: {r.stderr.strip()}")
        syms = subprocess.run([exe("nm"), e], capture_output=True, text=True).stdout
        addr = {l.split()[2]: int(l.split()[0], 16) for l in syms.splitlines() if len(l.split()) == 3}
        return open(b, "rb").read(), [addr[f"tramp{k}"] for k in range(len(originals))]


if __name__ == "__main__":
    code, tr = build(0x3CFF_F000, 256, "b:\\Leapster\\Apps\\Test\\save.bin", [0x3C80_1000, 0x3C80_2000])
    print(f"{len(code)} bytes, trampolines {[hex(t) for t in tr]}")
