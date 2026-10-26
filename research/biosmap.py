"""Research tool: finds where a BIOS 0.6 address's code or data lives in another Leapster 2 BIOS
(Connected B5 152-12076, CIP3 m9 152-12659), by its bytes.

Usage: python biosmap.py OTHER_BIOS.bin [ADDRESS ...]   (default: every address the stubs use)

For each 0.6 address, windows of its bytes (growing from 8 up to 64, starting at the address and a
little before it) are looked for in the other BIOS; a window found exactly once gives the address
there. ARC code has PC-relative branches and absolute long immediates that differ between the builds,
so a short unique window may be needed; every answer is printed with the window length, and an
address with no unique window is reported as not found (to be checked by hand, e.g. with objdump).
"""
import os
import sys

B = 0x4000_0000
HERE = os.path.dirname(os.path.abspath(__file__))
BIOS06 = os.path.join(HERE, "..", "..", "Ribbit", "roms", "bios", "leapster2", "152-12206_0.6.bin")

# Every BIOS address the stubs call or read (eestub, nativechip, streamstub, sdboot-emu's log hook),
# with what it is (BIOS 0.6).
ADDRESSES = {
    0x4004_2F98: "BootSystem log (printf-like, sdboot-emu)",
    0x4002_2AA8: "write PlayGame.lnk and restart (BT_StartSDMenu's helper)",
    0x4002_2C8C: "BT_StartSDMenu",
    0x400F_0674: "LC_Boot thunk",
    0x400F_06A0: "fclose thunk",
    0x400F_0830: "fopen thunk",
    0x400F_0890: "fread thunk",
    0x400F_098C: "fseek thunk (streamstub)",
    0x400F_09C8: "fwrite thunk",
    0x400F_16C8: "path builder (folder, name)",
    0x400F_1724: "PlayGame.lnk path builder",
    0x400F_1FDC: "malloc thunk",
    0x400E_839C: "strlen",
    0x400E_F75C: "double to int",
    0x4009_5FA4: "to-number (streamstub)",
    0x400A_0EA8: "lfh native (streamstub)",
    0x400A_2F54: "LF_PlayLFC native (streamstub)",
    0x4010_3E68: "streamstub data",
    0x400F_78F8: 'string "w+"',
    0x400F_78FC: 'string "ExtStorage"',
    0x400F_792C: 'string "SDMenu\\SDMenu.bin"',
}


def find(a06, other, addr):
    """(address in other, window length) or None."""
    o = addr - B
    for back in (0, 4, 8, 16):
        for length in (8, 12, 16, 20, 24, 32, 48, 64):
            w = a06[o - back:o - back + length]
            if len(w) < length:
                continue
            i = other.find(w)
            if i != -1 and other.find(w, i + 1) == -1:
                return B + i + back, length
    return None


def main():
    other = open(sys.argv[1], "rb").read()
    a06 = open(BIOS06, "rb").read()
    addrs = [int(a, 16) for a in sys.argv[2:]] or list(ADDRESSES)
    for a in addrs:
        r = find(a06, other, a)
        what = ADDRESSES.get(a, "")
        print(f"{a:#010x} -> " + (f"{r[0]:#010x} (window {r[1]})" if r else "NOT FOUND") + f"  {what}")


if __name__ == "__main__":
    main()
