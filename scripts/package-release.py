"""Builds a release package of LeapLoader for the system it runs on (modelled on Ribbit's
scripts/package-release.py, package-linux.py and package-mac.py).

Run:    python -I scripts/package-release.py [--skip-build]          (Windows, Linux, macOS)
Output: <target>/dist/LeapLoader-<version>-<system>.<zip|tar.gz>
        windows-x64.zip, linux-x64.tar.gz, macos-arm64.zip or macos-x64.zip (the Mac it runs on)
        (<target>: $LEAPLOADER_TARGET, default D:/leaploader-tmp/target-release on Windows,
        ~/.cache/leaploader/target-release on Linux, target/ in the repository on macOS)

The package holds, in a LeapLoader folder (macOS: inside LeapLoader.app/Contents/MacOS):
  the app, nativescan, the ARC binutils the save stubs are assembled with (arc-gnu: Ribbit's
  tools/arc-gnu on Windows, scripts/build-arc-binutils.sh elsewhere, or $ARC_GNU), the research
  scripts the card build runs (only the ones mkcard imports) and a Python of its own with numpy
  and scipy (python-build-standalone, checked against its SHA256SUMS), so players install nothing;
plus a read-me written here, the licence and the third-party notices. It is assembled in a fresh
staging folder from named files, so no dump, save or other local file can end up inside, and any
file holding the build machine's home folder, a development path or a personal email is refused.
"""
import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEM = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}[platform.system()]
ARCH = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
PACKAGE = f"{SYSTEM}-{ARCH}"
EXE = ".exe" if SYSTEM == "windows" else ""
DEFAULT_TARGET = {"windows": "D:/leaploader-tmp/target-release", "linux": "~/.cache/leaploader/target-release",
                  "macos": str(ROOT / "target")}[SYSTEM]
TARGET = Path(os.path.expanduser(os.environ.get("LEAPLOADER_TARGET", DEFAULT_TARGET)))
DIST = TARGET / "dist"
CACHE = TARGET / "package-cache"
# The binutils the scripts call (eestub, nativechip, streamstub: as, ld, nm, objcopy).
ARC_TOOLS = ["as", "ld", "nm", "objcopy"]
# mkcard.py and everything it imports (sndgen for the welcome sound, musicrender for the music).
SCRIPTS = ["mkcard", "avm1patch", "bigimage", "biosbank2sf2", "bioscall", "eestub", "gamenames", "icongen",
           "ingame", "menugen", "musicrender", "nativechip", "pixelfont", "saveshim", "sdpack", "seqgen", "sndgen",
           "streamstub", "swfgen"]


def imported_scripts():
    """The research scripts mkcard.py imports, directly or not (0.2.1 first missed bioscall)."""
    todo, seen = ["mkcard"], set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        for line in (ROOT / "research" / f"{name}.py").read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(?:import|from)\s+([A-Za-z_]\w*)", line)
            if m and (ROOT / "research" / f"{m.group(1)}.py").exists():
                todo.append(m.group(1))
    return seen
# The bundled Python: python-build-standalone's install_only build, and the music's packages.
PYTHON_RELEASE = "20261003"
PYTHON_VERSION = "3.12.15"
PYTHON_BUILDS = {"windows-x64": "x86_64-pc-windows-msvc", "linux-x64": "x86_64-unknown-linux-gnu",
                 "macos-arm64": "aarch64-apple-darwin", "macos-x64": "x86_64-apple-darwin"}
PYTHON_PACKAGES = ["numpy==2.2.6", "scipy==1.15.3"]
BUNDLE_ID = "io.github.motifmixes.leaploader"

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>LeapLoader</string>
  <key>CFBundleDisplayName</key><string>LeapLoader</string>
  <key>CFBundleIdentifier</key><string>{bundle_id}</string>
  <key>CFBundleVersion</key><string>{version}</string>
  <key>CFBundleShortVersionString</key><string>{version}</string>
  <key>CFBundleExecutable</key><string>leaploader</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""

START = {
    "windows": """Unzip it (right-click, Extract All...) and keep the LeapLoader folder
together: LeapLoader.exe uses the files beside it. Run LeapLoader.exe.""",
    "linux": """Unpack it (tar -xzf LeapLoader-...-linux-x64.tar.gz) and keep the
LeapLoader folder together. Run ./leaploader in it. Built on Ubuntu 22.04: it
runs on distributions with glibc 2.35 or later.""",
    "macos": """LeapLoader is not signed with an Apple Developer ID, so macOS stops it the
first time. Drag LeapLoader.app to Applications, then right-click (or
Control-click) it and choose Open, then Open again. If macOS says the app "is
damaged", run this once in Terminal:

    xattr -dr com.apple.quarantine /Applications/LeapLoader.app""",
}

README = """LeapLoader {version} - your own Leapster cartridges on a Leapster 2's SD card
===========================================================================

LeapLoader converts your own Leapster cartridge dumps so they run from an SD
card on a Leapster 2, with a menu to pick a game, working saves, and
HINT + A + B to go back to the menu. No games and no BIOS are included: you
need dumps of your own cartridges, and of your Leapster 2's BIOS (0.6,
Connected B5 or CIP3 m9), whose instruments play the menu's music.

So far LeapLoader has been tested only in the Ribbit emulator, NOT on a real
Leapster 2. Use it at your own risk, and copy your SD card's files somewhere
before you start.

User guide:       https://github.com/MotifMixes/LeapLoader/blob/main/docs/manual/01-welcome.md
Compatible games: https://github.com/MotifMixes/LeapLoader/blob/main/docs/compatibility.md

Starting
--------
Nothing else to install: everything LeapLoader needs comes with it.

{start}

1. Start LeapLoader. The first time it shows a note: read it and click
   Continue.
2. Add your dumps (.bin or .zip): Add roms..., Add a folder..., or Import
   Ribbit's Rom Folder. Games LeapLoader can't convert start switched off.
3. Your Leapster 2 BIOS: LeapLoader finds the one the Ribbit emulator uses;
   otherwise Build card asks you to choose it (File > Settings too).
4. Choose the output folder: the SD card's drive (or any folder, then copy
   its contents to the card's root).
5. Click Build card. On the Leapster 2, sign in as a player and tap the SD
   icon on the home screen: LeapLoader's menu opens.

In a game, hold HINT + A + B (2.5 s; up to 4 s on screens without the
prompt) to save and go back to the menu.

Leapster 2 over USB (untested on real hardware) writes the card while it
stays in the console; see TESTING-USB.txt, and please send the USB log.

Updates: when a new version is out, a green "Update to ..." button appears at
the top of LeapLoader; it downloads and installs it and restarts.

If LeapLoader closes or shows an error, send leaploader.log from its data
folder ({data}) with your report.

LeapLoader is free software under the GNU GPL v3 or later (LICENSE.txt). It
is not affiliated with or endorsed by LeapFrog Enterprises. It was written
almost entirely by an AI coding assistant under its author's direction (see
the project's read-me).
"""
DATA_FOLDER = {"windows": "%APPDATA%\\LeapLoader", "linux": "~/.config/leaploader",
               "macos": "~/.config/leaploader"}

BINUTILS_NOTICE = """
----------------------------------------------------------------------------
GNU binutils (arc-gnu: arc-elf32-as, -ld, -nm, -objcopy)
----------------------------------------------------------------------------
GNU binutils 2.45.1, unmodified. Windows: the ARCompact/ARCv2 elf32 toolchain
build 10504 from the arc-2026.03 release of
https://github.com/foss-for-mips-arc-processors/toolchain . Linux and macOS:
built from GNU's binutils-2.45.1.tar.xz by scripts/build-arc-binutils.sh.
Copyright (C) 2025 Free Software Foundation, Inc. GNU General Public License
v3 (the same text as LICENSE.txt). The corresponding source is published at
https://ftp.gnu.org/gnu/binutils/ (and with that toolchain release).
LeapLoader runs these programs to assemble the small ARC stubs it adds to
each game; it contains no binutils code.

----------------------------------------------------------------------------
Python, numpy and scipy (python/)
----------------------------------------------------------------------------
CPython {python} (python-build-standalone {release},
https://github.com/astral-sh/python-build-standalone), under the Python
Software Foundation License and the licences of the libraries it is built
with; numpy and scipy (BSD-3-Clause, with the licences of the libraries they
bundle). Each one's licence texts are in python/ (the interpreter's LICENSE
files, and the packages' *.dist-info folders).
"""


def run(*cmd, cwd=ROOT, env=None):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True, env=env)


def version():
    text = (ROOT / "app" / "Cargo.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        sys.exit("no version in app/Cargo.toml")
    return m.group(1)


def release_env():
    """Rust flags that keep this PC's folders out of the programs (panic messages name source files),
    and the release cfg (card::research_dir leaves out the source folder)."""
    home = str(Path.home().resolve())
    target = str(TARGET.resolve())
    # (The folder holding LeapLoader and Ribbit, whose crates nativescan uses: outside the home folder in
    # WSL, /mnt/c/...; rustc uses the last prefix that matches, so the more precise ones come later.)
    flags = [f"--remap-path-prefix={ROOT.parent}=src", f"--remap-path-prefix={home}=~",
             f"--remap-path-prefix={ROOT}=leaploader",
             f"--remap-path-prefix={target}=target", f"--remap-path-prefix={target.replace(chr(92), '/')}=target",
             "--cfg", "leaploader_release"]
    return dict(os.environ, CARGO_ENCODED_RUSTFLAGS="\x1f".join(flags))


def fetch(url, dest):
    """`url` into `dest` (kept in the cache: downloaded once)."""
    if not dest.exists():
        print(f"downloading {url}", flush=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.replace(dest)
    return dest


def bundled_python(payload):
    """python-build-standalone's install_only Python in payload/python, checked against the release's
    SHA256SUMS, with numpy and scipy installed (no .pyc files: they would hold this PC's paths)."""
    name = f"cpython-{PYTHON_VERSION}+{PYTHON_RELEASE}-{PYTHON_BUILDS[PACKAGE]}-install_only.tar.gz"
    base = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PYTHON_RELEASE}/"
    sums = fetch(base + "SHA256SUMS", CACHE / f"python-{PYTHON_RELEASE}-SHA256SUMS").read_text()
    want = next((line.split()[0] for line in sums.splitlines() if line.strip().endswith(name)), None)
    if not want:
        sys.exit(f"{name} is not in the release's SHA256SUMS")
    archive = fetch(base + name.replace("+", "%2B"), CACHE / name)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != want:
        archive.unlink()
        sys.exit(f"{name}: checksum does not match SHA256SUMS (deleted; run again)")
    with tarfile.open(archive) as t:
        t.extractall(payload)  # its single top folder is python/
    python = payload / "python" / ("python.exe" if SYSTEM == "windows" else "bin/python3")
    run(python, "-I", "-m", "pip", "install", "--no-compile", "--disable-pip-version-check", "--no-cache-dir",
        "--no-warn-script-location", *PYTHON_PACKAGES)
    # numpy's command-line launchers hold the staging folder's path, and LeapLoader runs none of them.
    for tool in ("f2py", "numpy-config"):
        for launcher in (payload / "python" / "Scripts" / f"{tool}.exe", payload / "python" / "bin" / tool):
            launcher.unlink(missing_ok=True)
    # What mkcard never uses: Python's own tests, IDLE, Tk, the packages' test suites.
    py = payload / "python"
    lib = py / "Lib" if SYSTEM == "windows" else next((py / "lib").glob("python3.*"))
    unused = [lib / n for n in ("test", "idlelib", "tkinter", "turtledemo", "ensurepip", "turtle.py")]
    if SYSTEM == "windows":
        unused += [py / "tcl", *py.glob("DLLs/_tkinter.pyd"), *py.glob("DLLs/tcl*.dll"), *py.glob("DLLs/tk*.dll")]
    else:
        # (Tcl/Tk's script folders: lib/tcl8.6, lib/tk8.6, lib/itcl4..., lib/thread2...; never on Windows,
        # where lib/ is Lib/ and holds threading.py.)
        unused += [d for d in py.glob("lib/*") if d.is_dir() and re.match(r"(tcl|tk|itcl|thread)\d", d.name)]
    unused += list(lib.glob("lib-dynload/_tkinter*"))
    site = lib / "site-packages"
    # (numpy imports one of its own test modules: only scipy's go.)
    unused += [d for d in site.glob("scipy/**/tests") if d.is_dir()]
    for p in unused:
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    # (-B: no .pyc files, which would hold this staging folder's path.)
    run(python, "-I", "-B", "-c", "import numpy, scipy.signal, scipy.io.wavfile, zlib, struct; "
        "print('python ok: numpy', numpy.__version__)")
    for cache in list(py.rglob("__pycache__")):
        shutil.rmtree(cache)
    return python


def arc_binutils(payload):
    out = payload / "arc-gnu"
    out.mkdir()
    if SYSTEM == "windows":
        src = Path(os.environ.get("ARC_GNU", ROOT.parent / "Ribbit" / "tools" / "arc-gnu"))
    else:
        src = Path(os.environ.get("ARC_GNU", CACHE / f"arc-gnu-{PACKAGE}"))
        if not (src / "arc-elf32-as").exists():
            run("sh", ROOT / "scripts" / "build-arc-binutils.sh", src, CACHE / "binutils-work")
    for t in ARC_TOOLS:
        f = src / f"arc-elf32-{t}{EXE}"
        if not f.is_file():
            sys.exit(f"missing {f}")
        shutil.copy2(f, out / f.name)


def personal_info(stage):
    """Files in `stage` holding the build machine's home folder, a development path or the git
    email: (file, what) pairs. LeapLoader's own files are also checked for any user-folder path
    (the bundled Python's sources and documentation mention such paths as examples)."""
    home = str(Path.home().resolve())
    needles = {home, home.replace("\\", "/"), "leaploader-tmp", str(ROOT), str(ROOT).replace("\\", "/")}
    email = subprocess.run(["git", "config", "user.email"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if email and not email.endswith("@users.noreply.github.com"):
        needles.add(email)
    ours = needles | {"C:\\Users\\", "C:/Users/", "/Users/", "/home/"}
    # On GitHub's machines the home folder is the runner's (/Users/runner), which is also where the
    # numpy and scipy wheels were built: their libraries hold it, and it says nothing about anyone.
    theirs = needles - {home, home.replace("\\", "/")} if os.environ.get("GITHUB_ACTIONS") else needles
    found = []
    for f in sorted(p for p in Path(stage).rglob("*") if p.is_file() and not p.is_symlink()):
        data = f.read_bytes()
        check = theirs if "python" in f.relative_to(stage).parts else ours
        found += [(f.relative_to(stage), n) for n in sorted(check) if n.encode() in data]
    return found


def crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n") if SYSTEM == "windows" else text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args()
    if PACKAGE not in PYTHON_BUILDS:
        sys.exit(f"no package for {PACKAGE}")
    ver = version()
    if not a.skip_build:
        env = release_env()
        for crate in ("app", "research/nativescan"):
            run("cargo", "build", "--release", "--target-dir", TARGET, cwd=ROOT / crate, env=env)
    name = f"LeapLoader-{ver}-{PACKAGE}"
    stage = DIST / name
    if stage.exists():
        shutil.rmtree(stage)
    if SYSTEM == "macos":
        app = stage / "LeapLoader.app" / "Contents"
        # Contents/MacOS holds only programs (everything there must be signed code); the scripts and
        # the Python go in Contents/Resources (card::package_resources).
        payload = app / "MacOS"
        resources = app / "Resources"
        payload.mkdir(parents=True)
        resources.mkdir()
        (app / "Info.plist").write_text(INFO_PLIST.format(version=ver, bundle_id=BUNDLE_ID), encoding="utf-8")
        docs = stage
    else:
        payload = resources = stage / "LeapLoader"
        payload.mkdir(parents=True)
        docs = payload
    program = "LeapLoader.exe" if SYSTEM == "windows" else "leaploader"
    shutil.copy2(TARGET / "release" / f"leaploader{EXE}", payload / program)
    shutil.copy2(TARGET / "release" / f"nativescan{EXE}", payload / f"nativescan{EXE}")
    (resources / "research").mkdir()
    missing = imported_scripts() - set(SCRIPTS)
    if missing:
        sys.exit(f"SCRIPTS lacks research scripts mkcard imports: {', '.join(sorted(missing))}")
    for s in SCRIPTS:
        shutil.copy2(ROOT / "research" / f"{s}.py", resources / "research" / f"{s}.py")
    arc_binutils(payload)
    bundled_python(resources)
    texts = {"README.txt": README.format(version=ver, start=START[SYSTEM], data=DATA_FOLDER[SYSTEM]),
             "LICENSE.txt": (ROOT / "LICENSE").read_text(encoding="utf-8"),
             "THIRD-PARTY-NOTICES.txt": (ROOT / "app" / "THIRD-PARTY-NOTICES.txt").read_text(encoding="utf-8")
             + BINUTILS_NOTICE.format(python=PYTHON_VERSION, release=PYTHON_RELEASE),
             "TESTING-USB.txt": (ROOT / "app" / "TESTING-USB.md").read_text(encoding="utf-8")}
    for dst, text in texts.items():
        (docs / dst).write_bytes(crlf(text).encode("utf-8"))
    if SYSTEM != "windows":
        for f in [payload / program, payload / "nativescan", *(payload / "arc-gnu").iterdir()]:
            f.chmod(0o755)

    # Only the named parts: the program, its helpers, the scripts, the Python, the texts.
    expected = {program, f"nativescan{EXE}", "research", "arc-gnu", "python"}
    if docs == payload:
        expected |= set(texts)
    found = {p.name for p in payload.iterdir()} | {p.name for p in resources.iterdir()}
    if found != expected:
        sys.exit(f"unexpected files in the package: {sorted(found ^ expected)}")
    leaks = personal_info(stage)
    if leaks:
        for f, n in leaks:
            print(f"  {f}: contains {n!r}")
        sys.exit("the package holds personal information (paths or email); not packaged")

    if SYSTEM == "macos":
        # Signed ad hoc (no Developer ID): every program and library inside (Python's, numpy's, scipy's,
        # binutils, nativescan: --deep only reaches nested bundles), then the app.
        macho = (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe")
        code = [f for f in [*payload.rglob("*"), *resources.rglob("*")] if f.is_file() and not f.is_symlink()
                and f.open("rb").read(4) in macho and f.name != "leaploader"]
        for i in range(0, len(code), 200):
            run("codesign", "--force", "--sign", "-", *code[i:i + 200])
        run("codesign", "--force", "--sign", "-", stage / "LeapLoader.app")
        run("codesign", "--verify", "--strict", stage / "LeapLoader.app")
        out = DIST / f"{name}.zip"
        out.unlink(missing_ok=True)
        run("ditto", "-c", "-k", "--keepParent", "--sequesterRsrc", stage, out)
    elif SYSTEM == "linux":
        out = DIST / f"{name}.tar.gz"

        def clean(info):
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            return info

        with tarfile.open(out, "w:gz", format=tarfile.PAX_FORMAT) as t:
            t.add(payload, arcname="LeapLoader", filter=clean)
    else:
        out = DIST / f"{name}.zip"
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for f in sorted(p for p in payload.rglob("*") if p.is_file()):
                # Times in UTC (zip stores local time, which would give away the time zone); in a
                # folder named LeapLoader, so a new release unzips over the last one.
                info = zipfile.ZipInfo(f"LeapLoader/{f.relative_to(payload).as_posix()}",
                                       date_time=time.gmtime(max(f.stat().st_mtime, 315532800))[:6])
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes(), compresslevel=9)
    print(f"{out} ({out.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
