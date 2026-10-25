"""Prototype (research): builds Flash 5 SWF movies with ActionScript (AVM1)
bytecode, and packs SWFs into a Leapster "RIB" image for the Leapster 2 SD
load area (0x3C80_0000), the format the BIOS boots as "Packed RIB Movie(s)".

Everything here is generated from scratch: no LeapFrog code or data.
The image layout follows docs/sd-boot-proof.md.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SD_BASE = 0x3C80_0000
FIRST_HANDLE = 0x8000_0000  # movie handles: FIRST_HANDLE + index (main movie = index 0)
TWIPS = 20


# ---------------------------------------------------------------- AVM1 assembler

class AS:
    """A tiny AVM1 assembler. Methods append actions; labels resolve jumps."""

    def __init__(self):
        self.code = []  # list of bytes chunks or ('jump'/'if', label)
        self.labels = {}

    def raw(self, op, body=b""):
        if op >= 0x80:
            self.code.append(bytes([op]) + struct.pack("<H", len(body)) + body)
        else:
            self.code.append(bytes([op]))
        return self

    def push(self, *vals):
        body = b""
        for v in vals:
            if isinstance(v, bool):
                body += b"\x05" + bytes([int(v)])
            elif isinstance(v, int):
                body += b"\x07" + struct.pack("<i", v)
            elif isinstance(v, float):
                body += b"\x06" + struct.pack("<d", v)[4:] + struct.pack("<d", v)[:4]
            elif v is None:
                body += b"\x02"
            elif isinstance(v, Reg):
                body += b"\x04" + bytes([v.n])
            else:
                body += b"\x00" + v.encode("latin-1") + b"\0"
        return self.raw(0x96, body)

    def call(self, name, *args):
        """Calls a global function by name; leaves the result on the stack."""
        for a in reversed(args):
            if isinstance(a, AS):
                self.code.extend(a.code)  # an expression already assembled
            else:
                self.push(a)
        return self.push(len(args), name).raw(0x3D)

    def callv(self, name, *args):
        return self.call(name, *args).raw(0x17)  # discard the result

    def getvar(self, name):
        return self.push(name).raw(0x1C)

    def setvar(self, name, value=None):
        """Sets a variable; with value None the value must already be on the stack (pushed after the name)."""
        if value is None:
            return self.raw(0x1D)
        return self.push(name, value).raw(0x1D)

    def label(self, name):
        self.code.append(("label", name))
        return self

    def jump(self, label):
        self.code.append(("jump", label))
        return self

    def if_true(self, label):
        self.code.append(("if", label))
        return self

    def define_function(self, name, params, body):
        """DefineFunction (0x9B). With name '' the function is pushed (anonymous)."""
        b = body.assemble()
        head = name.encode() + b"\0" + struct.pack("<H", len(params))
        for p in params:
            head += p.encode() + b"\0"
        head += struct.pack("<H", len(b))
        self.code.append(bytes([0x9B]) + struct.pack("<H", len(head)) + head + b)
        return self

    def op(self, name):
        if name == "gt":
            # a > b as b < a: ActionGreater (0x67) is Flash 6, the Leapster's player is Flash 5.
            return self.raw(0x4D).raw(0x48)
        ops = {"add": 0x47, "sub": 0x0B, "mul": 0x0C, "div": 0x0D, "eq": 0x49, "lt": 0x48,
               "not": 0x12, "pop": 0x17, "return": 0x3E, "getmember": 0x4E, "setmember": 0x4F,
               "stop": 0x07, "play": 0x06, "dup": 0x4C, "swap": 0x4D, "tostring": 0x4B, "tonumber": 0x4A,
               "strlen": 0x14, "substr": 0x15, "slt": 0x29, "chr": 0x33, "ord": 0x32, "inc": 0x50, "dec": 0x51,
               "newobject": 0x40, "initarray": 0x42, "callmethod": 0x52, "and": 0x60, "or": 0x61,
               "shl": 0x63, "shr": 0x64, "concat": 0x21, "streq": 0x13, "mod": 0x3F, "int": 0x18,
               "definelocal": 0x3C, "typeof": 0x44, "nextframe": 0x04, "gotoframe2": None}
        return self.raw(ops[name])

    def assemble(self):
        # Two passes: sizes are fixed (jumps are 5 bytes).
        pos, labels = 0, {}
        for c in self.code:
            if isinstance(c, tuple):
                if c[0] == "label":
                    labels[c[1]] = pos
                else:
                    pos += 5
            else:
                pos += len(c)
        out, pos = b"", 0
        for c in self.code:
            if isinstance(c, tuple):
                if c[0] == "label":
                    continue
                pos += 5
                off = labels[c[1]] - pos
                out += bytes([0x99 if c[0] == "jump" else 0x9D]) + struct.pack("<Hh", 2, off)
            else:
                out += c
                pos += len(c)
        return out


class Reg:
    def __init__(self, n):
        self.n = n


# ---------------------------------------------------------------- SWF writer

def tag(code, body):
    if len(body) < 0x3F:
        return struct.pack("<H", code << 6 | len(body)) + body
    return struct.pack("<HI", code << 6 | 0x3F, len(body)) + body


def bits(values_and_widths):
    """Packs (value, nbits) pairs MSB first, padded to a byte."""
    acc, n = 0, 0
    for v, w in values_and_widths:
        acc = (acc << w) | (v & ((1 << w) - 1))
        n += w
    pad = (-n) % 8
    acc <<= pad
    return acc.to_bytes((n + pad) // 8, "big")


def rect(xmin, xmax, ymin, ymax):
    nb = max(max(abs(x) for x in (xmin, xmax, ymin, ymax)).bit_length() + 1, 1)
    return bits([(nb, 5), (xmin, nb), (xmax, nb), (ymin, nb), (ymax, nb)])


def rgb(c):
    return bytes([(c >> 16) & 255, (c >> 8) & 255, c & 255])


def define_rect_shape(shape_id, w, h, color):
    """DefineShape (2): a filled w x h pixel rectangle at the origin."""
    W, H = w * TWIPS, h * TWIPS
    body = struct.pack("<H", shape_id) + rect(0, W, 0, H)
    body += b"\x01\x00" + rgb(color)  # one solid fill
    body += b"\x00"  # no line styles
    body += bytes([0x10])  # 1 fill bit, 0 line bits
    nb = max(W, H).bit_length() + 1
    recs = []
    # style change: moveto(0,0), fill1 = 1
    recs += [(0, 1), (0, 1), (0, 1), (1, 1), (0, 1), (1, 1), (1, 5), (0, 1), (0, 1), (1, 1)]
    # straight edges: right, down, left, up (general line flag 0, vertical flag)
    def hline(dx):
        n = max(abs(dx).bit_length() + 1, 2)
        return [(1, 1), (1, 1), (n - 2, 4), (0, 1), (0, 1), (dx, n)]
    def vline(dy):
        n = max(abs(dy).bit_length() + 1, 2)
        return [(1, 1), (1, 1), (n - 2, 4), (0, 1), (1, 1), (dy, n)]
    recs += hline(W) + vline(H) + hline(-W) + vline(-H)
    recs += [(0, 1), (0, 5)]  # end
    body += bits(recs)
    return tag(2, body)


def place(depth, char_id, x, y, name=None, color_mul=None, clip_depth=None):
    """PlaceObject2 with a translate matrix (and an optional instance name). With
    `clip_depth` the object is a mask for the objects above it up to that depth."""
    flags = 0x02 | 0x04  # has character, has matrix
    if name:
        flags |= 0x20
    if clip_depth:
        flags |= 0x40
    tx, ty = x * TWIPS, y * TWIPS
    nb = max(abs(tx).bit_length(), abs(ty).bit_length()) + 1
    matrix = bits([(0, 1), (0, 1), (nb, 5), (tx, nb), (ty, nb)])
    body = bytes([flags]) + struct.pack("<HH", depth, char_id) + matrix
    if name:
        body += name.encode() + b"\0"
    if clip_depth:
        body += struct.pack("<H", clip_depth)
    return tag(26, body)


def swf(tags, width=160, height=160, frame_rate=12, frames=1, bg=0x000000, version=5):
    body = rect(0, width * TWIPS, 0, height * TWIPS) + struct.pack("<HH", frame_rate << 8, frames)
    body += tag(9, rgb(bg))  # SetBackgroundColor
    body += b"".join(tags) + tag(0, b"")
    return b"FWS" + bytes([version]) + struct.pack("<I", 8 + len(body)) + body


def do_action(a):
    return tag(12, a.assemble() + b"\0")


def show_frame():
    return tag(1, b"")


# ---------------------------------------------------------------- RIB image packer

def approval_fields(cart_image):
    """The 0x1003 fields the BIOS's content-approval checks read, copied from a
    user-supplied cartridge image: ids 0x04-0x06 (texts; 0x04 is compared character
    by character with the BIOS's own copy at positions listed in its 0x1003/9, BIOS
    0.6 0x4005_2128), 0x0D-0x0F (strings) and 0x10 (20 bytes; a hash of 0x0D-0x0F,
    0x4005_23F8). The checks cover only these fields, not the movies."""
    d = cart_image
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    base = u32(0x11C)
    leap = u32(0x140) - base
    out = {}
    for i in range(struct.unpack_from("<H", d, leap + 6)[0]):
        tag, cnt, ptr = struct.unpack_from("<HHI", d, leap + 0x20 + 8 * i)
        if tag != 0x1003:
            continue
        for j in range(cnt):
            rid, _, v = struct.unpack_from("<HHI", d, ptr - base + 8 * j)
            if rid in (0x04, 0x05, 0x06, 0x0D, 0x0E, 0x0F):
                o = v - base
                out[rid] = d[o:d.index(b"\0", o)]
            elif rid == 0x10:
                out[rid] = d[v - base:v - base + 20]
    if not {0x04, 0x0D, 0x0E, 0x0F, 0x10} <= set(out):
        raise ValueError("no approval fields in this image")
    return out


SEQ_FIRST_HANDLE = 0x8000  # handles of a cartridge's sequences (resource 0x1006/6), e.g. Star Wars Jedi Reading
RAW_FIRST_HANDLE = 0x8000  # handles of the image's raw sounds (resource 0x1006/5), numbered as the sequences


def pack_rib(movies, title="LeapLoader", part="000-00000", base=SD_BASE, size=None, approval=None, sequences=(),
             raw_sounds=()):
    """Packs SWF movies (main movie first) into a RIB image linked at `base`.

    Layout (as SpongeBob's, LEAP directory at offset 0):
      0x000 'LEAP' directory: tags 0x1003 (text metadata), 0x1006 (id 7: movie table), 0x2000 (main movie handle)
      0x100 RIB header ('Copyright LeapFrog', 0x00010100, base, end, end+8, checksum pointer)
      0x140 pointer to the LEAP directory; 0x144 the 0x2000 blob
      then strings, the movie table and the movies (4-byte aligned); the checksum word at end+4.
    `sequences`: music in LeapFrog's sequence format (seqgen.py), as resource 0x1006/6 with
    handles SEQ_FIRST_HANDLE + i, the numbering cartridges use for theirs.
    `raw_sounds`: 8 kHz A-law clips (sndgen.load_alaw) for LF_PlayAudioRaw, as resource 0x1006/5 with
    handles RAW_FIRST_HANDLE + i; an item (data, [(start, end), ...]) gives one handle per byte range of
    `data` (several sounds sharing the same bytes). As the BIOS's own table (0x4000_5C2C): the pointers come in
    (start, end) pairs, count = 2 x clips, and handle first + i plays pair i (VERIFIED-FW + EMU).
    """
    img = bytearray(0x200)
    ptr = lambda off: base + off

    def put(data, align=4):
        off = (len(img) + align - 1) & ~(align - 1)
        img.extend(b"\0" * (off - len(img)))
        img.extend(data)
        return off

    texts = {0x0A: part.encode(), 0x0B: title.encode(), 0x0C: b"LeapLoader SD menu"}
    if approval:
        texts.update({k: v for k, v in approval.items() if k != 0x10})
    # 0x1003 ids 2 and 3 point to small version records, as on cartridges ({0x00010100, 0, 0, n}).
    ver2 = ptr(put(struct.pack("<4I", 0x00010100, 0, 0, 0x00010001)))
    ver3 = ptr(put(struct.pack("<4I", 0x00010100, 0, 0, 1)))
    text_entries = [(i, ptr(put(t + b"\0", 1))) for i, t in texts.items()]
    if approval:
        text_entries.append((0x10, ptr(put(approval[0x10]))))
    movie_offs = [put(m) for m in movies]
    table = struct.pack("<4I", 0x100, 0, FIRST_HANDLE, len(movies)) + b"".join(struct.pack("<I", ptr(o)) for o in movie_offs)
    table_off = put(table)
    raw_table_off = None
    if raw_sounds:
        raw_offs = []
        for r in raw_sounds:
            data, ranges = r if isinstance(r, tuple) else (r, [(0, len(r))])
            o = put(data, 1)
            raw_offs += [(o + a, o + b) for a, b in ranges]
        raw_table_off = put(struct.pack("<4I", 0x100, 0, RAW_FIRST_HANDLE, 2 * len(raw_offs))
                            + b"".join(struct.pack("<II", ptr(s), ptr(e)) for s, e in raw_offs))
    seq_table_off = None
    if sequences:
        seq_offs = [put(q) for q in sequences]
        seq_table_off = put(struct.pack("<4I", 0x100, 0, SEQ_FIRST_HANDLE, len(sequences))
                            + b"".join(struct.pack("<I", ptr(o)) for o in seq_offs))
    # sub-entry lists
    s1003 = put(b"".join(struct.pack("<HHI", i, 0x100, v) for i, v in sorted([(1, 1), (2, ver2), (3, ver3), (8, 0x100)] + text_entries)))
    # In ascending resource id order, as cartridges list them.
    s1006 = put((struct.pack("<HHI", 5, 0x100, ptr(raw_table_off)) if raw_table_off is not None else b"")
                + (struct.pack("<HHI", 6, 0x100, ptr(seq_table_off)) if seq_table_off is not None else b"")
                + struct.pack("<HHI", 7, 0x100, ptr(table_off)))
    s2000 = put(struct.pack("<HHI", 1, 0xFA00, ptr(0x144)))
    dirs = [(0x1003, len(text_entries) + 4, s1003), (0x1006, 1 + (seq_table_off is not None) + (raw_table_off is not None), s1006), (0x2000, 1, s2000)]
    img[0:8] = b"LEAP" + struct.pack("<HH", 0x100, len(dirs))
    for k, (t, n, o) in enumerate(dirs):
        struct.pack_into("<HHI", img, 0x20 + 8 * k, t, n, ptr(o))
    # RIB header
    img[0x100:0x118] = b"Copyright LeapFrog     \0"
    end_off = (len(img) + 3) & ~3
    img.extend(b"\0" * (end_off - len(img) + 16))
    struct.pack_into("<IIIII", img, 0x118, 0x00010100, base, ptr(end_off), ptr(end_off + 8), ptr(end_off + 4))
    struct.pack_into("<I", img, 0x140, base)
    struct.pack_into("<4I", img, 0x144, 0x00010100, 0, 0, FIRST_HANDLE)
    # checksum (BIOS 0x4005_28A4): one word every 0xF94 bytes from base to end
    s, a = 0, base
    while True:
        s = (s + struct.unpack_from("<I", img, a - base)[0]) & 0xFFFFFFFF
        a += 0xF94
        if not ptr(end_off) >= a:
            break
    struct.pack_into("<I", img, end_off + 4, s)
    if size:
        img.extend(b"\0" * (size - len(img)))
    return bytes(img)


# ---------------------------------------------------------------- fonts, text, buttons, sprites

def _shape_rects(rects, unit):
    """SHAPE records (no style arrays, 1 fill bit) for filled rectangles given in
    font pixels (x, y, w, h), scaled by `unit`; fill style 1 on every rectangle."""
    recs = []
    first = True
    for (x, y, w, h) in rects:
        X, Y, W, H = x * unit, y * unit, w * unit, h * unit
        nb = max(abs(X).bit_length(), abs(Y).bit_length()) + 1
        # StyleChangeRecord: TypeFlag 0, NewStyles 0, LineStyle 0, FillStyle1, FillStyle0 0, MoveTo 1
        recs += [(0, 1), (0, 1), (0, 1), (1 if first else 0, 1), (0, 1), (1, 1), (nb, 5), (X, nb), (Y, nb)]
        if first:
            recs += [(1, 1)]  # FillStyle1 = 1
            first = False
        def line(dx, dy):
            v = dx == 0
            d = dy if v else dx
            n = max(abs(d).bit_length() + 1, 2)
            return [(1, 1), (1, 1), (n - 2, 4), (0, 1), (1 if v else 0, 1), (d, n)]
        recs += line(W, 0) + line(0, H) + line(-W, 0) + line(0, -H)
    recs += [(0, 1), (0, 5)]
    return bytes([0x10]) + bits(recs)


def glyph_rects(rows):
    """Horizontal runs of '#' as (x, y, w, 1) with y relative to the baseline."""
    from pixelfont import ASCENT
    out = []
    for r, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == "#":
                s = x
                while x < len(row) and row[x] == "#":
                    x += 1
                out.append((s, r - ASCENT, x - s, 1))
            else:
                x += 1
    return out


def define_font(font_id):
    """DefineFont (10) with the LeapLoader pixel font: EM square 1024 = 8 font pixels."""
    from pixelfont import GLYPHS, CHARS
    shapes = [_shape_rects(glyph_rects(GLYPHS[c]), 128) for c in CHARS]
    n = len(shapes)
    offs, pos = [], 2 * n
    for s in shapes:
        offs.append(pos)
        pos += len(s)
    body = struct.pack("<H", font_id) + b"".join(struct.pack("<H", o) for o in offs) + b"".join(shapes)
    return tag(10, body)


def define_text(text_id, font_id, lines, scale=1):
    """DefineText (11). `lines`: [(x_px, baseline_y_px, color, string)]. One font pixel
    = `scale` screen pixels."""
    from pixelfont import CHARS, ADVANCE
    height = 8 * scale * TWIPS
    adv = ADVANCE * scale * TWIPS
    gbits, abits = 7, adv.bit_length() + 1
    recs = b""
    maxx = 0
    for (x, y, color, s) in lines:
        s = "".join(c if c in CHARS else "?" for c in s)[:255]
        recs += bytes([0x80 | 0x08 | 0x04 | 0x02 | 0x01]) + struct.pack("<H", font_id) + rgb(color)
        recs += struct.pack("<hhH", x * TWIPS, y * TWIPS, height) + bytes([len(s)])
        recs += bits([v for c in s for v in ((CHARS.index(c), gbits), (adv, abits))])
        maxx = max(maxx, x * TWIPS + adv * len(s))
    recs += b"\0"
    bounds = rect(0, max(maxx, 20), -height, 160 * TWIPS)
    matrix = bits([(0, 1), (0, 1), (0, 5)])
    return tag(11, struct.pack("<H", text_id) + bounds + matrix + bytes([gbits, abits]) + recs)


def define_button(button_id, hit_shape_id, actions_on_press):
    """DefineButton2 (34): an invisible hit area (`hit_shape_id` at the origin) whose
    actions run when the stylus presses it (IdleToOverDown | OverUpToOverDown)."""
    rec = bytes([0x08]) + struct.pack("<HH", hit_shape_id, 1) + bits([(0, 1), (0, 1), (0, 5)]) + bits([(0, 1), (0, 1), (0, 4)])
    chars = rec + b"\0"
    acts = actions_on_press.assemble() + b"\0"
    cond = struct.pack("<H", 0) + bytes([0x80 | 0x04, 0x00]) + acts
    body = struct.pack("<H", button_id) + b"\0" + struct.pack("<H", 2 + len(chars)) + chars + cond
    return tag(34, body)


def define_sprite(sprite_id, tags, frames=1):
    return tag(39, struct.pack("<HH", sprite_id, frames) + b"".join(tags) + tag(0, b""))


def set_property(a, target, prop, value_as):
    """target.prop = value (SetProperty 0x23). prop: 0 _x, 1 _y, 6 _alpha, 7 _visible.
    `target` is a path string, or an AS expression computing one."""
    if isinstance(target, AS):
        a.code.extend(target.code)
        a.push(prop)
    else:
        a.push(target, prop)
    a.code.extend(value_as.code)
    return a.raw(0x23)


def place_enterframe(depth, char_id, actions):
    """PlaceObject2 of `char_id` with clip actions: onClipEvent(enterFrame) runs `actions`
    every frame (SWF 5 clip-action format: 16-bit event flags; EnterFrame = 0x0002)."""
    acts = actions.assemble() + b"\0"
    clip = struct.pack("<HH", 0, 0x0002) + struct.pack("<HI", 0x0002, len(acts)) + acts + struct.pack("<H", 0)
    body = bytes([0x80 | 0x02]) + struct.pack("<HH", depth, char_id) + clip
    return tag(26, body)


def method(a, obj_as, name, *args):
    """obj.name(args...) leaving the result on the stack."""
    for x in reversed(args):
        if isinstance(x, AS):
            a.code.extend(x.code)
        else:
            a.push(x)
    a.push(len(args))
    a.code.extend(obj_as.code)
    return a.push(name).op("callmethod")


def swf_define_ids(m):
    """Character ids defined at the top level of a SWF (to pick unused ones)."""
    nbits = m[8] >> 3
    i = 8 + (5 + 4 * nbits + 7) // 8 + 4
    ids = set()
    defining = {2, 6, 7, 10, 11, 14, 20, 21, 22, 32, 33, 34, 35, 36, 37, 39, 46, 48, 60, 62, 75, 83, 84, 87, 90, 91}
    while i < len(m):
        cl = struct.unpack_from("<H", m, i)[0]
        code, ln = cl >> 6, cl & 0x3F
        i += 2
        if ln == 0x3F:
            ln = struct.unpack_from("<I", m, i)[0]
            i += 4
        if code in defining and ln >= 2:
            ids.add(struct.unpack_from("<H", m, i)[0])
        if code == 0:
            break
        i += ln
    return ids


def define_shape_layers(shape_id, layers):
    """DefineShape (2) with several solid colours. `layers`: [(rgb, [(x, y, w, h), ...])]
    in pixels; rectangles of one colour must not overlap (they are separate subpaths)."""
    layers = [(c, r) for c, r in layers if r]
    allx = [v for _, rs in layers for (x, y, w, h) in rs for v in (x, x + w)] or [0]
    ally = [v for _, rs in layers for (x, y, w, h) in rs for v in (y, y + h)] or [0]
    body = struct.pack("<H", shape_id) + rect(min(allx) * TWIPS, max(allx) * TWIPS, min(ally) * TWIPS, max(ally) * TWIPS)
    body += bytes([len(layers)]) + b"".join(b"\x00" + rgb(c) for c, _ in layers)
    body += b"\x00"  # no line styles
    fbits = max(len(layers).bit_length(), 1)
    body += bytes([fbits << 4])
    recs = []
    for idx, (_, rs) in enumerate(layers, start=1):
        for k, (x, y, w, h) in enumerate(rs):
            X, Y, W, H = x * TWIPS, y * TWIPS, w * TWIPS, h * TWIPS
            nb = max(abs(X).bit_length(), abs(Y).bit_length()) + 1
            first = k == 0
            # StyleChangeRecord: NewStyles 0, LineStyle 0, FillStyle1 (on colour change), FillStyle0 0, MoveTo 1
            recs += [(0, 1), (0, 1), (0, 1), (1 if first else 0, 1), (0, 1), (1, 1), (nb, 5), (X, nb), (Y, nb)]
            if first:
                recs += [(idx, fbits)]
            def line(dx, dy):
                v = dx == 0
                d = dy if v else dx
                n = max(abs(d).bit_length() + 1, 2)
                return [(1, 1), (1, 1), (n - 2, 4), (0, 1), (1 if v else 0, 1), (d, n)]
            recs += line(W, 0) + line(0, H) + line(-W, 0) + line(0, -H)
    recs += [(0, 1), (0, 5)]
    body += bits(recs)
    return tag(2, body)


def rounded_rects(x, y, w, h, r=2):
    """Non-overlapping rectangles forming a w x h box with corners rounded by r pixels
    (row insets from the edge: r=1 -> 1; r=2 -> 2, 1; r=3 -> 3, 1, 1)."""
    insets = [r] + [1] * (r - 1) if r > 0 else []
    out = []
    for i, inset in enumerate(insets):
        out.append((x + inset, y + i, w - 2 * inset, 1))
        out.append((x + inset, y + h - 1 - i, w - 2 * inset, 1))
    out.append((x, y + r, w, h - 2 * r))
    return out


def bitmap_rects(rows, ch="#", scale=1, ox=0, oy=0):
    """Horizontal runs of `ch` in a pixel-art bitmap, as rectangles."""
    out = []
    for r, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == ch:
                s = x
                while x < len(row) and row[x] == ch:
                    x += 1
                out.append((ox + s * scale, oy + r * scale, (x - s) * scale, scale))
            else:
                x += 1
    return out
