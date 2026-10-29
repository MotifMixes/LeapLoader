"""Wraps a homebrew app's native code (an SDK build's code.bin, sdk/) into a Leapster 2 SD image.

The image (swfgen.pack_rib: LEAP directory, RIB header, one movie) has a main movie whose first
frame calls the native __llapp(); code.bin, linked at 0x3C80_0000 + CODE_OFFSET (sdk/link.ld),
follows at CODE_OFFSET, with a 0x1009 resource pointing at its native list (sdk/entry.S `blob`).
The approval fields are a cartridge's (swfgen.approval_fields), as the menu's: mkcard takes them
from a game on the same card. Done first for the NES emulator port (2026-10-28).
"""
import struct

from swfgen import AS, SD_BASE, do_action, pack_rib, show_frame, swf

CODE_OFFSET = 0x1_0000
MAX_IMAGE = 0x80_0000
NATIVE = "__llapp"


def build(code, approval, title="Homebrew", native=NATIVE):
    movie = swf([do_action(AS().call(native).op("pop")), show_frame()])
    img = bytearray(pack_rib([movie], title=title[:32], approval=approval))
    end_off = struct.unpack_from("<I", img, 0x120)[0] - SD_BASE
    del img[end_off:]
    if end_off + 16 > CODE_OFFSET:
        raise ValueError("the movie part is too long for CODE_OFFSET")
    # the 0x1009 sub-entry list just before the code: (id 5, 0x200, the code's native list)
    img.extend(b"\0" * (CODE_OFFSET - 16 - len(img)))
    list_at = len(img)
    img.extend(struct.pack("<HHI", 5, 0x200, SD_BASE + CODE_OFFSET) + b"\0" * 8)
    img.extend(code)
    # directory: the 0x1009 entry in tag order (pack_rib wrote 0x1003, 0x1006, 0x2000)
    n = struct.unpack_from("<H", img, 6)[0]
    entries = [struct.unpack_from("<HHI", img, 0x20 + 8 * i) for i in range(n)]
    entries.append((0x1009, 1, SD_BASE + list_at))
    entries.sort(key=lambda e: e[0])
    assert 0x20 + 8 * len(entries) <= 0x100
    struct.pack_into("<H", img, 6, len(entries))
    for i, e in enumerate(entries):
        struct.pack_into("<HHI", img, 0x20 + 8 * i, *e)
    # RIB header end pointers and checksum, as pack_rib
    end_off = (len(img) + 3) & ~3
    img.extend(b"\0" * (end_off - len(img) + 16))
    struct.pack_into("<III", img, 0x120, SD_BASE + end_off, SD_BASE + end_off + 8, SD_BASE + end_off + 4)
    s, a = 0, SD_BASE
    while True:
        s = (s + struct.unpack_from("<I", img, a - SD_BASE)[0]) & 0xFFFFFFFF
        a += 0xF94
        if not SD_BASE + end_off >= a:
            break
    struct.pack_into("<I", img, end_off + 4, s)
    if len(img) > MAX_IMAGE:
        raise ValueError("code.bin makes the image larger than 8 MiB")
    return bytes(img)
