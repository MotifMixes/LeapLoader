"""Makes the stubs' BIOS calls work on every Leapster 2 BIOS with an SD slot (0.6 152-12206,
Connected B5 152-12076; 2026-10-26, user: "make sure it works on all leapster 2 bios").

The stubs (eestub.py, nativechip.py, streamstub.py) were written against BIOS 0.6 and load a BIOS
address into a register before calling it (`mov rN, 0x400F0830` ... `jl [rN]`), or pass one as an
argument. Those addresses differ in B5. `portable` rewrites each such line of a stub's assembly:

* C library and system calls are BIOS services: the BIOS's own thunks (0.6 0x400F_0830 fopen, ...)
  call a getter for service 0x10NN, whose lookup (0.6 0x400F_11A8, B5 0x400E_F560: the same code)
  returns [[gp + 4] + 0xC + 12 * (NN - 1) + 4], and then the function at a fixed slot of that table
  (VERIFIED-FW on 0.6 and B5). So `mov rN, fopen` becomes three loads:
      ld rN, [gp, 4] ; ld rN, [rN, 0x280] ; ld rN, [rN, 0x28]
* strlen, double-to-int (libgcc __fixdfsi) and the strings the stubs pass ("w+", "ExtStorage",
  "SDMenu\\SDMenu.bin", and "System", which 0.6 keeps in RAM at 0x3C7F_B3D0 and B5 doesn't) are the
  stub's own (appended).
* The Flash player's natives (lfh, LF_PlayLFC) and its to-number routine are no services: the stub
  reads the BIOS part number (at 0x4000_5B12 in every Leapster 2 BIOS; "152-12206", "152-12076",
  "152-12659") and picks that BIOS's address (found by each native's (name, function) pair in the
  BIOS, and lfh's own call for to-number).

CIP3 m9 (152-12659) has no SD slot or SD driver: a LeapLoader card can't run there.
"""
import re

# service table offset in [gp + 4] (0xC + 12 * (NN - 1) + 4), slot
FILE, BOOT, MEM, PATH = 0x280, 0x28, 0x10, 0x298       # services 0x1035, 0x1003, 0x1001, 0x1037
SERVICES = {
    0x400F0830: (FILE, 0x28),    # fopen(path, mode)
    0x400F06A0: (FILE, 0x2C),    # fclose(f)
    0x400F0890: (FILE, 0x30),    # fread(buf, size, n, f)
    0x400F09C8: (FILE, 0x34),    # fwrite(buf, size, n, f)
    0x400F098C: (FILE, 0x38),    # fseek(f, offset, whence)
    0x400F1FDC: (MEM, 200),      # malloc(n)
    0x400F0674: (BOOT, 0x34),    # LC_Boot(name)
    0x400F16C8: (PATH, 0x14),    # path(buf, size, folder, 1, name)
    0x400F1724: (PATH, 0x28),    # the PlayGame.lnk path(buf, size, 1)
}
OWN = {
    0x400E839C: "ll_strlen",
    0x400EF75C: "ll_dtoi",
    0x400F78F8: "ll_s_wplus",
    0x400F78FC: "ll_s_extstorage",
    0x400F792C: "ll_s_sdmenu",
    0x3C7FB3D0: "ll_s_system",
}
# 0.6 address -> (0.6, B5) for the Flash player's routines (B5: VERIFIED-FW 2026-10-26).
PER_BIOS = {
    0x40095FA4: (0x40095FA4, 0x40094C98),  # to-number (lfh's own call)
    0x400A0EA8: (0x400A0EA8, 0x4009FB9C),  # lfh native
    0x400A2F54: (0x400A2F54, 0x400A1C48),  # LF_PlayLFC native
}
NAMES = {"FOPEN": 0x400F0830, "FCLOSE": 0x400F06A0, "FREAD": 0x400F0890, "FWRITE": 0x400F09C8,
         "FSEEK": 0x400F098C, "MALLOC": 0x400F1FDC, "DTOI": 0x400EF75C}
# The BIOS part number's "20" (0.6) or "07" (B5) as a halfword at 0x4000_5B18.
ID_ADDRESS, ID_B5 = 0x40005B18, 0x3730

OWN_CODE = r"""
    .align  4
; ---- the stub's own strlen(s) -> length
ll_strlen:
    mov     r1, r0
1:
    ldb.ab  r2, [r1, 1]
    brne    r2, 0, 1b
    sub     r0, r1, r0
    sub     r0, r0, 1
    j_s     [blink]

    .align  4
; ---- double (r0 low, r1 high) -> int, truncated (|x| < 2^31), as libgcc's __fixdfsi
ll_dtoi:
    lsr     r2, r1, 20
    and     r2, r2, 0x7ff
    sub.f   r2, r2, 1023
    blt     3f
    and     r3, r1, 0xfffff
    or      r3, r3, 0x100000
    rsub.f  r4, r2, 20
    blt     1f
    lsr     r0, r3, r4
    b       2f
1:
    rsub    r4, r4, 0
    asl     r3, r3, r4
    rsub    r5, r4, 32
    lsr     r5, r0, r5
    or      r0, r3, r5
2:
    bbit0   r1, 31, 4f
    rsub    r0, r0, 0
4:
    j_s     [blink]
3:
    mov     r0, 0
    j_s     [blink]

    .align  4
ll_s_wplus:
    .asciz  "w+"
ll_s_extstorage:
    .asciz  "ExtStorage"
ll_s_sdmenu:
    .asciz  "SDMenu\\SDMenu.bin"
ll_s_system:
    .asciz  "System"
    .align  4
"""

_MOV = re.compile(r"^(\s*)mov(?:_s)?\s+(r\d+),\s*([A-Za-z_][A-Za-z0-9_]*|0x[0-9A-Fa-f_]+)\s*(;.*)?$")


def portable(src, end_marker=None):
    """`src` with every BIOS 0.6 address it loads rewritten (see above), and the stub's own routines
    and strings appended (before `end_marker` if given, else at the end). Raises if a 0.6 address
    is left in its code."""
    out, n = [], [0]

    def addr(tok):
        if tok in NAMES:
            return NAMES[tok]
        if tok.startswith("0x"):
            return int(tok.replace("_", ""), 16)
        return None

    for line in src.split("\n"):
        # (eestub names them with .equ: every use is rewritten below, so the names go.)
        if re.match(r"\s*\.equ\s+(" + "|".join(NAMES) + r")\s*,", line):
            continue
        m = _MOV.match(line)
        a = addr(m.group(3)) if m else None
        if a in SERVICES:
            ind, r = m.group(1), m.group(2)
            off, slot = SERVICES[a]
            out += [f"{ind}ld      {r}, [gp, 4]", f"{ind}ld      {r}, [{r}, {off:#x}]",
                    f"{ind}ld      {r}, [{r}, {slot:#x}]"]
        elif a in OWN:
            out.append(f"{m.group(1)}mov     {m.group(2)}, {OWN[a]}")
        elif a in PER_BIOS:
            ind, r = m.group(1), m.group(2)
            v06, vb5 = PER_BIOS[a]
            n[0] += 1
            b5, done = f"ll_bios{n[0]}_b5", f"ll_bios{n[0]}_end"
            out += [f"{ind}mov     {r}, {ID_ADDRESS:#x}", f"{ind}ldh     {r}, [{r}]",
                    f"{ind}cmp     {r}, {ID_B5:#x}", f"{ind}beq     {b5}",
                    f"{ind}mov     {r}, {v06:#x}", f"{ind}b       {done}",
                    f"{b5}:", f"{ind}mov     {r}, {vb5:#x}", f"{done}:"]
        else:
            out.append(line)
    text = "\n".join(out)
    if end_marker and end_marker in text:
        text = text.replace(end_marker, OWN_CODE + end_marker, 1)
    else:
        text += OWN_CODE
    # No 0.6-only address may be left in the code (comments may name them).
    code = "\n".join(l.split(";")[0] for l in text.split("\n"))
    left = [m for m in re.findall(r"0x(?:40|3[cC]7[fF])[0-9A-Fa-f_]{6,7}\b", code)
            if int(m.replace("_", ""), 16) not in (ID_ADDRESS,) and int(m.replace("_", ""), 16) not in
            {v for pair in PER_BIOS.values() for v in pair}]
    if left:
        raise ValueError(f"BIOS 0.6 addresses left in a stub: {sorted(set(left))}")
    return text
