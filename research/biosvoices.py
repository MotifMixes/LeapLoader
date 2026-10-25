"""Research tool: exports the Leapster 2 BIOS's built-in sounds (the narrator's voice lines,
e.g. the sign-in screen's "if you see your name, touch it", and the menu sound effects) as
WAV files, by having the console itself play them in the emulator and recording its output.

The voice lines are compressed in a format whose decoder is ARC code in the BIOS (not
reimplemented here), so the BIOS decodes them: a tiny SD-menu movie plays sound N each time
A is pressed, and research/sdboot-emu records each one to its own file.

Usage: python biosvoices.py OUTDIR [--api LF_PlayFgGAS] [--first 0x2000] [--count 836]
                            [--slot MS] [--approval CART.bin]

The output contains LeapFrog's recordings, so keep it private (never commit or share it).
"""
import argparse
import os
import struct
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swfgen import AS, approval_fields, do_action, pack_rib, show_frame, swf  # noqa: E402

EMU = "D:/leaploader-tmp/target-emu/release/sdboot-emu.exe"
BIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Ribbit", "roms", "bios",
                    "leapster2", "152-12206_0.6.bin")  # Ribbit checked out beside LeapLoader
STATE = "D:/leaploader-tmp/lfpmenu/menu.state"   # home screen right after tapping the SD icon
APPROVAL = "D:/leaploader-tmp/native/carts/1st-Grade_Leapster_EN.bin"
BTN_A = 4096
HZ = 8000


def build_player(api, first, approval):
    """SD menu movie: each A press stops all audio and plays api(lfh(first + k)), k = 0, 1, ..."""
    a = AS()
    a.push("k", 0).raw(0x1D)
    h = AS()
    h.getvar("bits").getvar("changed").op("and").push(BTN_A).op("and").op("not").if_true("end")
    h.callv("LF_StopAllAudio")
    h.callv(api, AS().call("lfh", AS().getvar("k").push(first).op("add")))
    h.push("k").getvar("k").push(1).op("add").raw(0x1D)
    h.label("end")
    a.define_function("onBtn", ["bits", "changed"], h)
    # Button events, as menugen.py (LeapsterASLibrary's pattern: LF_RegisterCallback, type 3).
    ctor = AS().getvar("this").push("callbackFunction").getvar("cb").op("setmember") \
        .getvar("this").push("ret1", "").op("setmember").getvar("this").push("ret2", "").op("setmember") \
        .push(3, 1).getvar("this").push("doRegister").op("callmethod").op("pop")
    a.define_function("ButtonEvents", ["cb"], ctor)
    a.getvar("ButtonEvents").push("prototype").op("getmember").push("doRegister").getvar("LF_RegisterCallback").op("setmember")
    call = AS().getvar("this").push("ret2").op("getmember").getvar("this").push("ret1").op("getmember") \
        .push(2).getvar("this").push("callbackFunction").op("callmethod").op("pop")
    a.getvar("ButtonEvents").push("prototype").op("getmember").push("doCall").define_function("", [], call).op("setmember")
    a.push("buttonEvents").getvar("onBtn").push(1, "ButtonEvents").op("newobject").raw(0x1D)
    a.op("stop")
    movie = swf([do_action(a), show_frame()], bg=0x203040, frame_rate=20)
    return pack_rib([movie], title="BIOS sounds", part="LL-SOUNDS", approval=approval)


def read_wav(path):
    with wave.open(path) as w:
        return list(struct.unpack(f"<{w.getnframes()}h", w.readframes(w.getnframes())))


def write_wav(path, s):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(HZ)
        w.writeframes(struct.pack(f"<{len(s)}h", *s))


def trim(s, level=64, pad=HZ // 50):
    """Cuts the silence before and after the sound (keeps 20 ms on each side)."""
    loud = [i for i, v in enumerate(s) if abs(v) > level]
    if not loud:
        return []
    return s[max(0, loud[0] - pad):loud[-1] + pad]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--api", default="LF_PlayFgGAS")
    p.add_argument("--first", default="0x2000")
    p.add_argument("--count", type=int, default=836)
    p.add_argument("--slot", type=int, default=8000, help="ms recorded per sound")
    p.add_argument("--approval", default=APPROVAL)
    p.add_argument("--prefix", default="")
    args = p.parse_args()
    first = int(args.first, 0)
    work = os.path.join(args.out, "_work")
    raw = os.path.join(work, "raw")
    menu_dir = os.path.join(work, "tree", "Leapster", "System", "SDMenu")
    os.makedirs(menu_dir, exist_ok=True)
    os.makedirs(raw, exist_ok=True)
    with open(os.path.join(menu_dir, "SDMenu.bin"), "wb") as f:
        f.write(build_player(args.api, first, approval_fields(open(args.approval, "rb").read())))
    # The menu loads after `card`; one press per sound, recorded from the press until the next.
    lines = [f"load {STATE}", "card", "run 12000"]
    for k in range(args.count):
        lines += ["audio", "hold a", "run 100", "release a", f"run {args.slot - 100}", f"audio {raw}/{k:04d}.wav"]
    script = os.path.join(work, "script.txt")
    open(script, "w").write("\n".join(lines) + "\n")
    r = subprocess.run([EMU, "--bios", BIOS, "--tree", os.path.join(work, "tree"), "--script", script,
                        "--out", os.path.join(work, "shots"), "--shot-every", "600000"], capture_output=True, text=True)
    open(os.path.join(work, "emu.txt"), "w").write(r.stdout + r.stderr)
    long_ones, silent = [], []
    for k in range(args.count):
        s = read_wav(f"{raw}/{k:04d}.wav")
        t = trim(s)
        if not t:
            silent.append(k)
            continue
        if any(abs(v) > 64 for v in s[-HZ // 10:]):
            long_ones.append(k)  # still sounding when the next press came: cut
        write_wav(os.path.join(args.out, f"{args.prefix}{first + k:04x}.wav"), t)
    print(f"{args.count - len(silent)} sounds written, silent: {len(silent)}, cut at {args.slot} ms: {long_ones}")


if __name__ == "__main__":
    main()
