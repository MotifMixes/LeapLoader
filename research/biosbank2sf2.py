"""Converts the Leapster 2 BIOS's built-in instrument bank (the sounds its
MIDI-style sequencer plays) into a SoundFont 2 file, for composing music that
will sound the same on the console. Reads the user's own BIOS dump; the output
contains LeapFrog's samples, so keep it private (do not commit or share it).

Usage: python biosbank2sf2.py BIOS.bin OUT.sf2

Format (VERIFIED-FW, Leapster 2 BIOS 0.6; see docs/sd-boot-proof.md for addresses):
* Resource 0x1006/2 of the BIOS (table at 0x4000_0628): {0x100, 0, first, count=128, ptr[128]},
  one pointer per program to its first zone record.
* Zone record, 20 bytes: u32 sample start, u32 sample end, u16 loop start, u16 loop end
  (low halves of addresses in the start's 64 KiB page), f32 scale, u8 low key, u8 high key, u16 level.
  The note-on code (0x4003_36D4) walks the records until high key >= note; the last zone has
  high key 0x7F.
* Pitch register = noteFrequencyHz(note) x scale (0x4003_31A4, frequency table at 0x400F_D2B0,
  A4 = 440), and 0x8000 = one sample per 1/8000 s. So the sample sounds at 32768 / scale Hz
  when played at 8 kHz.
* Samples are G.711 A-law, played at 8 kHz; a zone loops when loop end - loop start >= 2.
* `level` (+0x12) goes to the voice's 0x0180_4170/4184 registers: meaning UNKNOWN
  (envelope or volume); not applied here.
"""
import math
import struct
import sys

# General MIDI program names. The BIOS stores no names; its defined program numbers
# fit General MIDI (pianos at 0-1, organs at 16-21, guitar at 24...), so presets are
# labelled with these and a "?" (HYPOTHESIS until checked by ear).
GM = ["Acoustic Grand", "Bright Piano", "Electric Grand", "Honky-tonk", "E.Piano 1", "E.Piano 2",
      "Harpsichord", "Clavinet", "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba",
      "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ", "Perc. Organ", "Rock Organ",
      "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Bandoneon", "Nylon Guitar",
      "Steel Guitar", "Jazz Guitar", "Clean Guitar", "Muted Guitar", "Overdrive Gtr", "Distortion Gtr",
      "Gtr Harmonics", "Acoustic Bass", "Finger Bass", "Pick Bass", "Fretless Bass", "Slap Bass 1",
      "Slap Bass 2", "Synth Bass 1", "Synth Bass 2", "Violin", "Viola", "Cello", "Contrabass",
      "Tremolo Str", "Pizzicato Str", "Harp", "Timpani", "Strings", "Slow Strings", "Synth Str 1",
      "Synth Str 2", "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit", "Trumpet", "Trombone",
      "Tuba", "Muted Trumpet", "French Horn", "Brass", "Synth Brass 1", "Synth Brass 2", "Soprano Sax",
      "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet", "Piccolo",
      "Flute", "Recorder", "Pan Flute", "Bottle Blow", "Shakuhachi", "Whistle", "Ocarina",
      "Square Lead", "Saw Lead", "Calliope Lead", "Chiff Lead", "Charang", "Voice Lead", "Fifths Lead",
      "Bass+Lead", "New Age Pad", "Warm Pad", "Polysynth", "Choir Pad", "Bowed Pad", "Metal Pad",
      "Halo Pad", "Sweep Pad", "Rain FX", "Soundtrack FX", "Crystal FX", "Atmosphere", "Brightness",
      "Goblins FX", "Echoes FX", "Sci-Fi FX", "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba",
      "Bagpipe", "Fiddle", "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum",
      "Melodic Tom", "Synth Drum", "Reverse Cymbal", "Gtr Fret Noise", "Breath Noise", "Seashore",
      "Bird Tweet", "Telephone", "Helicopter", "Applause", "Gunshot"]

B = 0x4000_0000
PROGRAM_TABLE = 0x4000_0628  # BIOS 0.6 (B5 0x4000_0620, m9 0x4000_0624): see program_table


def program_table(d):
    """The BIOS's resource 0x1006/2, found through its LEAP directory (at [0x4000_0140], as in a
    cartridge), so every Leapster 2 BIOS works: 0.6, Connected B5, CIP3 m9 (2026-10-26)."""
    u32 = lambda a: struct.unpack_from("<I", d, a - B)[0]
    leap = u32(B + 0x140)
    if not B <= leap < B + len(d) or d[leap - B:leap - B + 4] != b"LEAP":
        return PROGRAM_TABLE
    for i in range(struct.unpack_from("<H", d, leap - B + 6)[0]):
        tag, count, lst = struct.unpack_from("<HHI", d, leap - B + 0x20 + 8 * i)
        if tag == 0x1006:
            for j in range(count):
                rid, _, v = struct.unpack_from("<HHI", d, lst - B + 8 * j)
                if rid == 2:
                    return v
    return PROGRAM_TABLE
DUMMY_LEN = 0x42  # a near-silent 66-byte sample used to fill unused key ranges


def alaw(c):
    """G.711 A-law to 16-bit linear (standard curve, as Ribbit's ribbit_audio)."""
    c ^= 0x55
    seg = (c & 0x70) >> 4
    t = (c & 0x0F) << 4
    if seg == 0:
        t += 8
    elif seg == 1:
        t += 0x108
    else:
        t = (t + 0x108) << (seg - 1)
    return t if c & 0x80 else -t


def read_bank(d):
    u32 = lambda a: struct.unpack_from("<I", d, a - B)[0]
    table = program_table(d)
    ver, _, first, count = struct.unpack_from("<4I", d, table - B)
    if ver != 0x100 or count != 128:
        raise SystemExit("no instrument table in this BIOS; is it a Leapster 2 BIOS dump?")
    programs = []
    for p in range(count):
        ptr = u32(table + 16 + 4 * p)
        zones = []
        if B <= ptr < B + len(d) - 20:
            a = ptr
            for _ in range(128):
                s, e, ls, le, scale, lo, hi, level = struct.unpack_from("<IIHHfBBH", d, a - B)
                if not (B <= s < e <= B + len(d)) or not (0 < scale < 1e5) or lo > hi:
                    zones = []
                    break
                page = s & 0xFFFF0000
                loop_start = page | ls
                if loop_start < s:
                    loop_start += 0x10000
                loop_end = page | le
                if loop_end < s:
                    loop_end += 0x10000
                zones.append(dict(start=s, end=e, loop_start=loop_start, loop_end=loop_end, scale=scale, lo=lo, hi=hi, level=level))
                if hi >= 0x7F:
                    break
                a += 20
        programs.append(zones)
    return programs


def chunk(cid, data):
    data = bytes(data)
    pad = b"\0" if len(data) % 2 else b""
    return cid + struct.pack("<I", len(data)) + data + pad


def list_chunk(kind, parts):
    return chunk(b"LIST", kind + b"".join(parts))


def name20(s):
    return s.encode("ascii", "replace")[:19].ljust(20, b"\0")


def build_sf2(d, programs, bank_name):
    # Samples (deduplicated by address range).
    samples, sample_index, smpl = [], {}, bytearray()
    for zones in programs:
        for z in zones:
            key = (z["start"], z["end"])
            if key in sample_index or z["end"] - z["start"] <= DUMMY_LEN:
                continue
            pcm = [alaw(c) for c in d[z["start"] - B:z["end"] - B]]
            first = len(smpl) // 2
            smpl += struct.pack(f"<{len(pcm)}h", *pcm) + b"\0" * 92  # 46 zero points after each sample
            freq = 32768.0 / z["scale"]
            exact = 69 + 12 * math.log2(freq / 440.0)
            root = min(127, max(0, round(exact)))
            corr = max(-99, min(99, round((root - exact) * 100)))
            looping = z["loop_end"] - z["loop_start"] >= 2
            sample_index[key] = len(samples)
            samples.append(dict(
                name=f"s{z['start']:08x}", start=first, end=first + len(pcm),
                ls=first + (z["loop_start"] - z["start"]) if looping else first,
                # The loop end is the last looped byte (some zones give the sample end itself).
                le=first + min(z["loop_end"] - z["start"] + 1, len(pcm)) if looping else first + len(pcm),
                root=root, corr=corr, looping=looping))
    # Instruments and presets: one instrument per defined program.
    inst, ibag, igen, phdr, pbag, pgen = [], [], [], [], [], []
    for p, zones in enumerate(programs):
        zs = [z for z in zones if (z["start"], z["end"]) in sample_index]
        if not zs:
            continue
        inst.append((f"{p:03d} {GM[p]}?", len(ibag)))
        for z in zs:
            si = sample_index[(z["start"], z["end"])]
            ibag.append((len(igen), 0))
            igen.append((43, z["lo"] | z["hi"] << 8))  # keyRange
            igen.append((54, 1 if samples[si]["looping"] else 0))  # sampleModes
            igen.append((53, si))  # sampleID (last)
        phdr.append((f"{p:03d} {GM[p]}?", p, 0, len(pbag)))
        pbag.append((len(pgen), 0))
        pgen.append((41, len(inst) - 1))  # instrument
    # terminal records
    inst.append(("EOI", len(ibag)))
    ibag.append((len(igen), 0))
    igen.append((0, 0))
    phdr.append(("EOP", 0, 0, len(pbag)))
    pbag.append((len(pgen), 0))
    pgen.append((0, 0))

    pd = []
    pd.append(chunk(b"phdr", b"".join(name20(n) + struct.pack("<HHHIII", pr, bk, bag, 0, 0, 0) for n, pr, bk, bag in phdr)))
    pd.append(chunk(b"pbag", b"".join(struct.pack("<HH", g, m) for g, m in pbag)))
    pd.append(chunk(b"pmod", b"\0" * 10))
    pd.append(chunk(b"pgen", b"".join(struct.pack("<HH", o, v) for o, v in pgen)))
    pd.append(chunk(b"inst", b"".join(name20(n) + struct.pack("<H", bag) for n, bag in inst)))
    pd.append(chunk(b"ibag", b"".join(struct.pack("<HH", g, m) for g, m in ibag)))
    pd.append(chunk(b"imod", b"\0" * 10))
    pd.append(chunk(b"igen", b"".join(struct.pack("<HH", o, v) for o, v in igen)))
    shdr = b"".join(name20(s["name"]) + struct.pack("<IIIIIBbHH", s["start"], s["end"], s["ls"], s["le"], 8000, s["root"], s["corr"], 0, 1) for s in samples)
    shdr += name20("EOS") + b"\0" * 26
    pd.append(chunk(b"shdr", shdr))
    info = list_chunk(b"INFO", [chunk(b"ifil", struct.pack("<HH", 2, 1)), chunk(b"isng", b"EMU8000\0"),
                                 chunk(b"INAM", bank_name.encode() + b"\0"),
                                 chunk(b"ICMT", b"Built by LeapLoader from the user's own BIOS dump. Private use only.\0")])
    sdta = list_chunk(b"sdta", [chunk(b"smpl", smpl)])
    pdta = list_chunk(b"pdta", pd)
    body = b"sfbk" + info + sdta + pdta
    return b"RIFF" + struct.pack("<I", len(body)) + body, len(samples), len(phdr) - 1


if __name__ == "__main__":
    d = open(sys.argv[1], "rb").read()
    programs = read_bank(d)
    sf2, ns, npres = build_sf2(d, programs, "Leapster 2 BIOS 0.6 instruments")
    open(sys.argv[2], "wb").write(sf2)
    print(f"{npres} presets, {ns} samples, {len(sf2) // 1024} KiB -> {sys.argv[2]}")
