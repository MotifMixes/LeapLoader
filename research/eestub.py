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

On some screens the game's scripts don't run at all (name-entry keyboards, videos: Cosmic Math,
Sonic X, Schoolhouse Rock), so neither the prompt nor the flusher sees the keys. For those, __llEE
also wraps ButtonMPI's poll (+8, run every 10 ms by the BIOS button task) as nativechip.py does:
held for FALLBACK_POLLS (4 s, after the prompt's 2.5 s bar would have gone back already) the stub
restarts into the menu. The button task must not touch files: while the game reads the card (Schoolhouse
Rock's videos) a save written from it hung the console, and BT_StartSDMenu's own PlayGame.lnk write failed,
so the console went to its home screen (VERIFIED-EMU). So the stub writes PlayGame.lnk (the menu's path,
as BT_StartSDMenu does: 0x400F_16C8 path, 0x400F_1724 the .lnk's path, "w+") once at install, in the
game's own context, and the fallback only calls LC_Boot("ExtStorage") (0x400F_0674), the restart that
reads it. (Any other restart of the game still boots the console's home screen, which ignores the .lnk.)
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bioscall  # noqa: E402

TOOLS = os.environ.get("ARC_GNU", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Ribbit", "tools", "arc-gnu"))
EXE = ".exe" if os.name == "nt" else ""  # the binutils' file names on this system
NATIVE_NAME = "__llEE"
KEYS_FLAG = 1 << 29
# ButtonMPI GetButtonState word 0 = pressed buttons: A, B, HINT (as nativechip.COMBO)
COMBO = 0x4000 | 0x2000 | 0x1000_0000
FALLBACK_POLLS = 400  # HINT + A + B held 4 s (one poll per 10 ms) with nothing done: back to the menu
QUIET = 10  # calls (one a frame) without changes before the save file is written
STALE = 100  # button polls (1 s) without a flusher call: chip writes go to the save file at once
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
    ; Only on the BIOSes bioscall.py knows: 0.6 (its part number's "20" at 0x4000_5B18) and the
    ; Connected B5 ("07"). 0.2.0 called 0.6 addresses on B5 too, and there a game got stuck on its
    ; loading screen and the SD card's files were scrambled (2026-10-26). On any other BIOS nothing
    ; is installed or written; the call returns 0 (no saves, no keys).
    mov     r1, 0x40005b18
    ldh     r1, [r1]
    mov     r14, 0
    cmp     r1, 0x3730
    beq     98f
    cmp     r1, 0x3032
    bne     13f
98:
    mov     r0, 0
    bl      arg_int
    mov     r15, r0
    bl      btn_install
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
    bl      menu_lnk
1:
    ; the button poll's tick count now: the chip writes see how long ago the flusher last ran
    mov     r5, ticks
    ld      r6, [r5]
    mov     r5, llee_tick
    st      r6, [r5]
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

    .align  4
; ---- the stub's prompt (prompt_rle's runs) into VRAM with uncached stores, then the bar for r9
; polls held (BAR_W * r9 / PROMPT_POLLS ~ r9 * 7 / 16 pixels, in pairs)
draw_prompt:
    mov     r0, prompt_data
    mov     r1, VRAM + PANEL_Y * VRAM_PITCH + PANEL_X / 2 * 3
    mov     r5, PANEL_H
dp_row:
    mov     r7, r1
    mov     r6, PANEL_W / 2
dp_run:
    ldb.ab  r2, [r0, 1]
    bbit0   r2, 7, dp_fill
    bclr    r2, r2, 7               ; see-through pairs
    sub     r6, r6, r2
    add     r3, r2, r2
    add     r3, r3, r2
    add     r7, r7, r3
    b       dp_next
dp_fill:
    ldb.ab  r3, [r0, 1]
    ldb.ab  r4, [r0, 1]
    ldb.ab  r8, [r0, 1]
    sub     r6, r6, r2
dp_put:
    stb.di  r3, [r7]
    stb.di  r4, [r7, 1]
    stb.di  r8, [r7, 2]
    add     r7, r7, 3
    sub     r2, r2, 1
    brne    r2, 0, dp_put
dp_next:
    brne    r6, 0, dp_run
    add     r1, r1, VRAM_PITCH
    sub     r5, r5, 1
    brne    r5, 0, dp_row
    ; the bar: r10 = min(r9 * 7 / 16, BAR_W) / 2 pairs
    add     r10, r9, r9
    add     r10, r10, r10
    add     r10, r10, r10
    sub     r10, r10, r9
    lsr     r10, r10
    lsr     r10, r10
    lsr     r10, r10
    lsr     r10, r10
    brlo    r10, BAR_W, 1f
    mov     r10, BAR_W
1:
    lsr     r10, r10
    breq    r10, 0, dp_done
    mov     r3, BAR_B0
    mov     r4, BAR_B1
    mov     r8, BAR_B2
    mov     r1, VRAM + BAR_Y * VRAM_PITCH + BAR_X / 2 * 3
    mov     r5, BAR_H
dp_brow:
    mov     r7, r1
    mov     r2, r10
dp_bput:
    stb.di  r3, [r7]
    stb.di  r4, [r7, 1]
    stb.di  r8, [r7, 2]
    add     r7, r7, 3
    sub     r2, r2, 1
    brne    r2, 0, dp_bput
    add     r1, r1, VRAM_PITCH
    sub     r5, r5, 1
    brne    r5, 0, dp_brow
dp_done:
    j_s     [blink]

    .align  4
; ---- ButtonMPI ([[gp+4]+0x7C]) copied with its poll (+8) wrapped, unless it is ours already
btn_install:
    ld      r1, [gp, 4]
    ld      r2, [r1, 0x7c]
    mov     r3, btn_table
    breq    r2, r3, 9f
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
9:
    j_s     [blink]

    .align  4
; ---- the poll wrapper: the original, then count how long HINT + A + B are held
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
    ; polls until going back: FALLBACK_POLLS, or PROMPT_POLLS with our own prompt drawn when no
    ; script is running (no flusher call for STALE polls: ingame.py's prompt can't show)
    ; The panel is drawn whenever HINT + A + B are held: on a real console ingame.py's prompt did
    ; not show in Cars with its script running (user, 2026-11-01; it does in Ribbit). With a script
    ; running, that prompt still does the going back (saves written) and the bar stays full until it
    ; or the fallback does.
    mov     r5, FALLBACK_POLLS
    breq    r4, 0, bp_check
    mov     r6, PROMPT_ON
    breq    r6, 0, bp_check
    mov     r9, r4
    bl      draw_prompt
    mov     r3, btn_hold
    ld      r4, [r3]
    mov     r5, PROMPT_LATE             ; (Cars' name entry: the script runs, its prompt doesn't go back)
    mov     r6, ticks
    ld      r6, [r6]
    mov     r7, llee_tick
    ld      r7, [r7]
    sub     r6, r6, r7
    brlo    r6, STALE, bp_check
    mov     r5, PROMPT_POLLS
bp_check:
    brlo    r4, r5, 3f
    mov     r0, 0x400f78fc          ; "ExtStorage": restart into the PlayGame.lnk written at install
    mov     r1, 0x400f0674
    jl      [r1]
3:
    mov     r3, ticks               ; a clock for the chip writes (one tick per poll, 10 ms)
    ld      r4, [r3]
    add     r4, r4, 1
    st      r4, [r3]
    mov     r0, r14
    add     sp, sp, 16
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

    .align  4
; ---- PlayGame.lnk = the menu's path, as BT_StartSDMenu (0x4002_2C8C) and 0x4002_2AA8 write it
menu_lnk:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    sub     sp, sp, 0x170           ; the menu's path at sp (0x68), the .lnk's at sp+0x68 (260)
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
    mov     r1, 0x400f78f8          ; "w+"
    mov     r2, FOPEN
    jl      [r2]
    mov     r13, r0
    breq    r13, 0, 1f
    mov     r0, sp
    mov     r1, 0x400e839c          ; strlen
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
    b       written
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
    b       written
8:
    mov     r0, 0
    j_s     [blink]
9:
    mov     r4, orig_table
    ld      r4, [r4]
    ld      r4, [r4, 0]
    j       [r4]

; ---- end of a chip write (returns 1). While the flusher runs, it writes the save file later; when it
; has not run for STALE ticks (the game's scripts stopped: Sonic X plays in its own native code after
; its logo), the file is written now, from the game's own call (not the button task: no file access there)
written:
    mov     r4, ticks
    ld      r5, [r4]
    mov     r4, llee_tick
    ld      r6, [r4]
    sub     r5, r5, r6
    brlo    r5, STALE, 1f
    st.aw   blink, [sp, -4]
    bl      persist
    mov     r4, dirty_lo            ; nothing left for the flusher to write
    mov     r5, 0xffff
    st      r5, [r4]
    mov     r5, 0
    st      r5, [r4, 4]
    mov     r4, pending
    st      r5, [r4]
    ld.ab   blink, [sp, 4]
1:
    mov     r0, 1
    j_s     [blink]

    .align  4
ticks:
    .word   0                       ; button polls so far
llee_tick:
    .word   0                       ; ticks at the flusher's last call
orig_table:
    .word   0
dirty_lo:
    .word   0xffff                  ; changed range (lo > hi: none)
dirty_hi:
    .word   0
fake_table:
    .word   0, 0, 0, 0, 0, 0
btn_orig:
    .word   0                       ; the BIOS's ButtonMPI table
btn_hold:
    .word   0                       ; polls with HINT + A + B held
btn_table:
    .fill   64, 1, 0                ; our copy of it (16 words)
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
prompt_data:                        ; the stub's prompt panel as runs (prompt_rle)
PROMPT_DATA
    .align  4
mem:
    .fill   SIZE, 1, CHIPFILL
"""


# The stub's own prompt (user, 2026-11-01: "i rly want it to show the same bar as the other games"):
# where no script runs (name entry, videos, Counting on Zero's native screens) ingame.py's prompt never
# shows, so with HINT + A + B held and no flusher call for STALE polls, the button poll draws the same
# panel straight into the LCD's VRAM (0x0300_0000, uncached stores; the game's next frame covers it, so
# every poll draws it again) with the bar filling over PROMPT_POLLS, then goes back as the fallback does.
# Panel, texts and colours as LeapLoader-Emulators' llm_back_prompt (ingame.py's layout, 12-bit colours).
PROMPT_POLLS = 250                         # 2.5 s, as the prompt's bar
PROMPT_LATE = 300                          # 3 s: with the panel drawn and a script running, back if its prompt hasn't gone
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 34, 136, 88
BAR_X, BAR_Y, BAR_W, BAR_H, BAR_RGB = 26, 104, 108, 8, 0x3B4
VRAM, VRAM_PITCH = 0x0300_0000, 240        # 160 x 160, two 12-bit pixels in three bytes


def pack(a, b):
    """Two 12-bit pixels as the LCD stores them: g0b0, r0r1, g1b1."""
    return bytes([a & 0xFF, (a >> 4 & 0xF0) | (b >> 8), b & 0xFF])


def prompt_rle(menu_name):
    """The panel as runs, row by row (PANEL_W / 2 pairs a row, no run across rows): a byte 0x80 + n
    skips n pairs (see-through: the rounded corners), a byte n < 0x80 then 3 bytes repeats that pair n times."""
    from pixelfont import GLYPHS, ADVANCE
    from swfgen import rounded_rects
    img = [[None] * PANEL_W for _ in range(PANEL_H)]

    def rect(x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if 0 <= yy - PANEL_Y < PANEL_H and 0 <= xx - PANEL_X < PANEL_W:
                    img[yy - PANEL_Y][xx - PANEL_X] = c

    def text(x, y, s, c, sc=1):  # from the glyph's top row, as llm_text
        for ch in s:
            for r, row in enumerate(GLYPHS.get(ch, GLYPHS["?"])):
                for i, px in enumerate(row):
                    if px == "#":
                        rect(x + i * sc, y + r * sc, sc, sc, c)
            x += ADVANCE * sc
    for r in rounded_rects(12, 34, 136, 88, 4):
        rect(*r, 0xFD1)
    for r in rounded_rects(15, 37, 130, 82, 3):
        rect(*r, 0x316)
    text(22, 43, "Back to the", 0xFFF)
    text(20, 56, menu_name, 0xFD1, 2)
    text(22, 78, "Keep holding", 0xFFF)
    text(22, 89, "HINT + A + B", 0xFD1)
    for r in rounded_rects(24, 102, 112, 12, 2):
        rect(*r, 0x103)
    out = bytearray()
    for row in img:
        pairs = []
        for p in range(PANEL_W // 2):
            a, b = row[2 * p], row[2 * p + 1]
            pairs.append(None if a is None and b is None else pack(a if a is not None else b, b if b is not None else a))
        i = 0
        while i < len(pairs):
            j = i
            while j < len(pairs) and pairs[j] == pairs[i] and j - i < 0x7F:
                j += 1
            out += bytes([0x80 + j - i]) if pairs[i] is None else bytes([j - i]) + pairs[i]
            i = j
    return bytes(out)


def build(address, size=256, path="b:\\save.dat", fill=0xFF, menu_name=None):
    """The stub assembled for `address` (a word-aligned RAM address in the SD image) with a
    `size`-byte chip kept in the file `path` (a BIOS path: b:\\Leapster\\Apps\\<game>\\save.dat),
    starting as `fill` before a save is read (0xFF: an erased chip; 0 for the games that came from
    the native chip, which starts zeroed: Pet Pals shows junk names from an erased one)."""
    if size & (size - 1) or not 32 <= size <= 0x10000:
        raise ValueError("chip size must be a power of two")
    data = prompt_rle(menu_name) if menu_name else b""
    prompt = "\n".join("    .byte   " + ", ".join(str(x) for x in data[i:i + 16]) for i in range(0, len(data), 16))
    src = (SOURCE.replace("SYSTEM_DEVICE", str(SYSTEM_DEVICE)).replace("COMBO", str(COMBO))
           .replace("KEYS_FLAG", str(KEYS_FLAG)).replace("MASK", str(size - 1)).replace("SIZE", str(size))
           .replace("QUIET", str(QUIET)).replace("STALE", str(STALE)).replace("FALLBACK_POLLS", str(FALLBACK_POLLS))
           .replace("PROMPT_ON", "1" if data else "0").replace("PROMPT_POLLS", str(PROMPT_POLLS)).replace("PROMPT_LATE", str(PROMPT_LATE))
           .replace("PROMPT_DATA", prompt)
           .replace("VRAM_PITCH", str(VRAM_PITCH)).replace("VRAM", str(VRAM)).replace("PANEL_X", str(PANEL_X))
           .replace("PANEL_Y", str(PANEL_Y)).replace("PANEL_W", str(PANEL_W)).replace("PANEL_H", str(PANEL_H))
           .replace("BAR_B0", str(pack(BAR_RGB, BAR_RGB)[0])).replace("BAR_B1", str(pack(BAR_RGB, BAR_RGB)[1]))
           .replace("BAR_B2", str(pack(BAR_RGB, BAR_RGB)[2])).replace("BAR_X", str(BAR_X)).replace("BAR_Y", str(BAR_Y))
           .replace("BAR_W", str(BAR_W)).replace("BAR_H", str(BAR_H)).replace("CHIPFILL", str(fill)).replace("PATH", path.replace("\\", "\\\\")))
    exe = lambda n: os.path.join(TOOLS, f"arc-elf32-{n}{EXE}")
    with tempfile.TemporaryDirectory() as t:
        s, o, e, b = (os.path.join(t, n) for n in ("stub.s", "stub.o", "stub.elf", "stub.bin"))
        open(s, "w").write(bioscall.portable(src))
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
