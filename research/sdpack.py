"""Prototype of LeapLoader's "prepare for SD" step (research; the product
version will be Rust). Converts a Leapster cartridge image (built for
0x8000_0000) into an image for the Leapster 2 BIOS's SD load (RAM at
0x3C80_0000), by rewriting only fields whose meaning is known, and refuses
images with resource types it does not understand.

Usage: python sdpack.py IN.bin OUT.bin [SAVE_PATH]      (exit 2 = unsupported)

Games with native ARC code (tags 0x1000/0x1009) are relocated with the list that
research/nativescan finds (native_relocs below); without nativescan they are refused.

Format notes: docs/research-report.md and docs/sd-boot-proof.md.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CART_BASE = 0x8000_0000
SD_BASE = 0x3C80_0000
MAX_SIZE = 0x80_0000  # RAM from 0x3C80_0000 to the end of the 16 MiB at 0x3D00_0000
SIGNATURE = b"Copyright LeapFrog"
# Tags whose contents are understood (see the table in docs/sd-boot-proof.md).
KNOWN_TAGS = {0x1003, 0x1005, 0x1006, 0x100C, 0x2000}
# Native code (helper libraries) and its function tables: relocated with nativescan's list.
NATIVE_TAGS = {0x1000, 0x1001, 0x1009, 0x100D, 0x3001}
NATIVESCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nativescan", "target", "release", "nativescan.exe")


class Unsupported(Exception):
    pass


def checksum(d, base):
    """The BIOS's RIB header checksum (0x4005_28A4): one word every 0xF94 bytes, base..end."""
    u = lambda a: struct.unpack_from("<I", d, a - base)[0]
    start, end = u(base + 0x11C), u(base + 0x120)
    s, a = 0, start
    while True:
        s = (s + u(a)) & 0xFFFFFFFF
        a += 0xF94
        if not end >= a:
            return s


def checksum_ok(src):
    """Whether a cartridge dump's stored header checksum matches (False also if unreadable)."""
    try:
        stored = struct.unpack_from("<I", src, struct.unpack_from("<I", src, 0x128)[0] - CART_BASE)[0]
        return checksum(src, CART_BASE) == stored
    except struct.error:
        return False


def repair(src):
    """A dump with dumping-tool text markers removed, if that makes its checksum match; else `src`.
    Seen in Cars Supercharged: "LBK00000014000000018a813" (24 bytes) inserted at 0x40_0000,
    shifting everything after it (VERIFIED: the checksum matches once it is removed)."""
    import re
    if checksum_ok(src):
        return src
    out = bytes(src)
    for m in reversed(list(re.finditer(rb"LBK[0-9a-fA-F]{21}", src))):
        if m.start() % 0x1000 == 0:
            out = out[:m.start()] + out[m.end():] + out[-1:] * 24
    return out if out != src and checksum_ok(out) else src


def native_relocs(path):
    """nativescan's relocation list for the image at `path`: [(offset, kind, value)]."""
    import subprocess
    import tempfile
    exe = os.environ.get("NATIVESCAN", NATIVESCAN)
    if not os.path.exists(exe):
        raise Unsupported("native code, and research/nativescan is not built")
    with tempfile.TemporaryDirectory() as t:
        out = os.path.join(t, "relocs.txt")
        r = subprocess.run([exe, path, "--relocs", out], capture_output=True, text=True)
        if r.returncode != 0:
            raise Unsupported("nativescan failed: " + r.stderr.strip()[-200:])
        report = r.stdout
        if "\nVERDICT ok" not in report:
            raise Unsupported("native code not understood:\n" + report)
        return [(int(o, 16), k, int(v, 16)) for o, k, v in (l.split() for l in open(out) if l.strip())]


def convert(src, save_path=None, relocs=None, strict_checksum=True, menu_name="LeapLoader", app_dir=None):
    """`save_path`: when given (e.g. b:\Leapster\Apps\Game\save.dat), the game's saves go to
    that SD file through saveshim.py; None leaves the save calls as they are (no saves).
    `strict_checksum=False` converts a dump whose header checksum does not match (some dumps never
    had one written: Ni Hao Kai-lan's is erased); the SD image always gets a correct one."""
    d = bytearray(src)
    size = len(d)
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    u16 = lambda o: struct.unpack_from("<H", d, o)[0]
    inside = lambda v: CART_BASE <= v < CART_BASE + size
    off = lambda v: v - CART_BASE
    edits = []  # (offset, old, new) of every rewritten word
    notes = convert.notes = []  # what the caller should tell the user (read as sdpack.convert.notes)

    relocated = set()

    def reloc(o):
        if o in relocated:
            return  # shared (instrument zones used by several programs)
        relocated.add(o)
        v = u32(o)
        if not inside(v):
            raise Unsupported(f"word at {o:#x} ({v:#010x}) expected to point into the image")
        nv = v - CART_BASE + SD_BASE
        struct.pack_into("<I", d, o, nv)
        edits.append((o, v, nv))

    convert.files = {}  # extra files for the game's folder (images over 8 MiB: bigimage.py)
    big = None
    if size > MAX_SIZE:
        import bigimage
        if app_dir is None:
            raise Unsupported(f"{size // 0x100000} MiB image; the SD load area holds at most 8 MiB")
        try:
            big = bigimage.plan(src)
        except bigimage.Unsupported as e:
            raise Unsupported(str(e))
    if d[0x100:0x100 + len(SIGNATURE)] != SIGNATURE:
        raise Unsupported("no RIB header ('Copyright LeapFrog' at 0x100)")
    if u32(0x11C) != CART_BASE:
        raise Unsupported(f"RIB base is {u32(0x11C):#010x}, not the cartridge window")
    stored = u32(off(u32(0x128)))
    if checksum(d, CART_BASE) != stored and strict_checksum:
        raise Unsupported("header checksum does not match: damaged or modified dump")

    for o in (0x11C, 0x120, 0x124, 0x128):
        reloc(o)
    # 0x140 points to the LEAP directory in both layouts (0x8000_0000 when it
    # is at the start of the image, 0x8000_0144 when it follows the header).
    leap = off(u32(0x140))
    reloc(0x140)
    if d[leap:leap + 4] != b"LEAP":
        raise Unsupported("no LEAP resource directory")

    n = u16(leap + 6)
    tags = [u16(leap + 0x20 + 8 * i) for i in range(n)]
    unknown = sorted(set(tags) - KNOWN_TAGS - (NATIVE_TAGS if relocs is not None else set()))
    if unknown:
        raise Unsupported("resource types not understood (native code or unknown data): " + ", ".join(f"{t:#06x}" for t in unknown))

    has_movies = False
    movie_table = main_handle = None
    movie_tables = []
    ee_size = 256
    for i in range(n):
        e = leap + 0x20 + 8 * i
        tag, count, ptr = u16(e), u16(e + 2), u32(e + 4)
        reloc(e + 4)
        for j in range(count):
            s = off(ptr) + 8 * j
            rid, value = u16(s), u32(s + 4)
            if not inside(value):
                continue  # an immediate value
            reloc(s + 4)
            blob = off(value)
            if tag == 0x1006:
                # {version, flags, first handle, count, pointers[count]}: the first
                # handle is a number the game's ActionScript uses, NOT an address.
                n = u32(blob + 12)
                if rid == 2 and u32(blob + 8) == 0x2000:
                    # An instrument bank (as the BIOS's, biosbank2sf2.py): one pointer per
                    # program to 20-byte zones {start, end, loop start/end (low halves, kept),
                    # scale, low key, high key, level}, up to the zone whose high key is 0x7F.
                    for k in range(n):
                        z = u32(blob + 16 + 4 * k)
                        if not inside(z):
                            continue
                        z = off(z)
                        for _ in range(128):
                            for f in (z, z + 4):
                                if inside(u32(f)):
                                    reloc(f)
                            if d[z + 0x11] >= 0x7F:
                                break
                            z += 20
                for k in range(n):
                    e = u32(blob + 16 + 4 * k)
                    if e:  # some tables have empty (null) slots
                        reloc(blob + 16 + 4 * k)
                    # Bitmaps whose header holds the address of their own pixel data a few bytes
                    # in: Scooby-Doo Arcade's table 13 {data = +0x14, 2, width, height, size, ...},
                    # table 16 of Go Diego Go and Schoolhouse Rock {w, h | flags, data = +8, ...}.
                    if inside(e) and off(e) + 0x20 <= size:
                        for h in range(0, 0x20, 4):
                            if e + h < u32(off(e) + h) <= e + 0x20 and (u32(off(e) + h) - e) % 4 == 0:
                                reloc(off(e) + h)
                # Some tables hold a second array of n addresses right after the first (sound
                # tables of Creature Create, Ratatouille, ...: read by the sound hardware).
                second = [blob + 16 + 4 * (n + k) for k in range(n)]
                if n and second[-1] + 4 <= size and all(u32(o) == 0 or inside(u32(o)) for o in second)                         and any(u32(o) for o in second):
                    for o in second:
                        if u32(o):
                            reloc(o)
                if rid == 7:
                    has_movies = True
                    movie_tables.append(blob)
            elif tag == 0x1005 and rid == 3:
                # EEPROM descriptor {0x100, device 1, 4, 0x2000, 0x64, size}: 0x100/0x200/0x800 bytes
                ee_size = u32(blob + 0x14)
                # The long form (NASCAR, Sonic X, Cars, ...): 0, then three functions and a data
                # address of the game's own native code at +0x1C..+0x28.
                if u32(blob + 0x18) == 0:
                    for k in range(0x1C, 0x2C, 4):
                        if inside(u32(blob + k)):
                            reloc(blob + k)
                if ee_size & (ee_size - 1) or not 32 <= ee_size <= 0x10000:
                    ee_size = 256
            elif tag == 0x2000 and rid == 1:  # Talking Words Factory has 0x2000/3 and /5 too
                main_handle = u32(blob + 12)
            # tag 0x2000: {0x00010100, 0, 0, main movie handle}. The handle (e.g.
            # 0x8000_0006) only looks like an address; the system menu plays the SD
            # image's main movie by it ("PlayMovie: Packed RIB Movie(s)"). Unchanged.
    if not has_movies:
        raise Unsupported("no movie table (resource 0x1006/7)")
    # Fonts (resource 0x1006/1, first word 0x0101_0100): pointers to their own name, style and
    # glyph tables. Every word inside a font that points into the same font is one (a font ends
    # where the next known resource starts).
    # Every entry of the font table counts, whatever its first word (Bratz World's is 0x0650_0100),
    # and the last resource of the image ends at the image's end.
    starts = resource_starts(src)
    fonts = font_table_entries(src)
    for k, s0 in enumerate(starts):
        if u32(s0 - CART_BASE) != 0x0101_0100 and s0 not in fonts:
            continue
        s1 = starts[k + 1] if k + 1 < len(starts) else CART_BASE + size
        for o in range(s0 - CART_BASE, s1 - CART_BASE - 3, 4):
            v = struct.unpack_from("<I", src, o)[0]
            if s0 <= v < s1:
                reloc(o)
    # Some games have more than one movie table (Cars: flags 0x100 and 0x101): the one whose
    # handles include the main movie's.
    movie_table = next((t for t in movie_tables if main_handle is not None
                        and 0 <= main_handle - u32(t + 8) < u32(t + 12)), movie_tables[0])
    if relocs is not None:
        done = {e[0] for e in edits}
        limm = set()
        handle_limit = max([0] + [struct.unpack_from("<I", src, t - CART_BASE + 12)[0]
                                      for t in table_addresses(src)
                                      if struct.unpack_from("<I", src, t - CART_BASE + 8)[0] == CART_BASE])
        for o, kind, v in relocs:
            if o in done:
                continue
            # Data words from 0x8000_0000 up to the largest table's handle count (no more: Foster's
            # Home points at 0x8000_00BC, past its 29 handles) are resource handles (0x8000_0000 + index: Go Diego Go's 0x100D lists hold 571, Rock the World's
            # go up to 0x8000_1A1F), not pointers. Handles 0x8000_0000 and 0x8000_0010 are also the
            # addresses of the header and its 0x1001 list, so no exception can be made for those.
            if kind == "word" and v < CART_BASE + handle_limit:
                continue
            if kind == "word":
                old = u32(o)
            else:  # ARCompact long immediate: high halfword first
                old = u16(o) << 16 | u16(o + 2)
            if old != v or not inside(v):
                raise Unsupported(f"native relocation at {o:#x}: found {old:#010x}, expected {v:#010x}")
            nv = v - CART_BASE + SD_BASE
            if kind == "word":
                struct.pack_into("<I", d, o, nv)
            else:
                struct.pack_into("<HH", d, o, nv >> 16, nv & 0xFFFF)
                limm.add(o)
            edits.append((o, v, nv))

    if big is not None:
        import bigimage
        try:
            d, edits, remap = bigimage.compact(d, edits, limm if relocs is not None else set(), big)
        except bigimage.Unsupported as e:
            raise Unsupported(str(e))
        movie_table = remap(movie_table)
        slots_at = MAX_SIZE - big.get("reserved", big["nslots"] * big["slot"])  # slots (+ sound ring)
        d = d[:u32(0x120) - SD_BASE + 12]  # nothing after the trailer belongs to the image
        if len(d) > slots_at:
            raise Unsupported("the image does not fit below the slots")
        d = d[:slots_at] + bytes([0xFF]) * max(0, slots_at - len(d))
        convert.files = bigimage.install(d, src, big, app_dir, remap, edits)
        notes.append(f"{len(convert.files)} files stay on the card, loaded when used: " + ", ".join(sorted(convert.files)))
    if save_path is not None:
        pointers = {v for _, v, _ in edits}
        try:
            add_saves(d, movie_table, main_handle, ee_size, save_path, pointers, native=relocs is not None,
                      menu_name=menu_name)
        except Unsupported as e:
            if relocs is None or "no free space" not in str(e):
                raise
            # No room for the main-movie copy: the all-native chip (HINT + A + B without a prompt).
            add_native_chip(d, ee_size, save_path, pointers)
            notes.append("saves through the native chip (save.bin); HINT + A + B without an on-screen prompt")
    if big is not None:
        # The file ends after the last byte in use; the slots above it stay out of the load.
        end = len(d)
        while end > 0 and d[end - 1] == 0xFF:
            end -= 1
        end = max((end + 3) & ~3, u32(0x120) - SD_BASE + 12)
        d = d[:end]
    struct.pack_into("<I", d, u32(0x128) - SD_BASE, checksum(d, SD_BASE))
    return bytes(d), edits


def relocs_for(path, src):
    """nativescan's list when the image has native code, else None."""
    leap = struct.unpack_from("<I", src, 0x140)[0] - CART_BASE
    n = struct.unpack_from("<H", src, leap + 6)[0]
    tags = {struct.unpack_from("<H", src, leap + 0x20 + 8 * i)[0] for i in range(n)}
    return native_relocs(path) if tags & NATIVE_TAGS else None


FLUSH_DEPTH = 16000  # display depth of the save flusher clip (far above what games use)
AS_SHIM = os.environ.get("LL_AS_SHIM") == "1"  # Flash-only games: the old ActionScript save shim (add_saves)


def free_space(d, need, pointers):
    """Offset of `need` bytes of padding: after the image's end if there is room, else in the
    largest run of 0xFF that no known pointer reaches into, 4 KiB in from both ends."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    end = (u32(0x120) - SD_BASE + 16 + 3) & ~3
    if need <= len(d) - end and len(set(d[end:end + need])) <= 1:
        return end
    import re
    margin = 4096
    pad = re.compile(b"[\xff]{%d,}" % (need + 2 * margin))
    runs = sorted(((m.end() - m.start(), m.start()) for m in pad.finditer(bytes(d))), reverse=True)
    for length, start in runs:
        # A window at the run's start, or at its end (a resource may end where the run begins).
        for at in (start + margin, start + length - margin - need):
            at = (at + 3) & ~3
            lo, hi = SD_BASE + at - margin, SD_BASE + at + need + margin
            if not any(lo <= p - CART_BASE + SD_BASE < hi for p in pointers):
                return at
    raise Unsupported("no free space in the image for the save-enabled main movie")


def add_saves(d, movie_table, main_handle, ee_size, save_path, pointers=(), native=False, menu_name="LeapLoader"):
    """Saves for SD: a RAM save chip (eestub.py) behind the BIOS's EEPROM interface, added as one
    more 0x1009 resource (with a directory entry of its own when the game has no 0x1009 list),
    and a copy of the main movie that installs it (saveshim.build_ee_loader) and runs the
    HINT + A + B watcher. The stub reads and writes the save file itself.
    `native`: the game has native code (only it needs the RAM chip; Flash-only games could use
    the ActionScript shim instead, see AS_SHIM).
    AS_SHIM (LL_AS_SHIM=1): Flash-only games as before 2026-10-25: their cartridge-memory natives
    renamed to same-length paths of the ActionScript shim's functions (saveshim.py), which read the
    save file byte by byte at start (1st Grade: the title ~4-5 s later than without saves)."""
    import eestub
    import ingame
    import saveshim
    import swfgen
    from swfgen import do_action
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    first, count = u32(movie_table + 8), u32(movie_table + 12)
    movies = [u32(movie_table + 16 + 4 * k) - SD_BASE for k in range(count)]
    index = main_handle - first
    overlay_handle = first + count  # the HINT + A + B prompt, appended to the table below
    if not 0 <= index < count:
        raise Unsupported(f"main movie handle {main_handle:#x} not in the movie table")
    chip = native or not AS_SHIM
    for o in sorted(set(movies)) if not chip else ():
        seg = d[o:o + u32(o + 4)]
        for f in saveshim.FLOAT_NATIVES:
            if f.encode() + b"\0" in seg:
                raise Unsupported(f"the game saves floats ({f}); saves for it are not supported yet")
    renamed = 0
    for o in sorted(set(movies)) if not chip else ():
        ln = u32(o + 4)
        seg = bytes(d[o:o + ln])
        for old, new in saveshim.rename_map().items():
            renamed += seg.count(old + b"\0")
            seg = seg.replace(old + b"\0", new + b"\0")
        d[o:o + ln] = seg
    # The main movie, with a DoAction (the shim) first after the header.
    mo = movies[index]
    m = bytes(d[mo:mo + u32(mo + 4)])
    nbits = m[8] >> 3
    hdr_end = 8 + (5 + 4 * nbits + 7) // 8 + 4
    used = swfgen.swf_define_ids(m)
    sprite_id = next(i for i in range(0xFFF0, 0x8000, -1) if i not in used)
    # Every frame, the clip writes pending saves and runs the HINT + PAUSE watcher (ingame.py).
    flusher = saveshim.build_ee_flusher if chip else lambda: saveshim.build_flusher(ee_size)
    every_frame = flusher()
    every_frame.code.extend(swfgen.AS().call("_level0:__llTick").op("pop").code)
    first = saveshim.build_ee_loader(save_path, ee_size) if chip else saveshim.build_shim(save_path, ee_size)
    inject = (do_action(first)
              + do_action(ingame.build_watcher(saveshim.build_ee_flusher(True) if chip else flusher(), overlay_handle, poll=chip))
              + swfgen.define_sprite(sprite_id, [swfgen.show_frame()])
              + swfgen.place_enterframe(FLUSH_DEPTH, sprite_id, every_frame))
    m2 = bytearray(m[:hdr_end] + inject + m[hdr_end:])
    struct.pack_into("<I", m2, 4, len(m2))

    # Lay out the free space after the image: the new main movie, the overlay movie, and a
    # copy of the movie table with the overlay as one more movie (handle first + count; the
    # 0x1006 entry then points at the copy). A table of its own for the overlay was not always
    # found: the overlay never loaded in Cars, I Spy Challenger, Creature Create (VERIFIED-EMU).
    overlay = ingame.build_overlay(menu_name)
    entry, count_1006, list_1006 = find_dir_entry(d, 0x1006)
    table_len = 16 + 4 * (count + 1)
    # Then the RAM chip stub and a copy of the 0x1009 list with it added (and, for a game without
    # a 0x1009 list, a copy of the resource directory with an entry for it).
    leap = u32(0x140) - SD_BASE
    n_dir = struct.unpack_from("<H", d, leap + 6)[0]
    has_1009 = any(struct.unpack_from("<H", d, leap + 0x20 + 8 * i)[0] == 0x1009 for i in range(n_dir))
    stub_len = len(eestub.build(SD_BASE, ee_size, save_path)) if chip else 0
    n_1009 = find_dir_entry(d, 0x1009)[1] if chip and has_1009 else 0
    dir_len = 0 if has_1009 else 0x20 + 8 * (n_dir + 1) + 4
    size = lambda at: ((((at + len(m2) + 3) & ~3) + len(overlay) + 3) & ~3) + table_len - at \
        + (stub_len + 8 * (n_1009 + 1) + 8 + dir_len if chip else 0)
    at = free_space(d, size(0) + 16, pointers)
    o_at = (at + len(m2) + 3) & ~3
    t_at = (o_at + len(overlay) + 3) & ~3
    if chip:
        s_at = (t_at + table_len + 3) & ~3
        stub = eestub.build(SD_BASE + s_at, ee_size, save_path)
        d[s_at:s_at + len(stub)] = stub
        n_at = (s_at + len(stub) + 3) & ~3
        if has_1009:
            e9, c9, list9 = find_dir_entry(d, 0x1009)
            d[n_at:n_at + 8 * c9] = d[list9:list9 + 8 * c9]
            struct.pack_into("<HHI", d, n_at + 8 * c9, 5, 0x200, SD_BASE + s_at)
            struct.pack_into("<HHI", d, e9, 0x1009, c9 + 1, SD_BASE + n_at)
        else:
            # A Flash-only game: the directory moves to a copy with a 0x1009 entry (one list
            # entry: the stub), in tag order as the others; the header's pointer (0x140) follows.
            struct.pack_into("<HHI", d, n_at, 5, 0x200, SD_BASE + s_at)
            entries = [struct.unpack_from("<HHI", d, leap + 0x20 + 8 * i) for i in range(n_dir)]
            entries.append((0x1009, 1, SD_BASE + n_at))
            entries.sort(key=lambda e: e[0])
            dir_at = (n_at + 8 + 3) & ~3
            d[dir_at:dir_at + 0x20] = d[leap:leap + 0x20]
            struct.pack_into("<H", d, dir_at + 6, n_dir + 1)
            for i, e in enumerate(entries):
                struct.pack_into("<HHI", d, dir_at + 0x20 + 8 * i, *e)
            struct.pack_into("<I", d, 0x140, SD_BASE + dir_at)
    d[at:at + len(m2)] = m2
    d[o_at:o_at + len(overlay)] = overlay
    d[t_at:t_at + 16 + 4 * count] = d[movie_table:movie_table + 16 + 4 * count]
    struct.pack_into("<I", d, t_at + 12, count + 1)
    struct.pack_into("<I", d, t_at + 16 + 4 * count, SD_BASE + o_at)
    struct.pack_into("<I", d, t_at + 16 + 4 * index, SD_BASE + at)
    pointed = [k for k in range(count_1006) if struct.unpack_from("<HHI", d, list_1006 + 8 * k)[0] == 7
               and struct.unpack_from("<I", d, list_1006 + 8 * k + 4)[0] == SD_BASE + movie_table]
    if len(pointed) != 1:
        raise Unsupported("the main movie table is not in the 0x1006 list once")
    struct.pack_into("<I", d, list_1006 + 8 * pointed[0] + 4, SD_BASE + t_at)
    return renamed


def resource_starts(src):
    """Sorted cartridge addresses where resources start: directory blobs and the entries of
    every 0x1006 table (both arrays where there are two)."""
    u32 = lambda o: struct.unpack_from("<I", src, o)[0]
    u16 = lambda o: struct.unpack_from("<H", src, o)[0]
    inside = lambda v: CART_BASE <= v < CART_BASE + len(src)
    leap = u32(0x140) - CART_BASE
    out = set()
    for i in range(u16(leap + 6)):
        tag, count, lst = struct.unpack_from("<HHI", src, leap + 0x20 + 8 * i)
        for j in range(count):
            v = u32(lst - CART_BASE + 8 * j + 4)
            if not inside(v):
                continue
            out.add(v)
            if tag == 0x1006:
                o = v - CART_BASE
                for k in range(2 * u32(o + 12)):
                    if o + 16 + 4 * k + 4 <= len(src) and inside(u32(o + 16 + 4 * k)):
                        out.add(u32(o + 16 + 4 * k))
    return sorted(out)


def table_addresses(src):
    """Cartridge addresses of the image's 0x1006 tables."""
    u32 = lambda o: struct.unpack_from("<I", src, o)[0]
    u16 = lambda o: struct.unpack_from("<H", src, o)[0]
    leap = u32(0x140) - CART_BASE
    out = []
    for i in range(u16(leap + 6)):
        tag, count, lst = struct.unpack_from("<HHI", src, leap + 0x20 + 8 * i)
        if tag == 0x1006:
            out += [struct.unpack_from("<I", src, lst - CART_BASE + 8 * j + 4)[0] for j in range(count)]
    return [t for t in out if CART_BASE <= t < CART_BASE + len(src)]


def font_table_entries(src):
    """Cartridge addresses of the fonts listed in resource 0x1006/1."""
    u32 = lambda o: struct.unpack_from("<I", src, o)[0]
    u16 = lambda o: struct.unpack_from("<H", src, o)[0]
    inside = lambda v: CART_BASE <= v < CART_BASE + len(src)
    leap = u32(0x140) - CART_BASE
    out = set()
    for i in range(u16(leap + 6)):
        tag, count, lst = struct.unpack_from("<HHI", src, leap + 0x20 + 8 * i)
        if tag != 0x1006:
            continue
        for j in range(count):
            rid, _, v = struct.unpack_from("<HHI", src, lst - CART_BASE + 8 * j)
            if rid == 1 and inside(v):
                o = v - CART_BASE
                out.update(p for p in (u32(o + 16 + 4 * k) for k in range(u32(o + 12))) if inside(p))
    return out


def gap(d, need, pointers, margin=256):
    """Offset of `need` bytes inside a run of 0xFF or 0x00 (padding) that no known pointer reaches
    into, `margin` bytes in from both ends; the runs before the image's trailer and after its end
    are the usual ones."""
    import re
    runs = sorted(((m.end() - m.start(), m.start()) for m in re.finditer(rb"(\xff|\x00)\1{%d,}" % (need + 2 * margin - 1), bytes(d))),
                  reverse=True)
    for length, start in runs:
        for at in (start + margin, start + length - margin - need):
            at = (at + 3) & ~3
            lo, hi = SD_BASE + at - margin, SD_BASE + at + need + margin
            if at >= start and at + need <= start + length and not any(lo <= p - CART_BASE + SD_BASE < hi for p in pointers):
                return at
    raise Unsupported("no free space in the image for the native save chip")


def add_native_chip(d, ee_size, save_path, pointers):
    """nativechip.py: every function pointer of the game's 0x1009 lists goes through a trampoline
    that installs the chip once. The chip saves to save.bin next to `save_path`."""
    import nativechip
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    inside = lambda v: SD_BASE <= v < SD_BASE + len(d)
    _, count, lst = find_dir_entry(d, 0x1009)
    slots = []
    for j in range(count):
        blob = u32(lst + 8 * j + 4)
        if not inside(blob):
            continue
        b = blob - SD_BASE
        n, pairs = u32(b + 8) >> 16, u32(b + 12)
        if u32(b) != 0x100 or not inside(pairs):
            continue
        for k in range(n):
            o = pairs - SD_BASE + 8 * k + 4
            if inside(u32(o)):
                slots.append(o)
    if not slots:
        raise Unsupported("no named natives to install the save chip from")
    path = save_path[:-len("save.dat")] + "save.bin" if save_path.endswith("save.dat") else save_path + ".bin"
    originals = [u32(o) for o in slots]
    size = len(nativechip.build(SD_BASE, ee_size, path, originals)[0])
    at = gap(d, size, pointers)
    code, tramps = nativechip.build(SD_BASE + at, ee_size, path, originals)
    d[at:at + len(code)] = code
    for o, t in zip(slots, tramps):
        struct.pack_into("<I", d, o, t)


def find_dir_entry(d, tag):
    """(offset of the LEAP directory entry, its count, offset of its sub-entry list)."""
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    leap = u32(0x140) - SD_BASE
    for i in range(struct.unpack_from("<H", d, leap + 6)[0]):
        e = leap + 0x20 + 8 * i
        t, c, p = struct.unpack_from("<HHI", d, e)
        if t == tag:
            return e, c, p - SD_BASE
    raise Unsupported(f"no {tag:#06x} resources")


if __name__ == "__main__":
    src = open(sys.argv[1], "rb").read()
    save = sys.argv[3] if len(sys.argv) > 3 else None
    try:
        out, edits = convert(src, save, relocs_for(sys.argv[1], src))
    except Unsupported as e:
        print(f"UNSUPPORTED: {e}")
        sys.exit(2)
    open(sys.argv[2], "wb").write(out)
    print(f"OK: {len(edits)} words relocated")
