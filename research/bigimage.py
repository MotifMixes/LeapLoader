"""Prototype (research): cartridge images larger than the SD load area (8 MiB at 0x3C80_0000).

Idea: the biggest resources stay on the card as files next to game.bin, and are read into a RAM
slot at the top of the load area just before the game uses them.

Videos played by a native PEG app (Schoolhouse Rock America Rock, Grammar Rock): see plan_peg.

Movies loaded with getURL(lfh(handle), "_levelN") (Talking Words Factory's 8 stories):
* the movies are cut out of the image, and every pointer after them moved down (`compact`);
* each becomes a file `m<index>.bin`;
* the name `lfh` in the remaining movies' ActionScript is renamed to the same-length native `llZ`
  (streamstub.py). llZ converts its argument with the BIOS's own to-number routine, and when that
  is one of the external handles reads its file into a slot and points the movie table at it;
  then it jumps to the BIOS's lfh, so the result is what lfh would have returned;
* two slots, used in turn, so the movie playing now is never overwritten by the next one
  (Talking Words Factory loads every story into _level1: at most the old and the new are alive).
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CART_BASE = 0x8000_0000
SD_BASE = 0x3C80_0000
MAX_SIZE = 0x80_0000
RESERVE = 0x8_0000      # kept free in the image for the save code, the overlay and the loader
CUT_ALIGN = 0x1000      # cuts are whole 4 KiB blocks: everything after keeps its alignment
SLOT_ALIGN = 0x1000


class Unsupported(Exception):
    pass


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def resource_end(src, start):
    import sdpack
    nxt = [s for s in sdpack.resource_starts(src) if s > start]
    return min(nxt) if nxt else CART_BASE + len(src)


def plan(src):
    """How to fit an image over 8 MiB: videos played by a PEG app (plan_peg), else movies."""
    try:
        return plan_peg(src)
    except Unsupported:
        pass
    try:
        return plan_movies(src)
    except Unsupported as e:
        try:
            return plan_pool(src)
        except Unsupported as e2:
            raise Unsupported(f"{e}; {e2}")


def plan_movies(src):
    """Which movies to keep outside the image: {"movies": [(table entry offset, handle, start, length)],
    "slot": slot size, "nslots": 2}. Raises Unsupported if the image cannot be made to fit."""
    import sdpack
    leap = _u32(src, 0x140) - CART_BASE
    movies = []
    for i in range(struct.unpack_from("<H", src, leap + 6)[0]):
        tag, count, lst = struct.unpack_from("<HHI", src, leap + 0x20 + 8 * i)
        if tag != 0x1006:
            continue
        for j in range(count):
            rid, _, v = struct.unpack_from("<HHI", src, lst - CART_BASE + 8 * j)
            if rid != 7 or not CART_BASE <= v < CART_BASE + len(src):
                continue
            t = v - CART_BASE
            first, n = _u32(src, t + 8), _u32(src, t + 12)
            if first != 0x8000_0000:
                continue
            for k in range(n):
                p = _u32(src, t + 16 + 4 * k)
                if CART_BASE <= p < CART_BASE + len(src) and src[p - CART_BASE:p - CART_BASE + 3] == b"FWS":
                    movies.append((t + 16 + 4 * k, first + k, p - CART_BASE, _u32(src, p - CART_BASE + 4)))
    main = _main_handle(src)
    # Largest first; never the main movie, nor one listed twice.
    seen = {}
    for m in movies:
        seen.setdefault(m[2], []).append(m)
    cands = sorted((m for m in movies if len(seen[m[2]]) == 1 and m[1] != main), key=lambda m: -m[3])
    end = _u32(src, 0x120) - CART_BASE + 12
    # Movies alone first (the games that fit that way keep their sounds), then sounds too.
    for lfc in (None, plan_lfc(src)):
        extra = lfc["cut"] if lfc else 0
        ring = lfc["ring"] if lfc else 0
        chosen = []
        for m in cands:
            if m[3] < 0x4_0000:
                break
            chosen.append(m)
            cut = sum((c[3] // CUT_ALIGN) * CUT_ALIGN for c in chosen) + extra
            slot = (max(c[3] for c in chosen) + SLOT_ALIGN - 1) & ~(SLOT_ALIGN - 1)
            if end - cut + 2 * slot + ring + RESERVE <= MAX_SIZE:
                return {"mode": "lfh", "movies": sorted(chosen, key=lambda m: m[2]), "slot": slot, "nslots": 2,
                        "lfc": lfc, "reserved": 2 * slot + ring}
    raise Unsupported(f"{len(src) // 0x100000} MiB image: moving its movies and sounds to the card does not make it fit")


LFC_RING = 0x4_0000  # sounds read from the card go round this buffer (the longest clip is ~37 KB)
POOL_MOVIE_MIN = 0x8000  # pool mode: movies from this size go to the card
POOL_MIN = 0x20_0000     # pool mode: the least room for the movies loaded at the same time


def _movies(src):
    """[(table entry offset, handle, start, length)] of the movies in tables whose handles start
    at 0x8000_0000."""
    out = []
    for t in _tables(src).values():
        first, n = _u32(src, t + 8), _u32(src, t + 12)
        for k in range(n):
            p = _u32(src, t + 16 + 4 * k)
            if CART_BASE <= p < CART_BASE + len(src) and src[p - CART_BASE:p - CART_BASE + 3] == b"FWS":
                out.append((t + 16 + 4 * k, first + k, p - CART_BASE, _u32(src, p - CART_BASE + 4)))
    return out


def plan_pool(src):
    """Story Explorers: movies are loaded by GetURL2(handle, "_level" + N) from handles kept in
    variables, several levels at once. Every such GetURL2 is patched (avm1patch.level_loads) to call
    the native loader first, which reads the movie from m.bin into a pool (streamstub.build_pool);
    the LF_PlayLFC sounds go to s.bin (plan_lfc)."""
    import avm1patch
    import streamstub
    movies = _movies(src)
    for _, _, p, ln in movies:
        try:
            _, other = avm1patch.level_loads(src[p:p + ln], streamstub.NAME_LEVEL, streamstub.NAME_URL)
        except avm1patch.Unsupported as e:
            raise Unsupported(f"pool mode: {e}")
        if other:
            raise Unsupported(f"pool mode: the movie at {p:#x} loads movies in a way not handled")
    main = _main_handle(src)
    seen = {}
    for m in movies:
        seen.setdefault(m[2], []).append(m)
    chosen = [m for m in movies if len(seen[m[2]]) == 1 and m[1] != main and m[3] >= POOL_MOVIE_MIN]
    lfc = plan_lfc(src)
    end = _u32(src, 0x120) - CART_BASE + 12
    cut = sum((m[3] // CUT_ALIGN) * CUT_ALIGN for m in chosen) + (lfc["cut"] if lfc else 0)
    ring = lfc["ring"] if lfc else 0
    pool = (MAX_SIZE - (end - cut) - RESERVE - ring) & ~(SLOT_ALIGN - 1)
    if pool < POOL_MIN or pool < max(m[3] for m in chosen):
        raise Unsupported(f"pool mode: {pool // 1024} KiB left for movies")
    return {"mode": "pool", "movies": sorted(chosen, key=lambda m: m[2]), "lfc": lfc, "pool": pool,
            "slot": 0, "nslots": 0, "reserved": pool + ring}


def plan_lfc(src):
    """The sound clips of table 4 (played by LF_PlayLFC), cut out in whole 4 KiB blocks of the runs
    they fill: {"cuts": [(start, end)], "clips": {entry offset: (handle index, start, length)},
    "cut": bytes cut, "ring": ring size}, or None."""
    import sdpack
    t = _sound_table(src)
    if t is None or b"LF_PlayLFC\x00" not in src:
        return None
    starts = sorted(set(s - CART_BASE for s in sdpack.resource_starts(src)))
    entries = {}
    for k in range(_u32(src, t + 12)):
        p = _u32(src, t + 16 + 4 * k)
        if CART_BASE <= p < CART_BASE + len(src):
            entries[t + 16 + 4 * k] = (k, p - CART_BASE)
    clip_starts = {p for _, p in entries.values()}
    # Runs: consecutive resources that are all clips. A clip ends where the next one starts; the
    # last of a run has no known end (clips carry no length, and the resource list can miss
    # what follows), so it stays in the image and the cut stops at its start.
    cuts, run, length = [], [], {}
    for s in starts + [len(src)]:
        if s in clip_starts:
            run.append(s)
            continue
        for x, y in zip(run, run[1:]):
            length[x] = y - x
        if len(run) > 1:
            a = run[0]
            b = a + ((run[-1] - a) // CUT_ALIGN) * CUT_ALIGN
            if b > a:
                cuts.append((a, b))
        run = []
    inside = lambda p: any(a <= p < b for a, b in cuts)
    clips = {e: (k, p, length[p]) for e, (k, p) in entries.items() if inside(p)}
    if not clips:
        return None
    return {"cuts": cuts, "clips": clips, "cut": sum(b - a for a, b in cuts), "ring": LFC_RING}


def _main_handle(src):
    leap = _u32(src, 0x140) - CART_BASE
    for i in range(struct.unpack_from("<H", src, leap + 6)[0]):
        tag, count, lst = struct.unpack_from("<HHI", src, leap + 0x20 + 8 * i)
        if tag == 0x2000:
            v = _u32(src, lst - CART_BASE + 4)
            return _u32(src, v - CART_BASE + 12)
    return None


def compact(d, edits, limm, big):
    """Cut the planned movies out of `d` (an image relocated in place, layout as the cartridge's).
    Returns (new image, new edits, map: old offset -> new offset or None)."""
    lfc = big.get("lfc")
    cuts = sorted([(s, s + (length // CUT_ALIGN) * CUT_ALIGN) for _, _, s, length in big["movies"]] +
                  (lfc["cuts"] if lfc else []))
    starts = [c[0] for c in cuts]

    def m(o):
        shift = 0
        for a, b in cuts:
            if o < a:
                break
            if o < b:
                return None
            shift += b - a
        return o - shift

    out = bytearray()
    prev = 0
    for a, b in cuts:
        out += d[prev:a]
        prev = b
    out += d[prev:]
    ext_entries = {e for e, _, _, _ in big["movies"]} | (set(lfc["clips"]) if lfc else set())
    new_edits = []
    for o, v, nv in edits:
        no = m(o)
        if no is None:
            raise Unsupported(f"a pointer at {o:#x} lies in a movie that goes to the card")
        t = v - CART_BASE
        nt = m(t)
        if nt is None or o in ext_entries:
            if o in ext_entries:
                continue  # set by the loader
            if o not in limm:
                # A data word nativescan only took for a pointer (America Rock: 0x8084_2402 at
                # 0x7CE78, odd, into the middle of a video): its original value goes back.
                struct.pack_into("<I", out, no, v)
                continue
            raise Unsupported(f"the code at {o:#x} points into a resource that goes to the card ({v:#010x})")
        val = SD_BASE + nt
        if o in limm:
            struct.pack_into("<HH", out, no, val >> 16, val & 0xFFFF)
        else:
            struct.pack_into("<I", out, no, val)
        new_edits.append((no, CART_BASE + nt, val))
    return out, new_edits, m


def rename_lfh(movie):
    """'lfh' -> 'llZ' wherever it is a whole ActionScript string (constant pools, pushes)."""
    return re.sub(rb"(?<![A-Za-z0-9_$.:])lfh\x00", b"llZ\x00", movie)


def install(d, src, big, app_dir, m, edits):
    if big["mode"] == "peg":
        return install_peg(d, src, big, app_dir, m, edits)
    if big["mode"] == "pool":
        return install_pool(d, src, big, app_dir, m, edits)
    return install_lfh(d, src, big, app_dir, m, edits)


def install_pool(d, src, big, app_dir, m, edits):
    """Pool mode (plan_pool): m.bin (the movies, their GetURL2s patched), s.bin (the sounds), the
    natives llL/llU (and LL_PlayLFC), patched copies of the movies kept in the image."""
    import avm1patch
    import sdpack
    import streamstub
    pointers = {v for _, v, _ in edits}
    lfc = big["lfc"]
    ring = SD_BASE + MAX_SIZE - (lfc["ring"] if lfc else 0)
    pool = ring - big["pool"]

    def patched(swf):
        ins, _ = avm1patch.level_loads(swf, streamstub.NAME_LEVEL, streamstub.NAME_URL)
        out = avm1patch.patch_swf(swf, ins) if ins else swf
        return rename_playlfc(out) if lfc else out

    at = sdpack.free_space(d, len(streamstub.STUB_SWF) + 64, pointers)
    d[at:at + len(streamstub.STUB_SWF)] = streamstub.STUB_SWF
    stub = SD_BASE + at
    out_ids = {e for e, _, _, _ in big["movies"]}
    data, recs = bytearray(), {}
    for e, handle, p, ln in big["movies"]:
        swf = patched(bytes(src[p:p + ln]))
        recs[handle - 0x8000_0000] = (SD_BASE + m(e), len(data), len(swf))
        data += swf + bytes(-len(swf) % 16)
        struct.pack_into("<I", d, m(e), stub)  # until loaded: the empty movie
    # Movies left in the image: a patched copy if they load movies, else the rename in place.
    for e, handle, p, ln in _movies(src):
        if e in out_ids:
            continue
        o = _u32(d, m(e)) - SD_BASE
        swf = patched(bytes(d[o:o + ln]))
        if len(swf) == ln:
            d[o:o + ln] = swf
        else:
            at = sdpack.free_space(d, len(swf) + 64, pointers)
            d[at:at + len(swf)] = swf
            struct.pack_into("<I", d, m(e), SD_BASE + at)
    n = max(recs) + 1
    rec_list = [recs.get(k, (0, 0, 0)) for k in range(n)]
    path = app_dir + "\\m.bin"
    size = len(streamstub.build_pool(SD_BASE, path, rec_list, pool, ring, stub))
    at = sdpack.free_space(d, size + 64, pointers)
    code = streamstub.build_pool(SD_BASE + at, path, rec_list, pool, ring, stub)
    d[at:at + len(code)] = code
    add_native_resource(d, SD_BASE + at, pointers)
    files = {"m.bin": bytes(data)}
    if lfc:
        files["s.bin"] = install_lfc(d, src, lfc, app_dir, m, pointers, ring)
    return files


def install_lfh(d, src, big, app_dir, m, edits):
    """Add the loader to the compacted image `d` (padded to the slots' start): the files, the
    native llZ, the renamed lfh. Returns {file name: bytes}."""
    import sdpack
    import streamstub
    slot, nslots = big["slot"], big["nslots"]
    slots = [SD_BASE + MAX_SIZE - (k + 1) * slot for k in range(nslots)]
    files, groups = {}, []
    for entry, handle, start, length in big["movies"]:
        name = f"m{handle - 0x8000_0000}.bin"
        files[name] = bytes(src[start:start + length])
        groups.append((handle, app_dir + "\\" + name, [(SD_BASE + m(entry), 0)]))
        struct.pack_into("<I", d, m(entry), slots[0])  # until loaded: the slot (empty)
    code_len = len(streamstub.build(SD_BASE, groups, slots, slot)[0])
    pointers = {v for _, v, _ in edits}
    at = sdpack.free_space(d, code_len + 64, pointers)
    code, blob = streamstub.build(SD_BASE + at, groups, slots, slot)
    d[at:at + len(code)] = code
    add_native_resource(d, SD_BASE + at + blob, pointers)
    renames = [rename_lfh]
    lfc = big.get("lfc")
    if lfc:
        files["s.bin"] = install_lfc(d, src, lfc, app_dir, m, pointers, slots[-1] - lfc["ring"])
        renames.append(rename_playlfc)
    # Rename the natives in every movie left in the image, and in those on the card.
    for t in table_addresses_sd(d):
        if _u32(d, t - SD_BASE + 8) != 0x8000_0000 or _u32(d, t - SD_BASE) != 0x100:
            continue
        for k in range(_u32(d, t - SD_BASE + 12)):
            p = _u32(d, t - SD_BASE + 16 + 4 * k)
            if SD_BASE <= p < SD_BASE + len(d) and d[p - SD_BASE:p - SD_BASE + 3] == b"FWS" and p not in slots:
                o = p - SD_BASE
                ln = _u32(d, o + 4)
                for r in renames:
                    d[o:o + ln] = r(bytes(d[o:o + ln]))
    if lfc:
        for name in [n for n in files if n.startswith("m")]:
            files[name] = rename_playlfc(files[name])
    return files


def rename_playlfc(movie):
    """'LF_PlayLFC' -> 'LL_PlayLFC' (the same length) wherever it is a whole ActionScript string."""
    import streamstub
    return re.sub(rb"(?<![A-Za-z0-9_$.:])LF_PlayLFC\x00", streamstub.NAME_LFC.encode() + b"\x00", movie)


def install_lfc(d, src, lfc, app_dir, m, pointers, ring):
    """The sound clips go to s.bin; LL_PlayLFC reads one into the ring before LF_PlayLFC plays it.
    Returns s.bin's bytes."""
    import sdpack
    import streamstub
    data, where = bytearray(), {}
    for e, (k, p, ln) in sorted(lfc["clips"].items(), key=lambda c: c[1][1]):
        if p not in where:
            where[p] = len(data)
            data += src[p:p + ln]
        struct.pack_into("<I", d, m(e), ring)  # until loaded: the ring (empty)
    # One record per handle index of table 4: {table word, offset in s.bin, length} (length 0: in the image).
    t = _sound_table(src)
    n = _u32(src, t + 12)
    recs = [(0, 0, 0)] * n
    for e, (k, p, ln) in lfc["clips"].items():
        recs[k] = (SD_BASE + m(e), where[p], ln)
    first = _u32(src, t + 8)
    size = len(streamstub.build_lfc(SD_BASE, app_dir + "\\s.bin", first, recs, ring, lfc["ring"]))
    at = sdpack.free_space(d, size + 64, pointers)
    code = streamstub.build_lfc(SD_BASE + at, app_dir + "\\s.bin", first, recs, ring, lfc["ring"])
    d[at:at + len(code)] = code
    add_native_resource(d, SD_BASE + at, pointers)
    return bytes(data)


def add_native_resource(d, blob, pointers):
    """One more 0x1009 resource {id 5, flags 0x200, blob}: a copy of the list with it added, or,
    for a game without native lists, a copy of the LEAP directory with a 0x1009 entry added."""
    import sdpack
    try:
        e9, c9, list9 = sdpack.find_dir_entry(d, 0x1009)
        new = bytes(d[list9:list9 + 8 * c9]) + struct.pack("<HHI", 5, 0x200, blob)
        at = sdpack.free_space(d, len(new) + 16, pointers)
        d[at:at + len(new)] = new
        struct.pack_into("<HHI", d, e9, 0x1009, c9 + 1, SD_BASE + at)
    except sdpack.Unsupported:
        # Entries stay in ascending tag order (the BIOS looks resources up in order).
        leap = _u32(d, 0x140) - SD_BASE
        n = struct.unpack_from("<H", d, leap + 6)[0]
        lst = struct.pack("<HHI", 5, 0x200, blob)
        entries = [bytes(d[leap + 0x20 + 8 * i:leap + 0x28 + 8 * i]) for i in range(n)]
        size = 0x20 + 8 * (n + 1)
        at = sdpack.free_space(d, size + len(lst) + 16, pointers)
        l_at = (at + size + 3) & ~3
        entries.append(struct.pack("<HHI", 0x1009, 1, SD_BASE + l_at))
        entries.sort(key=lambda e: struct.unpack_from("<H", e)[0])
        head = bytearray(d[leap:leap + 0x20])
        struct.pack_into("<H", head, 6, n + 1)
        d[at:at + size] = bytes(head) + b"".join(entries)
        d[l_at:l_at + len(lst)] = lst
        struct.pack_into("<I", d, 0x140, SD_BASE + at)


def table_addresses_sd(d):
    """SD addresses of the 0x1006 tables of an SD image."""
    leap = _u32(d, 0x140) - SD_BASE
    out = []
    for i in range(struct.unpack_from("<H", d, leap + 6)[0]):
        tag, count, lst = struct.unpack_from("<HHI", d, leap + 0x20 + 8 * i)
        if tag == 0x1006:
            out += [_u32(d, lst - SD_BASE + 8 * j + 4) for j in range(count)]
    return [t for t in out if SD_BASE <= t < SD_BASE + len(d)]


def _tables(src):
    """{resource id: cartridge address} of the 0x1006 tables whose first handle is 0x8000_0000."""
    leap = _u32(src, 0x140) - CART_BASE
    out = {}
    for i in range(struct.unpack_from("<H", src, leap + 6)[0]):
        tag, count, lst = struct.unpack_from("<HHI", src, leap + 0x20 + 8 * i)
        if tag != 0x1006:
            continue
        for j in range(count):
            rid, _, v = struct.unpack_from("<HHI", src, lst - CART_BASE + 8 * j)
            if CART_BASE <= v < CART_BASE + len(src) and _u32(src, v - CART_BASE + 8) == 0x8000_0000:
                out.setdefault(rid, v - CART_BASE)
    return out


def _sound_table(src):
    """Offset of table 0x1006/4 (LF_PlayLFC's clips, handles from 0x8000), or None."""
    leap = _u32(src, 0x140) - CART_BASE
    for i in range(struct.unpack_from("<H", src, leap + 6)[0]):
        tag, count, lst = struct.unpack_from("<HHI", src, leap + 0x20 + 8 * i)
        if tag != 0x1006:
            continue
        for j in range(count):
            rid, _, v = struct.unpack_from("<HHI", src, lst - CART_BASE + 8 * j)
            if rid == 4 and CART_BASE <= v < CART_BASE + len(src) and _u32(src, v - CART_BASE) == 0x100:
                return v - CART_BASE
    return None


def _natives(d, base):
    """{name: offset of its function word} of every 0x1009 pair list (image based at `base`)."""
    leap = _u32(d, 0x140) - base
    inside = lambda v: base <= v < base + len(d)
    out = {}
    for i in range(struct.unpack_from("<H", d, leap + 6)[0]):
        tag, count, lst = struct.unpack_from("<HHI", d, leap + 0x20 + 8 * i)
        if tag != 0x1009:
            continue
        for j in range(count):
            b = _u32(d, lst - base + 8 * j + 4)
            if not inside(b) or _u32(d, b - base) != 0x100:
                continue
            n, pairs = _u32(d, b - base + 8) >> 16, _u32(d, b - base + 12)
            if not inside(pairs):
                continue
            for k in range(n):
                nm = _u32(d, pairs - base + 8 * k)
                if inside(nm):
                    name = bytes(d[nm - base:nm - base + 64]).split(b"\x00")[0].decode("latin-1")
                    out[name] = pairs - base + 8 * k + 4
    return out


def plan_peg(src):
    """Schoolhouse Rock style: ActionScript writes the video number to global data byte 1
    (LF_WriteGlobalDataBytes(1, n, 1)) and calls LF_PlayPegApplication(2); the game's PEG app then
    plays command list n of table 10, which names its video (command 0x55: handle 6 bytes on, in
    table 14) and its songs (command 0x59: handle right after, in table 15). Every video and every
    song of 64 KiB or more goes to the card: one file per video number (v<n>.bin: the video and its
    songs at 4 KiB boundaries), read into one slot when the app is started."""
    t = _tables(src)
    if not {10, 14, 15} <= set(t):
        raise Unsupported("no PEG video tables")
    names = _natives(src, CART_BASE)
    if "LF_PlayPegApplication" not in names or "LF_WriteGlobalDataBytes" not in names:
        raise Unsupported("no PEG natives")
    import sdpack
    starts = sdpack.resource_starts(src)

    def res(table, k):
        e = t[table] + 16 + 4 * k
        p = _u32(src, e) - CART_BASE
        nxt = min([s - CART_BASE for s in starts if s - CART_BASE > p] + [len(src)])
        return e, p, nxt - p

    cmds = t[10]
    groups, ext = [], {}
    for v in range(_u32(src, cmds + 12)):
        p = _u32(src, cmds + 16 + 4 * v) - CART_BASE
        nxt = min([s - CART_BASE for s in starts if s - CART_BASE > p] + [len(src)])
        blob = src[p:nxt]  # this command list only
        vids = [struct.unpack_from("<I", blob, m.start() + 6)[0] for m in re.finditer(rb"\x55", blob)
                if m.start() + 10 <= len(blob) and struct.unpack_from("<I", blob, m.start() + 6)[0] >> 8 == 0x80_0000]
        songs = [struct.unpack_from("<I", blob, m.start() + 1)[0] for m in re.finditer(rb"\x59", blob)
                 if m.start() + 5 <= len(blob) and struct.unpack_from("<I", blob, m.start() + 1)[0] >> 8 == 0x80_0000]
        if not vids:
            raise Unsupported(f"PEG command list {v}: no video")
        members = [(14, vids[0] - 0x8000_0000)] + [(15, h - 0x8000_0000) for h in songs]
        members = [(tb, k) for tb, k in members if k < _u32(src, t[tb] + 12) and res(tb, k)[2] >= 0x1_0000]
        for tb, k in members:
            ext[(tb, k)] = res(tb, k)
        groups.append(members)
    cuts = sorted({(e, None, p, ln) for e, p, ln in ext.values()}, key=lambda c: c[2])
    sizes = [sum((ext[mb][2] + 0xFFF) & ~0xFFF for mb in g) for g in groups]
    slot = (max(sizes) + SLOT_ALIGN - 1) & ~(SLOT_ALIGN - 1)
    end = _u32(src, 0x120) - CART_BASE + 12
    cut = sum((c[3] // CUT_ALIGN) * CUT_ALIGN for c in cuts)
    if end - cut + slot + RESERVE > MAX_SIZE:
        raise Unsupported("moving the videos to the card does not make it fit")
    return {"mode": "peg", "movies": cuts, "slot": slot, "nslots": 1, "groups": groups, "ext": ext}


def install_peg(d, src, big, app_dir, m, edits):
    import sdpack
    import streamstub
    slot = big["slot"]
    slot_base = SD_BASE + MAX_SIZE - slot
    files, groups = {}, []
    for v, members in enumerate(big["groups"]):
        data, words = bytearray(), []
        for mb in members:
            e, p, ln = big["ext"][mb]
            words.append((SD_BASE + m(e), len(data)))
            data += src[p:p + ln]
            data += bytes((-len(data)) % 0x1000)
        name = f"v{v}.bin"
        files[name] = bytes(data)
        groups.append((app_dir + "\\" + name, words))
    for e, _, _, _ in big["movies"]:
        struct.pack_into("<I", d, m(e), slot_base)  # until loaded: the slot (empty)
    names = _natives(d, SD_BASE)
    w_off, p_off = names["LF_WriteGlobalDataBytes"], names["LF_PlayPegApplication"]
    orig_w, orig_p = _u32(d, w_off), _u32(d, p_off)
    pointers = {v for _, v, _ in edits}
    size = len(streamstub.build_peg(SD_BASE, groups, slot_base, slot, orig_w, orig_p)[0])
    at = sdpack.free_space(d, size + 64, pointers)
    code, addr = streamstub.build_peg(SD_BASE + at, groups, slot_base, slot, orig_w, orig_p)
    d[at:at + len(code)] = code
    struct.pack_into("<I", d, w_off, addr["wgdb"])
    struct.pack_into("<I", d, p_off, addr["peg"])
    return files
