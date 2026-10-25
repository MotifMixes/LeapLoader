"""Prototype (research): renders a MIDI file with the Leapster 2 BIOS's own instruments into one
looping 8 kHz A-law clip for LeapLoader's menu (played with LF_PlayAudioRaw, like the welcome sound).

Why not the BIOS sequencer (seqgen.py): it has 5 pitched voices, so a song with more notes at once
loses notes (the user's 13-track song lost ~800). A rendered clip keeps every note of every track.

How each note is rendered (as the console's note-on code plays it, biosbank2sf2.py):
* the program's zone is the first whose high key >= the note (BIOS 0x4003_36D4);
* pitch: source samples per 1/8000 s = noteFrequency(note) x scale / 32768, with the BIOS's own
  frequency table (0x400F_D2B0, A4 = 440 Hz; equal temperament, also used for key 0);
* notes after the song's end (a silence of 32 quarters or more, seqgen.song_end) are left out;
* the A-law sample plays from its start, looping between loop start and loop end (inclusive) when
  the zone loops, and stops at the note's end (a 5 ms fade, as the SoundFont the song was written
  with releases at once);
* loudness: velocity as a SoundFont's default curve, (velocity / 127)^2 (40 dB range).
Quality: every track is rendered on its own at 48 kHz in 32-bit float, from samples upsampled 16x
with a polyphase low-pass filter (near-ideal interpolation), so nothing is lost before the final
mix. Each track can be written as its own WAV (`stems_dir`) to check by ear. Notes still sounding
at the song's end carry over into the loop start (`loop_start`), so the loop is seamless. The mix is then
filtered and resampled to 8 kHz (the console's raw-sound rate), dithered and A-law encoded.

The rendered audio contains the BIOS's instrument samples: keep the stems and previews private
(local/ or D:\\leaploader-tmp), never commit them.

Usage: python musicrender.py SONG.mid OUT_DIR [LOOP_START_SECONDS]
       (OUT_DIR gets the stems, mix-48k.wav, music-8k.wav)
Track names are BIOS program numbers (0-127), as for seqgen.py.
"""
import os
import struct
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biosbank2sf2  # noqa: E402
import seqgen  # noqa: E402

RATE = 48000          # render rate
OUT_RATE = 8000       # LF_PlayAudioRaw's rate
UP = 16               # sample upsampling before interpolation
RELEASE_S = 0.005
FREQ_TABLE = 0x400F_D2B0
DEFAULT_BIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Ribbit", "roms", "bios",
                            "leapster2", "152-12206_0.6.bin")
B = biosbank2sf2.B
_ALAW = np.array([biosbank2sf2.alaw(c) for c in range(256)], dtype=np.float32) / 32768.0


def _zone_wave(bios, z, cache):
    """A zone's sample as float, upsampled UP times (cached by address range)."""
    key = (z["start"], z["end"])
    if key not in cache:
        raw = np.frombuffer(bios[z["start"] - B:z["end"] - B], dtype=np.uint8)
        cache[key] = resample_poly(_ALAW[raw].astype(np.float64), UP, 1).astype(np.float32)
    return cache[key]


# ---- The 8 kHz clip. Two things limit it: nothing above 4 kHz (the raw-sound rate) and A-law's
# 8 bits, whose rounding noise is white, ~38 dB under the music: next to the quiet highs it was
# heard as crackle (user, 2026-10-25: "muffled and kinda distorted crackly").
CUTOFF = 3850        # Hz: the anti-alias low-pass, flat to ~3.7 kHz (was resample_poly's, falling from ~3.4 kHz)
SHELF_DB = 3.0       # brightness: a gentle lift above ~2 kHz, where the 4 kHz limit dulls the sound most
SHAPE_G1, SHAPE_G2 = 0.94, 0.6   # noise shaping: the noise follows the music's spectrum (below)
SHAPE_ORDER, SHAPE_FRAME = 10, 256


def _interp_response(f):
    """|H(f)| of the 8 -> 32 kHz interpolator that plays the clip in Ribbit (MAME's, ribbit-audio
    INTERP: a 64-tap Kaiser sinc with its cutoff at 3.9 kHz)."""
    from scipy.signal import firwin, freqz
    h = firwin(64, 3900, window=("kaiser", 6.0), fs=32000) * 4
    _, r = freqz(h, worN=np.asarray(f, dtype=np.float64), fs=32000)
    return np.abs(r)


def to_8k(x):
    """48 kHz float -> 8 kHz: a steep low-pass at CUTOFF, then an EQ that undoes the interpolator's
    fall near 4 kHz (at most +6 dB) and adds the SHELF_DB lift."""
    from scipy.signal import firwin, firwin2
    lp = firwin(1201, CUTOFF, window=("kaiser", 10.0), fs=RATE)
    y = resample_poly(x, 1, RATE // OUT_RATE, window=lp)
    f = np.linspace(0, OUT_RATE / 2, 65)
    gain = np.minimum(1 / np.maximum(_interp_response(f), 1e-3), 2.0)
    gain *= 10 ** (SHELF_DB / 20 / (1 + np.exp(-(f - 2000) / 250)))  # smooth step around 2 kHz
    gain[-1] = 0.0
    eq = firwin2(63, f, gain, fs=OUT_RATE)
    return np.convolve(y, eq, mode="same")


def _lpc(x, order):
    """Autocorrelation LPC (Levinson): a[0] = 1, A(z) = sum a[k] z^-k."""
    r = np.array([np.dot(x[:len(x) - k], x[k:]) for k in range(order + 1)])
    if r[0] <= 0:
        return np.r_[1.0, np.zeros(order)]
    r[0] *= 1.0001  # (white-noise correction: keeps A(z) well inside the unit circle)
    a, err = np.r_[1.0, np.zeros(order)], r[0]
    for i in range(1, order + 1):
        k = -np.dot(a[:i], r[i:0:-1]) / err
        a[:i + 1] = a[:i + 1] + k * a[:i + 1][::-1]
        err *= 1 - k * k
    return a


def alaw_shaped(x):
    """Float in [-1, 1] -> A-law bytes with noise shaping: the rounding error is fed back so the
    noise added (output - input) has the spectrum A(z/G2) / A(z/G1), A from the music around each
    frame (LPC), as speech codecs weight theirs: the noise sits under the loud parts of the
    spectrum, where the music masks it, instead of evenly over the quiet highs. Each byte is the
    A-law code nearest the shaped value (ffmpeg's encoder truncates instead)."""
    import bisect
    values = (_ALAW * 32768.0).astype(np.float64)
    order_ = np.argsort(values)
    sv, codes = values[order_].tolist(), order_.tolist()
    mids = [(sv[k] + sv[k + 1]) / 2 for k in range(len(sv) - 1)]
    x = np.asarray(x, dtype=np.float64) * 32767.0
    out = bytearray(len(x))
    p = SHAPE_ORDER
    e_hist, r_hist = [0.0] * p, [0.0] * p     # most recent first
    win = np.hanning(2 * SHAPE_FRAME)
    for f0 in range(0, len(x), SHAPE_FRAME):
        seg = x[max(0, f0 - SHAPE_FRAME // 2):f0 + 3 * SHAPE_FRAME // 2]
        a = _lpc(seg * win[:len(seg)], p)
        b = (a[1:] * SHAPE_G2 ** np.arange(1, p + 1)).tolist()   # numerator A(z/G2)
        c = (a[1:] * SHAPE_G1 ** np.arange(1, p + 1)).tolist()   # denominator A(z/G1)
        for n in range(f0, min(f0 + SHAPE_FRAME, len(x))):
            q = 0.0
            for k in range(p):
                q += b[k] * e_hist[k] - c[k] * r_hist[k]
            v = x[n] + q
            j = bisect.bisect_left(mids, v)
            y = sv[j]
            out[n] = codes[j]
            e = y - v
            e_hist.insert(0, e); e_hist.pop()
            r_hist.insert(0, y - x[n]); r_hist.pop()
    return bytes(out)


def _seconds(tempos, division):
    """MIDI tick -> seconds, through the tempo map."""
    marks, t, sec, us = [], 0, 0.0, 500000
    for tick, new_us in tempos:
        sec += (tick - t) * us / 1e6 / division
        marks.append((tick, sec, new_us))
        t, us = tick, new_us

    def conv(tick):
        base_tick, base_sec, cur = 0, 0.0, 500000
        for mt, ms, mus in marks:
            if mt <= tick:
                base_tick, base_sec, cur = mt, ms, mus
        return base_sec + (tick - base_tick) * cur / 1e6 / division
    return conv


def render(midi_path, bios_path=DEFAULT_BIOS, stems_dir=None, report=None, loop_start=0.0, console_programs=()):
    """MIDI -> 8 kHz A-law bytes: the song once, from its start to its end. `loop_start`: where the
    song continues after its end (seconds), so notes ringing past the end are added there.
    `console_programs`: tracks the console plays itself on its sequencer's 5 voices (user
    2026-10-25: the drums, "have the drum part come through the real system", then the flute and
    bass): their notes are left out of the clip and come back in report["sequence"] (seqgen format,
    looping from `loop_start`, see console_voices / console_sequence), except key 0, which the
    sequencer cannot play (0 is a rest there), and notes that find no free voice: those stay in the
    clip. The clip's loop is then a whole number of sequencer ticks (4 ms), so the two keep time
    loop after loop."""
    bios = open(bios_path, "rb").read()
    programs = biosbank2sf2.read_bank(bios)
    freqs = struct.unpack_from("<128f", bios, FREQ_TABLE - B)
    tracks, division, tempos = seqgen.read_midi(midi_path)
    sec = _seconds(tempos, division)
    all_notes = [n for _, ns in tracks for n in ns]
    end_tick = seqgen.song_end([(s, e, n, v, 0) for s, e, n, v in all_notes], division)
    total = int(round(sec(end_tick) * RATE))
    release = int(RELEASE_S * RATE)
    ls_out = int(round(loop_start * RATE))
    if console_programs:
        tick = RATE * seqgen.TICK_MS // 1000
        total = ls_out + max(tick, int(round((total - ls_out) / tick)) * tick)
    cache, stems, counts = {}, [], []
    console_buf = np.zeros(total, dtype=np.float64)
    voices, on_console = [], set()
    if console_programs:
        wanted = [(sec(s), sec(min(e, end_tick)), int(name), note, vel, (name, k))
                  for name, ns in tracks if ns and int(name) in console_programs
                  for k, (s, e, note, vel) in enumerate(ns) if note and s < end_tick]
        voices = console_voices(wanted, loop_start, total / RATE)
        on_console = {n[5] for v in voices for n in v}
    for name, notes in tracks:
        if not notes:
            continue
        program = int(name)
        zones = programs[program]
        if not zones:
            raise ValueError(f"track {name}: BIOS program {program} has no instrument")
        buf = np.zeros(total, dtype=np.float64)
        kept = 0
        for k, (s, e, note, vel) in enumerate(notes):
            if s >= end_tick:
                continue
            z = next((z for z in zones if z["hi"] >= note), zones[-1])
            wave = _zone_wave(bios, z, cache)
            length = (z["end"] - z["start"])
            # (the table's entry 0 is a placeholder: key 0 is a rest in the sequencer, but a MIDI drum hit here)
            freq = freqs[note] if note else 440.0 * 2 ** ((note - 69) / 12)
            step = freq * z["scale"] / 32768.0 * OUT_RATE / RATE   # source samples per output sample
            a = int(round(sec(s) * RATE))
            n = int(round(sec(min(e, end_tick)) * RATE)) - a
            if n <= 0:
                continue
            n += release
            pos = step * np.arange(n, dtype=np.float64)
            ls, le = z["loop_start"] - z["start"], min(z["loop_end"] - z["start"] + 1, length)
            if le - ls >= 2:
                over = pos >= le
                pos[over] = ls + np.mod(pos[over] - ls, le - ls)
            else:
                n = min(n, int(np.searchsorted(pos, length - 1)))
                pos = pos[:n]
            if n <= 0:
                continue
            x = pos * UP
            i = np.minimum(x.astype(np.int64), len(wave) - 2)
            frac = x - i
            y = wave[i] * (1 - frac) + wave[i + 1] * frac
            env = np.ones(n)
            r = min(release, n)
            env[n - r:] = np.linspace(1, 0, r)
            y = y * env * (vel / 127.0) ** 2
            idx = a + np.arange(n)
            over = idx >= total                       # what rings past the end goes on at the loop start
            idx[over] = ls_out + (idx[over] - total) % (total - ls_out)
            if (name, k) in on_console:
                np.add.at(console_buf, idx, y)        # (counted for the level, not in the clip)
                continue
            np.add.at(buf, idx, y)
            kept += 1
        stems.append((name, buf))
        counts.append((name, kept, len(notes)))
    mix = sum(b for _, b in stems)
    peak = float(np.max(np.abs(mix))) or 1.0
    if stems_dir:
        os.makedirs(stems_dir, exist_ok=True)
        for k, (name, b) in enumerate(stems):
            wavfile.write(os.path.join(stems_dir, f"track{k + 1:02d}-program{name}.wav"), RATE,
                          (b / peak * 0.95).astype(np.float32))
        wavfile.write(os.path.join(stems_dir, "mix-48k.wav"), RATE, (mix / peak * 0.95).astype(np.float32))
    # 48 kHz -> 8 kHz, loop-aware: silence before the start (the first time), the loop start after
    # the end.
    pad = RATE // 10
    eight = lambda x: to_8k(np.concatenate([np.zeros(pad), x, x[ls_out:ls_out + pad]]))[
        pad * OUT_RATE // RATE:][:total * OUT_RATE // RATE]
    low = eight(mix)
    # The level as if the console's parts were in the clip too (the balance stays as composed).
    gain = 0.95 / (float(np.max(np.abs(eight(mix + console_buf) if on_console else low))) or 1.0)
    low *= gain
    alaw = alaw_shaped(low)
    if stems_dir:
        back = _ALAW[np.frombuffer(alaw, dtype=np.uint8)]
        wavfile.write(os.path.join(stems_dir, "music-8k.wav"), OUT_RATE, back.astype(np.float32))
    if report is not None:
        report.update(seconds=total / RATE, tracks=counts, notes=sum(c[1] for c in counts))
        if on_console:
            report.update(sequence=console_sequence(voices, loop_start, total / RATE, gain), seq_level=gain,
                          seq_notes=len(on_console))
    return alaw


# The volume command (88 v) -> the voice's volume register, at LF_SetBgMIDIVolume(SEQ_VOLUME)
# (VERIFIED-EMU 2026-10-25, BIOS 0.6: one drum note per volume, `voices` in sdboot-emu).
SEQ_VOLUME = 127
SEQ_LEAD_MS = 6.0
SEQ_VOLUME_CURVE = [(16, 0x1DAE), (32, 0x2456), (64, 0x33D0), (80, 0x3E0C), (100, 0x5016), (120, 0x6DA0), (127, 0x7F1E)]


def seq_volume_for(amplitude):
    """The volume command whose register comes nearest amplitude x 0x7FFF (the clip plays at
    raw volume 127 = register 0x7FFF), interpolated in dB between the measured points."""
    import math
    want = 20 * math.log10(max(amplitude, 1e-6))
    pts = [(v, 20 * math.log10(r / 0x7FFF)) for v, r in SEQ_VOLUME_CURVE]
    if want <= pts[0][1]:
        return max(1, round(pts[0][0] * 10 ** ((want - pts[0][1]) / 20)))  # (below the table: by amplitude)
    for (v0, d0), (v1, d1) in zip(pts, pts[1:]):
        if want <= d1:
            return round(v0 + (v1 - v0) * (want - d0) / (d1 - d0))
    return 127


def drum_programs(midi_path):
    """The drum tracks' programs: tracks spanning more than five octaves (a kit maps a sound to
    each key; seqgen.arrange's rule)."""
    tracks, _, _ = seqgen.read_midi(midi_path)
    return {int(name) for name, ns in tracks if ns and max(n[2] for n in ns) - min(n[2] for n in ns) > 60}


def _ticks(loop_start, end):
    # (every time SEQ_LEAD_MS early, loop point and end too: the console's part came in ~6 ms behind
    # the clip, VERIFIED-EMU 2026-10-25, the same in every loop)
    tick = lambda t: max(0, int(round((t * 1000 - SEQ_LEAD_MS) / seqgen.TICK_MS)))
    return tick, tick(loop_start), tick(end)


def console_voices(notes, loop_start, end):
    """[(start s, end s, program, key, velocity, id)] -> the sequencer's voices, each a list of
    (start tick, end tick, program, key, velocity, id): every note on the first voice free at its
    start, in time order; a note held over the loop point ends there; notes for which all
    seqgen.VOICES voices are busy are left out (they stay in the clip)."""
    tick, lt, et = _ticks(loop_start, end)
    voices = []
    for s, e, prog, key, vel, ident in sorted(notes, key=lambda n: (n[0], n[1])):
        a, b = tick(s), min(tick(e), et)
        if a < lt < b:
            b = lt
        if b <= a or a >= et:
            continue
        v = next((v for v in voices if v[-1][1] <= a), None)
        if v is None:
            if len(voices) == seqgen.VOICES:
                continue
            voices.append(v := [])
        v.append((a, b, prog, key, vel, ident))
    return voices


def console_sequence(voices, loop_start, end, level=1.0):
    """console_voices' voices as a sequence (seqgen.py), one track each: every event at its own
    time rounded to the 4 ms tick (no error builds up); the part before `loop_start` once, then the
    rest looping, as the clip. Loudness: as in the rendered clip (`level` x (velocity / 127)^2), by
    the volume command (88 v) before each note (seq_volume_for)."""
    tick, lt, et = _ticks(loop_start, end)
    out = []
    for v in voices:
        t = bytearray()
        at, prog_now, vol_now = 0, None, None

        def rest(to):
            nonlocal at
            while to > at:
                d = min(to - at, 0x7FFF)
                t.extend(bytes([0]) + seqgen.dur(d))
                at += d
        for part, (lo, hi) in enumerate(((0, lt), (lt, et))):
            if part == 1:
                rest(lt)
                t.extend(bytes([0x8E, seqgen.LOOP_FOREVER]))
                vol_now = prog_now = None          # (set again inside the loop)
            for a, b, prog, key, vel, _ in v:
                if not lo <= a < hi:
                    continue
                rest(a)
                if prog != prog_now:
                    t.extend(bytes([0x89, prog]))
                    prog_now = prog
                vol = seq_volume_for(level * (vel / 127.0) ** 2)
                if vol != vol_now:
                    t.extend(bytes([0x88, vol]))
                    vol_now = vol
                t.extend(bytes([key]) + seqgen.dur(b - a))
                at = b
            if part == 1:
                rest(et)
                t.extend(bytes([0x8F, 0]))
        out.append(bytes(t + bytes([0xFF, 0])))
    return seqgen.sequence(out)


if __name__ == "__main__":
    info = {}
    data = render(sys.argv[1], stems_dir=sys.argv[2], report=info,
                  loop_start=float(sys.argv[3]) if len(sys.argv) > 3 else 0.0)
    print(f"{info['seconds']:.2f} s loop, {info['notes']} notes, {len(data)} bytes of A-law")
    for name, kept, n in info["tracks"]:
        print(f"  program {name}: {kept} of {n} notes")
