"""Prototype (research): the native llZ for bigimage.py (images larger than 8 MiB).

llZ(x) is the BIOS's lfh(x) (native 0x400A_0EA8, VERIFIED-FW: a string argument comes back as the
same string, anything else as a number; getURL then treats the number as a resource handle), plus:
when x, converted with the BIOS's to-number routine 0x4009_5FA4 (as lfh does), is one of the
groups' handles, the group's file is read into a RAM slot and the group's table words are pointed
at it. Slots are used in turn; asking again for the group in the newest slot reads nothing.
File calls: the BIOS 0.6 C library thunks (see nativechip.py).

Group record: {handle as a double (lo, hi), path, count, count x (word address, offset in file)}.
"""
import os
import struct
import subprocess
import tempfile

TOOLS = os.environ.get("ARC_GNU", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Ribbit", "tools", "arc-gnu"))
FOPEN, FREAD, FCLOSE = 0x400F0830, 0x400F0890, 0x400F06A0
TONUMBER, LFH = 0x40095FA4, 0x400A0EA8
NAME = "llZ"

SOURCE = r"""
    .cpu    arc600
    .text
    .global _start
_start:
blob:
    .word   0x100, 0, 0x00010000, pairs
pairs:
    .word   name, llz
name:
    .asciz  "NAME"
    .align  4

; ---- llZ(ctx)
llz:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    st.aw   r15, [sp, -4]
    mov     r13, r0
    ld      r0, [r13, 0]
    ld      r1, [r13, 12]
    mov     r2, 0
    mov     r3, TONUMBER
    jl      [r3]
    mov     r14, groups
    mov     r15, NGROUPS
1:
    breq    r15, 0, 5f
    ld      r2, [r14, 0]
    ld      r3, [r14, 4]
    brne    r2, r0, 2f
    brne    r3, r1, 2f
    mov     r0, r14
    bl      load
    b       5f
2:
    ld      r2, [r14, 12]
    asl     r2, r2, 3
    add     r14, r14, r2
    add     r14, r14, 16
    sub     r15, r15, 1
    b       1b
5:
    mov     r0, r13
    ld.ab   r15, [sp, 4]
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    mov     r12, LFH
    j       [r12]

; ---- load(group): into the slot after the newest, unless the newest holds it already
load:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    st.aw   r15, [sp, -4]
    mov     r13, r0
    mov     r4, newest
    ld      r5, [r4]
    mov     r6, slot_group
    ld.as   r7, [r6, r5]
    breq    r7, r13, 9f
    add     r5, r5, 1
    brlo    r5, NSLOTS, 3f
    mov     r5, 0
3:
    st      r5, [r4]
    asl     r8, r5, 2
    add     r8, r6, r8
    st      r13, [r8]
    mov     r6, slot_base
    ld.as   r14, [r6, r5]
    ld      r0, [r13, 8]
    mov     r1, mode_r
    mov     r2, FOPEN
    jl      [r2]
    mov     r15, r0
    breq    r15, 0, 9f
    mov     r0, r14
    mov     r1, 1
    mov     r2, SLOT
    mov     r3, r15
    mov     r4, FREAD
    jl      [r4]
    mov     r0, r15
    mov     r1, FCLOSE
    jl      [r1]
    ld      r2, [r13, 12]
    add     r3, r13, 16
4:
    breq    r2, 0, 9f
    ld      r4, [r3, 0]
    ld      r5, [r3, 4]
    add     r5, r5, r14
    st      r5, [r4]
    add     r3, r3, 8
    sub     r2, r2, 1
    b       4b
9:
    ld.ab   r15, [sp, 4]
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

    .align  4
newest:
    .word   0
slot_group:
SLOTGROUPS
slot_base:
SLOTBASES
mode_r:
    .asciz  "rb"
    .align  4
groups:
GROUPS
PATHS
    .align  4
"""


def build(address, groups, slots, slot_size):
    """`groups`: [(handle, path, [(word address, offset in the file)])]. Returns (code, offset of
    the 0x1009 blob in it = 0)."""
    recs, paths = [], []
    for k, (handle, path, words) in enumerate(groups):
        lo, hi = struct.unpack("<II", struct.pack("<d", float(handle)))
        recs.append(f"    .word   {lo:#x}, {hi:#x}, path{k}, {len(words)}\n" +
                    "".join(f"    .word   {a:#x}, {o:#x}\n" for a, o in words))
        paths.append(f"path{k}:\n    .asciz  \"{path.replace(chr(92), chr(92) * 2)}\"\n")
    src = (SOURCE.replace("NAME", NAME).replace("NGROUPS", str(len(groups))).replace("NSLOTS", str(len(slots)))
           .replace("SLOTGROUPS", "".join("    .word   0xffffffff\n" for _ in slots))
           .replace("SLOTBASES", "".join(f"    .word   {s:#x}\n" for s in slots))
           .replace("GROUPS", "".join(recs)).replace("PATHS", "".join(paths))
           .replace("mov     r2, SLOT\n", f"mov     r2, {slot_size:#x}\n")
           .replace("TONUMBER", f"{TONUMBER:#x}").replace("LFH", f"{LFH:#x}")
           .replace("FOPEN", f"{FOPEN:#x}").replace("FREAD", f"{FREAD:#x}").replace("FCLOSE", f"{FCLOSE:#x}"))
    exe = lambda n: os.path.join(TOOLS, f"arc-elf32-{n}.exe")
    with tempfile.TemporaryDirectory() as t:
        s, o, e, b = (os.path.join(t, n) for n in ("s.s", "s.o", "s.elf", "s.bin"))
        open(s, "w").write(src)
        for cmd in ([exe("as"), "-mcpu=arc600", "-o", o, s],
                    [exe("ld"), "-EL", "-Ttext", f"{address:#x}", "-e", "_start", "-o", e, o],
                    [exe("objcopy"), "-O", "binary", "-j", ".text", e, b]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"{os.path.basename(cmd[0])}: {r.stderr.strip()}")
        return open(b, "rb").read(), 0


if __name__ == "__main__":
    code, _ = build(0x3CF0_0000, [(0x8000_0001, "b:\\Leapster\\Apps\\T\\m1.bin", [(0x3C80_1234, 0)])],
                    [0x3CE0_0000, 0x3CD0_0000], 0x10_0000)
    print(len(code), "bytes")


PEG_SOURCE = r"""
    .cpu    arc600
    .text
    .global _start
_start:

; ---- LF_WriteGlobalDataBytes(addr, value, n) wrapper: remember the value written to byte 1
wgdb:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    mov     r13, r0
    mov     r0, 0
    bl      arg_int
    mov     r14, r0
    brne    r14, 1, 1f
    mov     r0, 1
    bl      arg_int
    mov     r1, current
    st      r0, [r1]
1:
    mov     r0, r13
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    mov     r12, ORIG_WGDB
    j       [r12]

; ---- LF_PlayPegApplication(n) wrapper: load the current video's file first
peg:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    mov     r13, r0
    mov     r1, current
    ld      r1, [r1]
    brhs    r1, NGROUPS, 1f
    mov     r0, groups
    asl     r1, r1, 2
    ld      r0, [r0, r1]
    bl      load
1:
    mov     r0, r13
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    mov     r12, ORIG_PEG
    j       [r12]

; ---- argument r0 of the native whose context is r13, as an integer
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

; ---- load(group record): read its file into the slot, point its table words at it
load:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r15, [sp, -4]
    mov     r13, r0
    mov     r4, loaded
    ld      r5, [r4]
    breq    r5, r13, 9f
    st      r13, [r4]
    ld      r0, [r13, 0]
    mov     r1, mode_r
    mov     r2, FOPEN
    jl      [r2]
    mov     r15, r0
    breq    r15, 0, 9f
    mov     r0, SLOTBASE
    mov     r1, 1
    mov     r2, SLOTSIZE
    mov     r3, r15
    mov     r4, FREAD
    jl      [r4]
    mov     r0, r15
    mov     r1, FCLOSE
    jl      [r1]
    ld      r2, [r13, 4]
    add     r3, r13, 8
4:
    breq    r2, 0, 9f
    ld      r4, [r3, 0]
    ld      r5, [r3, 4]
    add     r5, r5, SLOTBASE
    st      r5, [r4]
    add     r3, r3, 8
    sub     r2, r2, 1
    b       4b
9:
    ld.ab   r15, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    j       [blink]

    .align  4
current:
    .word   0xffffffff
loaded:
    .word   0
groups:
GROUPPTRS
RECORDS
mode_r:
    .asciz  "rb"
PATHS
    .align  4
"""

DTOI = 0x400EF75C  # BIOS double (r0:r1) -> int, as lfh uses it


def build_peg(address, groups, slot_base, slot_size, orig_wgdb, orig_peg):
    """`groups`: one per video number: (path, [(word address, offset in the file)]).
    Returns (code, {"wgdb": address, "peg": address}) for the two wrappers."""
    ptrs = "".join(f"    .word   rec{k}\n" for k in range(len(groups)))
    recs = "".join(f"rec{k}:\n    .word   path{k}, {len(w)}\n" + "".join(f"    .word   {a:#x}, {o:#x}\n" for a, o in w)
                   for k, (_, w) in enumerate(groups))
    paths = "".join(f"path{k}:\n    .asciz  \"{p.replace(chr(92), chr(92) * 2)}\"\n" for k, (p, _) in enumerate(groups))
    src = (PEG_SOURCE.replace("GROUPPTRS", ptrs).replace("RECORDS", recs).replace("PATHS", paths)
           .replace("NGROUPS", str(len(groups))).replace("ORIG_WGDB", f"{orig_wgdb:#x}").replace("ORIG_PEG", f"{orig_peg:#x}")
           .replace("SLOTBASE", f"{slot_base:#x}").replace("SLOTSIZE", f"{slot_size:#x}").replace("DTOI", f"{DTOI:#x}")
           .replace("FOPEN", f"{FOPEN:#x}").replace("FREAD", f"{FREAD:#x}").replace("FCLOSE", f"{FCLOSE:#x}"))
    exe = lambda n: os.path.join(TOOLS, f"arc-elf32-{n}.exe")
    with tempfile.TemporaryDirectory() as t:
        s, o, e, b = (os.path.join(t, n) for n in ("s.s", "s.o", "s.elf", "s.bin"))
        open(s, "w").write(src)
        for cmd in ([exe("as"), "-mcpu=arc600", "-o", o, s],
                    [exe("ld"), "-EL", "-Ttext", f"{address:#x}", "-e", "_start", "-o", e, o],
                    [exe("objcopy"), "-O", "binary", "-j", ".text", e, b]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"{os.path.basename(cmd[0])}: {r.stderr.strip()}")
        syms = subprocess.run([exe("nm"), e], capture_output=True, text=True).stdout
        addr = {l.split()[2]: int(l.split()[0], 16) for l in syms.splitlines() if len(l.split()) == 3}
        return open(b, "rb").read(), {"wgdb": addr["wgdb"], "peg": addr["peg"]}


# ---- LL_PlayLFC: sound clips of table 4 kept in one file on the card (Story Explorers)
NAME_LFC = "LL_PlayLFC"  # the same length as LF_PlayLFC, which the movies' ActionScript names
PLAYLFC = 0x400A2F54     # BIOS native LF_PlayLFC (VERIFIED-FW: its name/function pair at 0x4010_3E68)
FSEEK = 0x400F098C       # BIOS C library thunk, slot 0x38 after fwrite (f, offset, whence)

LFC_SOURCE = r"""
    .cpu    arc600
    .text
    .global _start
_start:
    .word   0x100, 0, 0x00010000, pairs
pairs:
    .word   name, plfc
name:
    .asciz  "NAME"
    .align  4

; ---- LL_PlayLFC(ctx): read the clip named by argument 0 into the ring, then LF_PlayLFC
plfc:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    st.aw   r15, [sp, -4]
    st.aw   r16, [sp, -4]
    st.aw   r17, [sp, -4]
    st.aw   r18, [sp, -4]
    mov     r13, r0
    ld      r0, [r13, 0]
    ld      r1, [r13, 12]
    mov     r2, 0
    mov     r3, TONUMBER
    jl      [r3]
    mov     r2, DTOI
    jl      [r2]
    sub     r14, r0, FIRST
    cmp     r14, NCLIPS
    bhs     9f
    asl     r2, r14, 3
    asl     r3, r14, 2
    add     r2, r2, r3
    mov     r15, clips
    add     r15, r15, r2
    ld      r16, [r15, 8]
    breq    r16, 0, 9f
    mov     r4, last
    ld      r5, [r4]
    breq    r5, r14, 9f
    mov     r4, ringpos
    ld      r17, [r4]
    add     r6, r17, r16
    cmp     r6, RINGSIZE
    bls     1f
    mov     r17, 0
1:
    add     r17, r17, RING
    mov     r0, path
    mov     r1, mode_r
    mov     r2, FOPEN
    jl      [r2]
    mov     r18, r0
    breq    r18, 0, 9f
    ld      r1, [r15, 4]
    mov     r2, 0
    mov     r3, FSEEK
    jl      [r3]
    mov     r0, r17
    mov     r1, 1
    mov     r2, r16
    mov     r3, r18
    mov     r4, FREAD
    jl      [r4]
    mov     r0, r18
    mov     r1, FCLOSE
    jl      [r1]
    ld      r2, [r15, 0]
    st      r17, [r2]
    sub     r17, r17, RING
    add     r17, r17, r16
    add     r17, r17, 3
    and     r17, r17, -4
    mov     r4, ringpos
    st      r17, [r4]
    mov     r4, last
    st      r14, [r4]
9:
    mov     r0, r13
    ld.ab   r18, [sp, 4]
    ld.ab   r17, [sp, 4]
    ld.ab   r16, [sp, 4]
    ld.ab   r15, [sp, 4]
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    mov     r12, PLAYLFC
    j       [r12]

    .align  4
last:
    .word   0xffffffff
ringpos:
    .word   0
mode_r:
    .asciz  "rb"
path:
    .asciz  "PATH"
    .align  4
clips:
CLIPS
"""


def build_lfc(address, path, first, recs, ring, ring_size):
    """`recs`: per handle index (handle - `first`) of table 4: (table word address, offset in the
    file, length; 0 = the clip stays in the image). Returns the code; the 0x1009 blob is at 0."""
    clips = "".join(f"    .word   {a:#x}, {o:#x}, {n:#x}\n" for a, o, n in recs)
    src = (LFC_SOURCE.replace("NAME", NAME_LFC).replace("PATH", path.replace(chr(92), chr(92) * 2))
           .replace("NCLIPS", str(len(recs))).replace("CLIPS", clips).replace("FIRST", f"{first:#x}")
           .replace("RINGSIZE", f"{ring_size:#x}").replace("RING", f"{ring:#x}")
           .replace("TONUMBER", f"{TONUMBER:#x}").replace("DTOI", f"{DTOI:#x}").replace("PLAYLFC", f"{PLAYLFC:#x}")
           .replace("FOPEN", f"{FOPEN:#x}").replace("FSEEK", f"{FSEEK:#x}").replace("FREAD", f"{FREAD:#x}")
           .replace("FCLOSE", f"{FCLOSE:#x}"))
    exe = lambda n: os.path.join(TOOLS, f"arc-elf32-{n}.exe")
    with tempfile.TemporaryDirectory() as t:
        s, o, e, b = (os.path.join(t, n) for n in ("s.s", "s.o", "s.elf", "s.bin"))
        open(s, "w").write(src)
        for cmd in ([exe("as"), "-mcpu=arc600", "-o", o, s],
                    [exe("ld"), "-EL", "-Ttext", f"{address:#x}", "-e", "_start", "-o", e, o],
                    [exe("objcopy"), "-O", "binary", "-j", ".text", e, b]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"{os.path.basename(cmd[0])}: {r.stderr.strip()}")
        return open(b, "rb").read()


# ---- llL / llU: movies kept in one file on the card, loaded into a pool by level (Story Explorers)
# Every GetURL2 into "_level" + N gets llL(N) and llU(url) in front of it (avm1patch.level_loads).
# Each level holds its current and its previous movie (the one being replaced may still run this
# frame); the movie before that is freed and its table word goes back to an empty movie (stub).
NAME_LEVEL, NAME_URL = "llL", "llU"
NLEVELS = 64

POOL_SOURCE = r"""
    .cpu    arc600
    .text
    .global _start
_start:
    .word   0x100, 0, 0x00020000, pairs
pairs:
    .word   name_l, lll, name_u, llu
name_l:
    .asciz  "LNAME"
name_u:
    .asciz  "UNAME"
    .align  4

; ---- llL(level): the level of the next llU
lll:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    mov     r13, r0
    ld      r0, [r13, 0]
    ld      r1, [r13, 12]
    mov     r2, 0
    mov     r3, TONUMBER
    jl      [r3]
    mov     r2, DTOI
    jl      [r2]
    mov     r2, pending
    st      r0, [r2]
    mov     r0, r13
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    mov     r12, LFH
    j       [r12]

; ---- llU(url): the movie url (a handle) goes into the pending level
llu:
    st.aw   blink, [sp, -4]
    st.aw   r13, [sp, -4]
    st.aw   r14, [sp, -4]
    st.aw   r15, [sp, -4]
    st.aw   r16, [sp, -4]
    st.aw   r17, [sp, -4]
    st.aw   r18, [sp, -4]
    st.aw   r19, [sp, -4]
    st.aw   r20, [sp, -4]
    mov     r13, r0
    ld      r0, [r13, 0]
    ld      r1, [r13, 12]
    mov     r2, 0
    mov     r3, TONUMBER
    jl      [r3]
    mov     r2, 0x7ff00000
    and     r3, r1, r2
    breq    r3, r2, 1f
    mov     r2, DTOI
    jl      [r2]
    add     r14, r0, 0x80000000
    b       2f
1:
    mov     r14, -1
2:
    mov     r2, pending
    ld      r15, [r2]
    mov     r3, -1
    st      r3, [r2]
    cmp     r15, NLEV
    bhs     9f
    mov     r16, 0
    cmp     r14, NMOV
    bhs     3f
    asl     r2, r14, 4
    mov     r17, recs
    add     r17, r17, r2
    ld      r2, [r17, 8]
    breq    r2, 0, 3f
    add     r16, r14, 1
3:
    asl     r3, r15, 2
    mov     r2, cur
    add     r18, r2, r3
    mov     r2, prev
    add     r19, r2, r3
    ld      r20, [r19]
    ld      r2, [r18]
    st      r2, [r19]
    st      r16, [r18]
    breq    r20, 0, 4f
    breq    r20, r16, 4f
    mov     r0, r20
    bl      live
    brne    r0, 0, 4f
    sub     r2, r20, 1
    asl     r2, r2, 4
    mov     r3, recs
    add     r3, r3, r2
    mov     r4, 0
    st      r4, [r3, 12]
    ld      r4, [r3, 0]
    mov     r5, STUB
    st      r5, [r4]
4:
    breq    r16, 0, 9f
    ld      r2, [r17, 12]
    breq    r2, 0, 5f
    ld      r3, [r17, 0]
    st      r2, [r3]
    b       9f
5:
    ld      r0, [r17, 8]
    bl      alloc
    brne    r0, 0, 6f
    mov     r2, failures
    ld      r3, [r2]
    add     r3, r3, 1
    st      r3, [r2]
    b       9f
6:
    mov     r18, r0
    mov     r0, path
    mov     r1, mode_r
    mov     r2, FOPEN
    jl      [r2]
    mov     r19, r0
    breq    r19, 0, 9f
    ld      r1, [r17, 4]
    mov     r2, 0
    mov     r3, FSEEK
    jl      [r3]
    mov     r0, r18
    mov     r1, 1
    ld      r2, [r17, 8]
    mov     r3, r19
    mov     r4, FREAD
    jl      [r4]
    mov     r0, r19
    mov     r1, FCLOSE
    jl      [r1]
    st      r18, [r17, 12]
    ld      r3, [r17, 0]
    st      r18, [r3]
9:
    mov     r0, r13
    ld.ab   r20, [sp, 4]
    ld.ab   r19, [sp, 4]
    ld.ab   r18, [sp, 4]
    ld.ab   r17, [sp, 4]
    ld.ab   r16, [sp, 4]
    ld.ab   r15, [sp, 4]
    ld.ab   r14, [sp, 4]
    ld.ab   r13, [sp, 4]
    ld.ab   blink, [sp, 4]
    mov     r12, LFH
    j       [r12]

; ---- live(r0 = movie + 1): 1 if a level holds it (now or as the previous movie), else 0
live:
    mov     r1, cur
    mov     r2, NLEV2
1:
    breq    r2, 0, 2f
    ld.ab   r3, [r1, 4]
    breq    r3, r0, 3f
    sub     r2, r2, 1
    b       1b
2:
    mov     r0, 0
    j       [blink]
3:
    mov     r0, 1
    j       [blink]

; ---- alloc(r0 = length): the first pool address clear of every loaded movie, or 0
alloc:
    mov     r1, r0
    mov     r2, POOL
1:
    add     r3, r2, r1
    mov     r4, POOLEND
    cmp     r3, r4
    bhi     8f
    mov     r5, recs
    mov     r6, NMOV
2:
    breq    r6, 0, 7f
    ld      r7, [r5, 12]
    breq    r7, 0, 3f
    ld      r8, [r5, 8]
    add     r8, r8, r7
    cmp     r2, r8
    bhs     3f
    cmp     r7, r3
    bhs     3f
    add     r2, r8, 15
    and     r2, r2, -16
    b       1b
3:
    add     r5, r5, 16
    sub     r6, r6, 1
    b       2b
7:
    mov     r0, r2
    j       [blink]
8:
    mov     r0, 0
    j       [blink]

    .align  4
pending:
    .word   0xffffffff
failures:
    .word   0
cur:
    .fill   NLEV, 4, 0
prev:
    .fill   NLEV, 4, 0
mode_r:
    .asciz  "rb"
path:
    .asciz  "PATH"
    .align  4
recs:
RECS
"""


def build_pool(address, path, recs, pool, pool_end, stub):
    """`recs`: per movie index (handle - 0x8000_0000): (table word address, offset in the file,
    length; 0 = the movie stays in the image). Returns the code; the 0x1009 blob is at 0."""
    body = "".join(f"    .word   {a:#x}, {o:#x}, {n:#x}, 0\n" for a, o, n in recs)
    src = (POOL_SOURCE.replace("LNAME", NAME_LEVEL).replace("UNAME", NAME_URL)
           .replace("PATH", path.replace(chr(92), chr(92) * 2)).replace("RECS", body)
           .replace("NLEV2", str(2 * NLEVELS)).replace("NLEV", str(NLEVELS)).replace("NMOV", str(len(recs)))
           .replace("POOLEND", f"{pool_end:#x}").replace("POOL", f"{pool:#x}").replace("STUB", f"{stub:#x}")
           .replace("TONUMBER", f"{TONUMBER:#x}").replace("DTOI", f"{DTOI:#x}").replace("LFH", f"{LFH:#x}")
           .replace("FOPEN", f"{FOPEN:#x}").replace("FSEEK", f"{FSEEK:#x}").replace("FREAD", f"{FREAD:#x}")
           .replace("FCLOSE", f"{FCLOSE:#x}"))
    exe = lambda n: os.path.join(TOOLS, f"arc-elf32-{n}.exe")
    with tempfile.TemporaryDirectory() as t:
        s, o, e, b = (os.path.join(t, n) for n in ("s.s", "s.o", "s.elf", "s.bin"))
        open(s, "w").write(src)
        for cmd in ([exe("as"), "-mcpu=arc600", "-o", o, s],
                    [exe("ld"), "-EL", "-Ttext", f"{address:#x}", "-e", "_start", "-o", e, o],
                    [exe("objcopy"), "-O", "binary", "-j", ".text", e, b]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"{os.path.basename(cmd[0])}: {r.stderr.strip()}")
        return open(b, "rb").read()


# The smallest movie: one empty frame (what a table word points at while its movie is not loaded).
STUB_SWF = b"FWS\x05" + (17).to_bytes(4, "little") + b"\x00" + b"\x00\x0c" + b"\x01\x00" + b"\x40\x00" + b"\x00\x00"
