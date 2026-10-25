"""Prototype (research): music for the Leapster 2 in LeapFrog's sequence format, from a MIDI file.

The BIOS plays these with LF_PlayBgMIDI(lfh(handle), ...) using its own 128 instruments
(biosbank2sf2.py makes a SoundFont of them for composing).

Format (BLiNXthetimesweeperGOD, gist "LeapFrog Sequencer (Leap-Font)"; checked against the BIOS's
own songs, resource 0x1006/6, e.g. the home screen music):
* Header: the bytes 02 00, u16 track count (little-endian), then per track a u16 offset (little-endian, from the start of
  the sequence) and a u16 ID (big-endian; unused).
* A track is one voice: commands one after the other.
    00-7F d   note (0 = rest) lasting d ticks; then the next command
    88 v      volume (0-0x7F)          89 p   program (BIOS instrument 0-127)
    8E n      loop start, n times      8F 00  loop end          FF 00  track end
  Durations: one byte below 0x80; else two bytes, (0x80 | d >> 8), d & 0xFF.

Usage: python seqgen.py IN.mid OUT.seq      (track names are the BIOS program numbers)
"""
import struct
import sys

LOOP_FOREVER = 0x7F  # as the home screen music (89 7C 8E 7F ...)


def dur(d):
    if not 0 < d <= 0x7FFF:
        raise ValueError(f"duration {d} out of range")
    return bytes([d]) if d < 0x80 else bytes([0x80 | d >> 8, d & 0xFF])


def track(program, volume, events, loop=True):
    """events: [(note, ticks)], note 0 = rest."""
    out = bytearray([0x89, program, 0x88, volume])
    if loop:
        out += bytes([0x8E, LOOP_FOREVER])
    for note, ticks in events:
        while ticks > 0:  # split very long notes/rests (only rests should need it)
            d = min(ticks, 0x7FFF)
            out += bytes([note]) + dur(d)
            ticks -= d
    if loop:
        out += bytes([0x8F, 0])
    return bytes(out + bytes([0xFF, 0]))


def sequence(tracks):
    """tracks: track() byte strings."""
    head = 4 + 4 * len(tracks)
    out = bytearray(bytes([2, 0]) + struct.pack("<H", len(tracks)))
    off = head
    for k, t in enumerate(tracks):
        out += struct.pack("<H", off) + struct.pack(">H", k)
        off += len(t)
    for t in tracks:
        out += t
    return bytes(out)


# ---------------------------------------------------------------- MIDI files

def read_midi(path):
    """[(track name, [(start tick, end tick, note, velocity)])], ticks per quarter, [(tick, us per quarter)]."""
    d = open(path, "rb").read()
    if d[:4] != b"MThd":
        raise ValueError("not a MIDI file")
    _, ntracks, division = struct.unpack(">HHH", d[8:14])
    if division & 0x8000:
        raise ValueError("SMPTE time division is not supported")
    o = 14
    tracks, tempos = [], []
    for _ in range(ntracks):
        if d[o:o + 4] != b"MTrk":
            raise ValueError("bad track chunk")
        ln = struct.unpack(">I", d[o + 4:o + 8])[0]
        b = d[o + 8:o + 8 + ln]
        o += 8 + ln
        i = tick = run = 0
        name, on, notes = "", {}, []

        def vlq():
            nonlocal i
            v = 0
            while True:
                c = b[i]
                i += 1
                v = v << 7 | c & 0x7F
                if c < 0x80:
                    return v
        while i < len(b):
            tick += vlq()
            st = b[i]
            if st == 0xFF:
                ty = b[i + 1]
                i += 2
                n = vlq()
                data = b[i:i + n]
                i += n
                if ty == 0x03:
                    name = data.decode("latin-1").strip()
                elif ty == 0x51:
                    tempos.append((tick, int.from_bytes(data, "big")))
                continue
            if st in (0xF0, 0xF7):
                i += 1
                i += vlq()
                continue
            if st & 0x80:
                run = st
                i += 1
            kind = run & 0xF0
            args = b[i:i + (1 if kind in (0xC0, 0xD0) else 2)]
            i += len(args)
            if kind == 0x90 and args[1] > 0:
                on.setdefault(args[0], []).append((tick, args[1]))
            elif kind in (0x80, 0x90):
                if on.get(args[0]):
                    start, vel = on[args[0]].pop(0)
                    if tick > start:
                        notes.append((start, tick, args[0], vel))
        tracks.append((name, sorted(notes)))
    return tracks, division, sorted(tempos) or [(0, 500000)]


def voices(notes):
    """Splits overlapping notes into monophonic lines (each track of the format is one voice)."""
    lines = []
    for n in sorted(notes):
        for line in lines:
            if line[-1][1] <= n[0]:
                line.append(n)
                break
        else:
            lines.append([n])
    return lines


def convert(path, ticks_per_quarter, loop=True, end_tick=None):
    """MIDI file -> sequence. `ticks_per_quarter`: sequencer ticks per quarter note (from the
    tempo; see TICK_MS). Each named track's notes become as many voices as its chords need."""
    tracks, division, tempos = read_midi(path)
    scale = ticks_per_quarter / division
    # The song's length: the end of the last note (a loop must not wait for trailing silence).
    last = end_tick or max(n[1] for _, notes in tracks for n in notes)
    out = []
    for name, notes in tracks:
        if not notes:
            continue
        try:
            program = int(name)
        except ValueError:
            raise ValueError(f"track {name!r}: name it after its BIOS program number (0-127)")
        notes = [n for n in notes if n[0] < last]
        for line in voices(notes):
            events, t = [], 0
            vel = max(n[3] for n in line)
            for start, end, note, _ in line:
                s, e = round(start * scale), round(min(end, last) * scale)
                if s > t:
                    events.append((0, s - t))
                if e > s:
                    events.append((note, e - s))
                    t = e
            total = round(last * scale)
            if total > t:
                events.append((0, total - t))
            out.append(track(program, min(0x7F, vel), events, loop))
    return sequence(out), len(out)


if __name__ == "__main__":
    seq, n = convert(sys.argv[1], int(sys.argv[3]) if len(sys.argv) > 3 else 48)
    open(sys.argv[2], "wb").write(seq)
    print(f"{n} voices, {len(seq)} bytes -> {sys.argv[2]}")


# ---------------------------------------------------------------- arranging for the hardware

VOICES = 5     # pitched voices 0-4 of the sound chip (Ribbit io/voices.rs); the BIOS's songs use 3-6 tracks
TICK_MS = 4    # one sequencer tick (VERIFIED-EMU: 100 ticks of a note and of a rest each last 400 ms)


def song_end(notes, division, gap_quarters=32):
    """End of the song: the last note end before a silence of `gap_quarters` or more (stray
    notes far after the music, e.g. a forgotten chord minutes later, are left out)."""
    end = 0
    for s, e, *_ in sorted(notes):
        if end and s - end > gap_quarters * division:
            break
        end = max(end, e)
    return end


def arrange(path, voices=VOICES, loop=True, drums=None, report=None):
    """MIDI file -> sequence for `voices` hardware voices. Track names are BIOS program numbers.
    Every note takes a free voice (a voice changes instrument between notes with 0x89); when all
    are busy the least important sounding note is cut, or the new one dropped. Importance: the
    velocity, plus the top note of the moment (melody), the lowest (bass) and `drums` tracks
    (default: tracks whose notes span more than five octaves, as percussion kits do)."""
    tracks, division, tempos = read_midi(path)
    us_per_quarter = tempos[0][1]
    scale = us_per_quarter / 1000 / TICK_MS / division        # MIDI ticks -> sequencer ticks
    notes = []
    for name, ns in tracks:
        if not ns:
            continue
        try:
            program = int(name)
        except ValueError:
            raise ValueError(f"track {name!r}: name it after its BIOS program number (0-127)")
        notes += [(s, e, n, v, program) for s, e, n, v in ns]
    if drums is None:
        span = {}
        for _, _, n, _, p in notes:
            lo, hi = span.get(p, (n, n))
            span[p] = (min(lo, n), max(hi, n))
        drums = {p for p, (lo, hi) in span.items() if hi - lo > 60}
    end = song_end(notes, division)
    notes = sorted((s, min(e, end), n, v, p) for s, e, n, v, p in notes if s < end)

    def importance(note):
        s, e, n, v, p = note
        now = [x for x in notes if x[0] <= s < x[1]]
        bonus = 40 if p in drums else 0
        if n == max(x[2] for x in now if x[4] not in drums or p in drums):
            bonus += 30
        if n == min(x[2] for x in now):
            bonus += 20
        return v + bonus

    rank = {note: importance(note) for note in notes}
    lines = [[] for _ in range(voices)]   # per voice: [start, end, note, velocity, program]
    dropped = cut = 0
    for note in notes:
        s = note[0]
        free = [k for k in range(voices) if not lines[k] or lines[k][-1][1] <= s]
        if free:
            same = [k for k in free if lines[k] and lines[k][-1][4] == note[4]]
            k = (same or free)[0]
        else:
            k = min(range(voices), key=lambda k: rank[tuple(lines[k][-1][:5])] if len(lines[k][-1]) == 5 else 0)
            weakest = lines[k][-1]
            if rank[tuple(weakest)] >= rank[note]:
                dropped += 1
                continue
            weakest[1] = s        # cut the weaker note short
            cut += 1
        lines[k].append(list(note))
    out = []
    total = round(end * scale)
    for line in lines:
        body = bytearray()
        prog = vol = None
        t = 0
        for s, e, n, v, p in line:
            a, b = round(s * scale), round(e * scale)
            if b <= a:
                continue
            if a > t:
                body += _events([(0, a - t)])
            if p != prog:
                body += bytes([0x89, p])
                prog = p
            if v != vol:
                body += bytes([0x88, min(0x7F, v)])
                vol = v
            body += _events([(n, b - a)])
            t = b
        if total > t:
            body += _events([(0, total - t)])
        head = bytes([0x8E, LOOP_FOREVER]) if loop else b""
        tail = bytes([0x8F, 0]) if loop else b""
        out.append(head + bytes(body) + tail + bytes([0xFF, 0]))
    if report is not None:
        report.update(drums=sorted(drums), notes=len(notes), dropped=dropped, cut=cut, seconds=total * TICK_MS / 1000,
                      voices_used=sum(1 for l in lines if l))
    return sequence(out)


def _events(events):
    out = bytearray()
    for note, ticks in events:
        while ticks > 0:
            d = min(ticks, 0x7FFF)
            out += bytes([note]) + dur(d)
            ticks -= d
    return bytes(out)
