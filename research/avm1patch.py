"""Prototype (research): inserts ActionScript into an uncompressed SWF before chosen actions.

What the insertion moves is fixed up: If/Jump offsets across it, the sizes of the DefineFunction,
DefineFunction2 and With bodies around it, the lengths of the tags that hold it (DoAction,
DoInitAction, DefineSprite) and the SWF's length. Inserted code lands before the chosen action, so a
branch to that action runs the inserted code too. Try blocks and WaitForFrame skips around an
insertion are refused (Unsupported).

Used by bigimage.py for movies kept on the card (Story Explorers): every GetURL2 that loads a movie
into "_level" + N first tells the native loader the level and the movie (see `level_loads`).
"""
import struct


class Unsupported(Exception):
    pass


def actions(b, start, end):
    """[(offset, opcode, total length)] of the action block b[start:end], function bodies inline."""
    out, i = [], start
    while i < end:
        op = b[i]
        ln = 1 + (2 + struct.unpack_from("<H", b, i + 1)[0] if op >= 0x80 else 0)
        out.append((i, op, ln))
        i += ln
        if op == 0:
            break
    return out


def _cstr_end(b, i):
    return b.index(b"\0", i) + 1


def _body_size_at(b, o, op):
    """Offset of the u16 body size in the action at o (DefineFunction, DefineFunction2, With)."""
    if op == 0x94:
        return o + 3
    k = _cstr_end(b, o + 3)
    n = struct.unpack_from("<H", b, k)[0]
    k += 2
    if op == 0x9B:
        for _ in range(n):
            k = _cstr_end(b, k)
        return k
    k += 3  # register count, flags
    for _ in range(n):
        k = _cstr_end(b, k + 1)
    return k


def patch_block(b, start, end, inserts):
    """The block b[start:end] with `inserts` {absolute offset of an action: bytes} applied."""
    acts = actions(b, start, end)
    starts = {o for o, _, _ in acts}
    for p in inserts:
        if p not in starts:
            raise Unsupported(f"insertion at {p:#x} is not the start of an action")
    pts = sorted(inserts)
    before = lambda x: sum(len(inserts[p]) for p in pts if p < x)       # a branch target / body edge
    new_at = lambda x: x + before(x) + (len(inserts[x]) if x in inserts else 0)  # where an action goes
    out = bytearray(b[start:end])
    fix = []  # (offset in the old block, packed value) to write after the copy
    for o, op, ln in acts:
        e = o + ln
        if op in (0x99, 0x9D):
            t = e + struct.unpack_from("<h", b, o + 3)[0]
            off = (t + before(t)) - (new_at(o) + ln)
            if not -0x8000 <= off < 0x8000:
                raise Unsupported(f"branch at {o:#x} out of range after the insertion")
            fix.append((o + 3, struct.pack("<h", off)))
        elif op in (0x9B, 0x8E, 0x94):
            at = _body_size_at(b, o, op)
            size = struct.unpack_from("<H", b, at)[0]
            s0, s1 = e, e + size
            fix.append((at, struct.pack("<H", (s1 + before(s1)) - (s0 + before(s0)))))
        elif op == 0x8F:
            if any(o < p < e + sum(struct.unpack_from("<HHH", b, o + 4)) for p in pts):
                raise Unsupported(f"insertion inside a Try block at {o:#x}")
        elif op in (0x8A, 0x8D):
            skip = b[o + (5 if op == 0x8A else 3)]
            nxt = [a for a, _, _ in acts if a >= e][:skip]
            if any(p in nxt for p in pts):
                raise Unsupported(f"insertion inside a WaitForFrame skip at {o:#x}")
    for at, val in fix:
        out[at - start:at - start + len(val)] = val
    res = bytearray()
    prev = start
    for p in pts:
        res += out[prev - start:p - start] + inserts[p]
        prev = p
    res += out[prev - start:]
    return bytes(res)


def _tag_header(code, ln):
    if ln < 0x3F:
        return struct.pack("<H", code << 6 | ln)
    return struct.pack("<HI", code << 6 | 0x3F, ln)


def _patch_tags(b, start, end, inserts):
    """Tags b[start:end] rebuilt with the insertions that fall in their action blocks."""
    out, i = bytearray(), start
    while i < end:
        h = i
        code_len = struct.unpack_from("<H", b, i)[0]
        i += 2
        code, ln = code_len >> 6, code_len & 0x3F
        if ln == 0x3F:
            ln = struct.unpack_from("<I", b, i)[0]
            i += 4
        body, nxt = (i, i + ln), i + ln
        mine = {p: v for p, v in inserts.items() if i <= p < nxt}
        if not mine:
            out += b[h:nxt]
        elif code == 12:
            new = patch_block(b, i, nxt, mine)
            out += _tag_header(code, len(new)) + new
        elif code == 59:
            new = b[i:i + 2] + patch_block(b, i + 2, nxt, mine)
            out += _tag_header(code, len(new)) + new
        elif code == 39:
            new = b[i:i + 4] + _patch_tags(b, i + 4, nxt, mine)
            out += _tag_header(code, len(new)) + new
        else:
            raise Unsupported(f"insertion in tag {code} at {h:#x} (only DoAction, DoInitAction, DefineSprite)")
        i = nxt
        if code == 0:
            break
    return bytes(out)


def header_end(swf):
    nbits = swf[8] >> 3
    return 8 + (5 + 4 * nbits + 7) // 8 + 4


def patch_swf(swf, inserts):
    """`swf` (b"FWS"...) with `inserts` {offset in the SWF: bytes} applied."""
    if swf[:3] != b"FWS":
        raise Unsupported("not an uncompressed SWF")
    h = header_end(swf)
    body = _patch_tags(swf, h, len(swf), inserts)
    out = bytearray(swf[:h]) + body
    struct.pack_into("<I", out, 4, len(out))
    return bytes(out)


def blocks(swf, start=None, end=None):
    """Every (start, end) action block of the SWF that patch_swf can change."""
    i = header_end(swf) if start is None else start
    end = len(swf) if end is None else end
    while i < end:
        code_len = struct.unpack_from("<H", swf, i)[0]
        i += 2
        code, ln = code_len >> 6, code_len & 0x3F
        if ln == 0x3F:
            ln = struct.unpack_from("<I", swf, i)[0]
            i += 4
        if code == 12:
            yield i, i + ln
        elif code == 59:
            yield i + 2, i + ln
        elif code == 39:
            yield from blocks(swf, i + 4, i + ln)
        i += ln
        if code == 0:
            break


def _push(*vals):
    """A Push action of ints and strings."""
    body = b""
    for v in vals:
        body += b"\x07" + struct.pack("<i", v) if isinstance(v, int) else b"\x00" + v.encode() + b"\0"
    return b"\x96" + struct.pack("<H", len(body)) + body


def call_pop(name, nargs):
    """Push nargs, name; CallFunction; Pop (the arguments are already on the stack)."""
    return _push(nargs, name) + b"\x3D\x17"


def level_loads(swf, level_native, movie_native):
    """Insertions before every GetURL2 of the SWF whose target is "_level" + N (StringAdd right
    before it) or a constant "_levelN": level_native(N), then movie_native(url) with the stack
    as it was. Returns ({offset: bytes}, count of GetURL2 actions left alone)."""
    ins, other = {}, 0
    for s, e in blocks(swf):
        acts = actions(swf, s, e)
        targets = set()
        for o, op, ln in acts:
            if op in (0x99, 0x9D):
                targets.add(o + ln + struct.unpack_from("<h", swf, o + 3)[0])
        pool = []
        for k, (o, op, ln) in enumerate(acts):
            if op == 0x88:
                n, i = struct.unpack_from("<H", swf, o + 3)[0], o + 5
                pool = []
                for _ in range(n):
                    j = _cstr_end(swf, i)
                    pool.append(swf[i:j - 1])
                    i = j
            if op != 0x9A or k == 0:
                continue
            po, pop_, pln = acts[k - 1]
            url = b"\x4D\x4C" + call_pop(movie_native, 1) + b"\x4D"  # swap, dup, call(url), swap
            if pop_ == 0x21 and po not in targets and o not in targets:  # StringAdd: N on top
                ins[po] = b"\x4C" + call_pop(level_native, 1)
                ins[o] = url
                continue
            target = _single_string(swf[po + 3:po + pln], pool) if pop_ == 0x96 and o not in targets else None
            if target is not None and target.startswith(b"_level") and target[6:].isdigit():
                ins[o] = _push(int(target[6:])) + call_pop(level_native, 1) + url
            else:
                other += 1
    return ins, other


def _single_string(body, pool):
    """The string a Push of exactly one string (literal or constant pool) pushes, else None."""
    if body[:1] == b"\x00" and body.endswith(b"\0") and body.count(b"\0") == 1:
        return body[1:-1]
    if len(body) == 2 and body[0] == 8 and body[1] < len(pool):
        return pool[body[1]]
    if len(body) == 3 and body[0] == 9:
        c = struct.unpack_from("<H", body, 1)[0]
        return pool[c] if c < len(pool) else None
    return None
