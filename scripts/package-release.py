"""Builds a Windows release zip of LeapLoader (modelled on Ribbit's scripts/package-release.py).

Run:    python -I scripts/package-release.py [--skip-build]
Output: <target>/dist/LeapLoader-<version>-windows-x64.zip
        (<target>: $LEAPLOADER_TARGET, default D:/leaploader-tmp/target-release)

The zip holds the app (LeapLoader.exe), nativescan.exe, the ARC binutils the save stubs are
assembled with (arc-gnu\\, from Ribbit's tools/arc-gnu or $ARC_GNU), the research scripts the
card build runs (research\\, only the ones mkcard imports), a read-me written here, the licence and
the third-party notices. It is assembled in a fresh staging folder from named files, so no dump,
save or other local file can end up inside; any other file is refused, and so is any file holding
the build machine's home folder or a personal email.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = Path(os.environ.get("LEAPLOADER_TARGET", "D:/leaploader-tmp/target-release"))
DIST = TARGET / "dist"
ARC_GNU = Path(os.environ.get("ARC_GNU", ROOT.parent / "Ribbit" / "tools" / "arc-gnu"))
# The binutils the scripts call (eestub, nativechip, streamstub: as, ld, nm, objcopy).
ARC_TOOLS = ["arc-elf32-as.exe", "arc-elf32-ld.exe", "arc-elf32-nm.exe", "arc-elf32-objcopy.exe"]
# mkcard.py and everything it imports (sndgen for the welcome sound, musicrender for the music).
SCRIPTS = ["mkcard", "avm1patch", "bigimage", "biosbank2sf2", "eestub", "gamenames", "icongen", "ingame",
           "menugen", "musicrender", "nativechip", "pixelfont", "saveshim", "sdpack", "seqgen", "sndgen",
           "streamstub", "swfgen"]

README = """LeapLoader {version} - your own Leapster cartridges on a Leapster 2's SD card
===========================================================================

LeapLoader converts your own Leapster cartridge dumps so they run from an SD
card on a Leapster 2, with a menu to pick a game, working saves, and
HINT + A + B to go back to the menu. No games and no BIOS are included: you
need dumps of your own cartridges.

So far LeapLoader has been tested only in the Ribbit emulator, NOT on a real
Leapster 2. Use it at your own risk, and copy your SD card's files somewhere
before you start.

User guide:      https://github.com/MotifMixes/LeapLoader/blob/main/docs/manual/01-welcome.md
Compatible games: https://github.com/MotifMixes/LeapLoader/blob/main/docs/compatibility.md

What you need
-------------
* Windows 10 or 11 (64-bit).
* Python 3.8 or newer, as "python" on the PATH (python.org; tick "Add
  python.exe to PATH"). The card is built by Python scripts in research\\.
* For the menu's music (optional): the Python packages numpy and scipy
  ("pip install numpy scipy") and a dump of your Leapster 2's BIOS 0.6
  (152-12206). LeapLoader finds the one Ribbit uses, or choose it in
  Settings. Without them the menu works, silently.
* A Leapster 2 (not the first Leapster or the L-MAX: they have no SD card).

Starting
--------
Unzip the folder anywhere and keep its files together (LeapLoader.exe uses
nativescan.exe, arc-gnu\\ and research\\ beside it).

1. Run LeapLoader.exe.
2. Add your dumps (.bin or .zip), or Import Ribbit's Rom Folder.
   Games LeapLoader can't convert start switched off.
3. Choose the output folder: the SD card's drive (or any folder, then copy
   its contents to the card's root).
4. Build. On the Leapster 2, the SD icon on the home screen opens
   LeapLoader's menu.

In a game, hold HINT + A + B (2.5 s; up to 4 s on screens without the
prompt) to save and go back to the menu.

Leapster 2 over USB (untested on real hardware) writes the card while it
stays in the console; see TESTING-USB.txt, and please send the USB log.

LeapLoader is free software under the GNU GPL v3 or later (LICENSE.txt). It
is not affiliated with or endorsed by LeapFrog Enterprises. It was written
almost entirely by an AI coding assistant under its author's direction (see
the project's read-me).
"""

BINUTILS_NOTICE = """
----------------------------------------------------------------------------
GNU binutils (arc-gnu\\: arc-elf32-as, -ld, -nm, -objcopy)
----------------------------------------------------------------------------
GNU binutils 2.45.1, ARCompact/ARCv2 elf32 toolchain build 10504, unmodified,
from the arc-2026.03 release of
https://github.com/foss-for-mips-arc-processors/toolchain
Copyright (C) 2025 Free Software Foundation, Inc. GNU General Public License
v3 (the same text as LICENSE.txt). The corresponding source is published with
that release and at https://ftp.gnu.org/gnu/binutils/. LeapLoader runs these
programs to assemble the small ARC stubs it adds to each game; it contains no
binutils code.
"""


def personal_info(stage):
    """Files in `stage` holding the build machine's home folder, any user folder path, a
    development path or the git email: (file, what) pairs. A release must have none."""
    home = str(Path.home().resolve())
    needles = {home, home.replace("\\", "/"), "C:\\Users\\", "C:/Users/", "/Users/", "/home/", "leaploader-tmp"}
    email = subprocess.run(["git", "config", "user.email"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if email and not email.endswith("@users.noreply.github.com"):
        needles.add(email)
    found = []
    for f in sorted(p for p in Path(stage).rglob("*") if p.is_file()):
        data = f.read_bytes()
        found += [(f.relative_to(stage), n) for n in sorted(needles) if n.encode() in data]
    return found


def version():
    text = (ROOT / "app" / "Cargo.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        sys.exit("no version in app/Cargo.toml")
    return m.group(1)


def release_env():
    """Rust flags that keep this PC's folders out of the programs (panic messages name source files)."""
    home = str(Path.home().resolve())
    target = str(TARGET.resolve())
    flags = [f"--remap-path-prefix={home}=~", f"--remap-path-prefix={ROOT}=leaploader",
             f"--remap-path-prefix={target}=target", f"--remap-path-prefix={target.replace(chr(92), '/')}=target",
             "--cfg", "leaploader_release"]
    return dict(os.environ, CARGO_ENCODED_RUSTFLAGS="\x1f".join(flags))


def crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args()
    ver = version()
    if not a.skip_build:
        env = release_env()
        for crate in ("app", "research/nativescan"):
            subprocess.run(["cargo", "build", "--release", "--target-dir", str(TARGET)], cwd=ROOT / crate, env=env,
                           check=True)
    name = f"LeapLoader-{ver}-windows-x64"
    stage = DIST / name
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "arc-gnu").mkdir(parents=True)
    (stage / "research").mkdir()
    files = {"LeapLoader.exe": TARGET / "release" / "leaploader.exe",
             "nativescan.exe": TARGET / "release" / "nativescan.exe"}
    files.update({f"arc-gnu/{t}": ARC_GNU / t for t in ARC_TOOLS})
    files.update({f"research/{s}.py": ROOT / "research" / f"{s}.py" for s in SCRIPTS})
    for dst, src in files.items():
        if not src.is_file():
            sys.exit(f"missing {src}")
        shutil.copy2(src, stage / dst)
    texts = {"README.txt": README.format(version=ver),
             "LICENSE.txt": (ROOT / "LICENSE").read_text(encoding="utf-8"),
             "THIRD-PARTY-NOTICES.txt": (ROOT / "app" / "THIRD-PARTY-NOTICES.txt").read_text(encoding="utf-8")
             + BINUTILS_NOTICE,
             "TESTING-USB.txt": (ROOT / "app" / "TESTING-USB.md").read_text(encoding="utf-8")}
    for dst, text in texts.items():
        (stage / dst).write_bytes(crlf(text))

    allowed = set(files) | set(texts)
    found = {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}
    if found != allowed:
        sys.exit(f"unexpected files in the package: {sorted(found ^ allowed)}")
    leaks = personal_info(stage)
    if leaks:
        for f, n in leaks:
            print(f"  {f}: contains {n!r}")
        sys.exit("the package holds personal information (paths or email); not packaged")

    out = DIST / f"{name}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(p for p in stage.rglob("*") if p.is_file()):
            # Times in UTC (zip stores local time, which would give away the time zone); in a
            # folder named LeapLoader, so a new release unzips over the last one.
            info = zipfile.ZipInfo(f"LeapLoader/{f.relative_to(stage).as_posix()}",
                                   date_time=time.gmtime(f.stat().st_mtime)[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, f.read_bytes(), compresslevel=9)
    print(f"{out} ({out.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
