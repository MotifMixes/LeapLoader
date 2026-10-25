"""Prototype (research): sounds for LeapLoader's SWF movies.

Two ways to play a sound on the Leapster 2:

* **Raw A-law on a voice** (`load_alaw`, used for the menu's welcome sound): 8 kHz G.711 A-law
  in a resource 0x1006/5 table, played with LF_PlayAudioRaw(lfh(handle)), as the BIOS's own
  sounds. The voice output is the clip as it is (VERIFIED-EMU: the BIOS's select sound comes
  out matching its A-law source, correlation 0.99999).
* **SWF ADPCM** (`define_sound`): the Flash player's own sounds; Talking Words Factory streams
  its stories as ADPCM, 11025 Hz, mono. Here: any audio file -> 11025 Hz mono PCM (ffmpeg) ->
  Flash ADPCM (4-bit codes, 4096-sample packets) in a DefineSound tag, started by StartSound.
  Decoded exactly as `adpcm_decode`, but the player mixes SWF sound into the 32 kHz PCM DAC
  stream through a band-pass of about 300-5500 Hz, at every SWF rate (VERIFIED-EMU, measured on
  white noise: under 250 Hz -30 to -40 dB and incoherent, flat 350-5000 Hz). A voice loses its
  low end and sounds thin next to the BIOS's narrator, so speech should use the A-law path.

Usage: python sndgen.py IN_AUDIO OUT.wav   (ADPCM round trip: encode, decode, write a WAV to listen to)
"""
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swfgen import bits, tag  # noqa: E402

RATE = 11025
ALAW_RATE = 8000
RATE_CODE = 1  # SWF rate field: 0 = 5.5k, 1 = 11k, 2 = 22k, 3 = 44k

STEPS = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80,
         88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598,
         658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327,
         3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289,
         16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]
INDEX_ADJ = [-1, -1, -1, -1, 2, 4, 6, 8]
PACKET = 4096


def load_pcm(path, peak=0.9):
    """Any audio file -> list of 16-bit samples, 11025 Hz mono, normalised to `peak` of full scale."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    s = list(struct.unpack(f"<{len(raw) // 2}h", raw))
    top = max(1, max(abs(x) for x in s))
    return [round(x * peak * 32767 / top) for x in s]


def load_alaw(path, peak=0.9):
    """Any audio file -> 8 kHz mono G.711 A-law bytes (ffmpeg resamples and encodes), normalised
    to `peak` of full scale."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(ALAW_RATE), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    s = struct.unpack(f"<{len(raw) // 2}h", raw)
    top = max(1, max(abs(x) for x in s))
    pcm = struct.pack(f"<{len(s)}h", *(round(x * peak * 32767 / top) for x in s))
    return subprocess.run(["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(ALAW_RATE), "-ac", "1", "-i", "-",
                           "-f", "alaw", "-"], input=pcm, capture_output=True, check=True).stdout


def _step(pred, index, code):
    step = STEPS[index]
    diff = step >> 3
    if code & 4:
        diff += step
    if code & 2:
        diff += step >> 1
    if code & 1:
        diff += step >> 2
    pred = max(-32768, min(32767, pred - diff if code & 8 else pred + diff))
    return pred, max(0, min(88, index + INDEX_ADJ[code & 7]))


def adpcm_encode(samples):
    """Flash ADPCM, mono, 4-bit: UB[2] code size (2 = 4 bits), then per packet SB[16] first sample,
    UB[6] step index, and up to 4095 4-bit codes; bits MSB first."""
    fields = [(2, 2)]
    for start in range(0, len(samples), PACKET):
        packet = samples[start:start + PACKET]
        pred, index = packet[0], 0
        # A first step index that fits the packet's opening slope (UB[6]: at most 63).
        if len(packet) > 1:
            d = abs(packet[1] - packet[0])
            while index < 63 and STEPS[index] < d:
                index += 1
        fields += [(pred, 16), (index, 6)]
        for x in packet[1:]:
            diff = x - pred
            code = 8 if diff < 0 else 0
            diff = abs(diff)
            step = STEPS[index]
            if diff >= step:
                code |= 4
                diff -= step
            if diff >= step >> 1:
                code |= 2
                diff -= step >> 1
            if diff >= step >> 2:
                code |= 1
            pred, index = _step(pred, index, code)
            fields.append((code, 4))
    return bits(fields)


def adpcm_decode(data, count):
    """The decoder side (for checking the encoder)."""
    n = int.from_bytes(data, "big")
    total = len(data) * 8
    pos = 0

    def take(w):
        nonlocal pos
        pos += w
        return (n >> (total - pos)) & ((1 << w) - 1)
    take(2)
    out = []
    while len(out) < count:
        pred = take(16)
        pred -= (pred & 0x8000) << 1
        index = take(6)
        out.append(pred)
        for _ in range(min(PACKET - 1, count - len(out))):
            pred, index = _step(pred, index, take(4))
            out.append(pred)
    return out


def define_sound(sound_id, samples):
    """DefineSound (14): ADPCM, 11 kHz, 16-bit, mono."""
    flags = 1 << 4 | RATE_CODE << 2 | 1 << 1
    return tag(14, struct.pack("<HBI", sound_id, flags, len(samples)) + adpcm_encode(samples))


def start_sound(sound_id):
    """StartSound (15): play `sound_id` once."""
    return tag(15, struct.pack("<HB", sound_id, 0))


if __name__ == "__main__":
    import wave
    pcm = load_pcm(sys.argv[1])
    back = adpcm_decode(adpcm_encode(pcm), len(pcm))
    err = sum((a - b) ** 2 for a, b in zip(pcm, back)) / len(pcm)
    sig = sum(a * a for a in pcm) / len(pcm)
    import math
    print(f"{len(pcm)} samples, {len(pcm) / RATE:.2f} s, ADPCM {len(adpcm_encode(pcm))} bytes, "
          f"SNR {10 * math.log10(sig / max(err, 1e-9)):.1f} dB")
    with wave.open(sys.argv[2], "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack(f"<{len(back)}h", *back))
