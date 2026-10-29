"""Prototype (research): builds the files for a LeapLoader SD card from cartridge dumps.

Usage: python mkcard.py [--menu leaploader|MENU.lfp|SDMenu.bin] [--music SONG.mid] [--music-loop SECONDS]
                        [--console drums,PROGRAM,...] [--short PROGRAM,...] [--floor PROGRAM:VELOCITY,...]
                        [--welcome SOUND|none] [--bios LEAPSTER2_BIOS.bin]
                        OUT_DIR DUMP.bin|FOLDER|HOMEBREW_FOLDER [...]
(--welcome: the sound LeapLoader's menu plays when it starts; default assets/welcome.alaw, made from welcome.mp3)
(--music: background music for LeapLoader's menu: a MIDI file whose track names are BIOS program
 numbers, rendered with the BIOS's instruments into a looping clip, musicrender.py; --music-loop: where
 the music starts again after its end, e.g. 20.21; default 0; --console: tracks the console's own
 sequencer plays instead of the clip, by BIOS program number, "drums" = the drum tracks; default drums;
 --short: tracks whose notes play their sample once, without looping it; --floor: a track's softer notes
 play at that velocity)
(--bios: a Leapster 2 BIOS dump (0.6, B5 or m9) whose instruments render the music; --music needs it)
(folders: every .bin in them)

OUT_DIR receives, ready to copy to the root of the card:
  Leapster/System/SDMenu/SDMenu.bin   the menu the home screen's SD icon boots: LeapLoader's
                                      (default), or LeapFrog's own SD menu taken from the user's
                                      .lfp package (e.g. LSTR-0x00130001-000000.lfp) or SDMenu.bin
  Leapster/Apps/<Game>/game.bin       each supported game, converted for SD, with saves
  Leapster/Apps/<Game>/meta.inf       LeapFrog's fields (BinFile, Icon, ProfileAccess for the
                                      console's three players, ...), read by both menus
  Leapster/Apps/<Game>/icon.swf       the game's button in LeapFrog's menu (icongen.py)
  Leapster/Apps/LeapLoader/home.txt   LeapLoader's Home button boots this (no game: the console goes
                                      back to its own menu, menugen.HOME_PATH)
Games are named from gamenames.py (known dumps), else the file name, else the cartridge's title.
Unsupported dumps are listed with the reason and skipped. The approval fields the
BIOS checks are copied from the first supported dump (see swfgen.approval_fields).
"""
import os
import re
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gamenames  # noqa: E402
import icongen  # noqa: E402
import menugen  # noqa: E402
import sdpack  # noqa: E402
from swfgen import approval_fields  # noqa: E402


def title_of(image):
    """The cartridge's title (0x1003/0x0B), or None."""
    u32 = lambda o: struct.unpack_from("<I", image, o)[0]
    base = u32(0x11C)
    leap = u32(0x140) - base
    for i in range(struct.unpack_from("<H", image, leap + 6)[0]):
        tag, cnt, ptr = struct.unpack_from("<HHI", image, leap + 0x20 + 8 * i)
        if tag == 0x1003:
            for j in range(cnt):
                rid, _, v = struct.unpack_from("<HHI", image, ptr - base + 8 * j)
                if rid == 0x0B and base <= v < base + len(image):
                    o = v - base
                    return image[o:image.index(b"\0", o)].decode("latin-1")
    return None


def product_id(image):
    """The cartridge's product ID (0x1003/0x01), or 0."""
    u32 = lambda o: struct.unpack_from("<I", image, o)[0]
    base = u32(0x11C)
    leap = u32(0x140) - base
    for i in range(struct.unpack_from("<H", image, leap + 6)[0]):
        tag, cnt, ptr = struct.unpack_from("<HHI", image, leap + 0x20 + 8 * i)
        if tag == 0x1003:
            for j in range(cnt):
                rid, _, v = struct.unpack_from("<HHI", image, ptr - base + 8 * j)
                if rid == 0x01:
                    return v
    return 0


def meta_inf(title, folder, image):
    """meta.inf in the layout of LeapFrog's downloads (factory card, .lfp packages).
    ProfileAccess keeps the quotes the BIOS's SD_GetNumGames was tested with."""
    clean = title.replace('"', "'")
    fields = [("MetaVersion", '"1.0"'), ("Device", '"Leapster"'), ("Type", '"Application"'),
              ("ProductID", f"0x{product_id(image):08X}"), ("PackageID", f'"{folder}"'),
              ("PartNumber", '"000-00000"'), ("Version", '"1.0.0.0"'), ("Locale", '"en-us"'),
              ("Name", f'"{clean}"'), ("ShortName", f'"{folder[:8]}"'), ("Publisher", '"LeapLoader"'),
              ("Developer", '"LeapLoader"'), ("Hidden", "0"), ("Depends", ""),
              ("ProfileAccess", '"0,1,2"'), ("Icon", '"icon.swf"'), ("BinFile", '"game.bin"')]
    return "".join(f"{k}={v}\r\n" for k, v in fields).encode("latin-1", "replace")


def leapfrog_menu(path):
    """SDMenu.bin and its meta.inf from LeapFrog's .lfp package (a zip), or a bare SDMenu.bin."""
    import zipfile
    if not zipfile.is_zipfile(path):
        return open(path, "rb").read(), None
    z = zipfile.ZipFile(path)
    names = {n.lower(): n for n in z.namelist()}
    bin_name = next((n for k, n in names.items() if k.endswith("sdmenu.bin")), None)
    if bin_name is None:
        raise SystemExit(f"{path}: no SDMenu.bin in the package")
    folder = bin_name.lower()[:-len("sdmenu.bin")]
    meta = next((n for k, n in names.items() if k == folder + "meta.inf"), None)
    return z.read(bin_name), z.read(meta) if meta else None


def folder_name(title, used):
    """A unique folder name for the game (the caller adds it to `used` once the game is kept)."""
    base = re.sub(r"[^A-Za-z0-9]", "", title)[:16] or "Game"
    name, n = base, 2
    while name.lower() in used:
        name, n = f"{base[:14]}{n}", n + 1
    return name


def console_programs(music, spec):
    """--console: "drums" (musicrender.drum_programs) and BIOS program numbers, comma-separated."""
    import musicrender
    out = set()
    for part in filter(None, (p.strip() for p in (spec or "").split(","))):
        out |= musicrender.drum_programs(music) if part == "drums" else {int(part)}
    return out


# The BIOSes the music can be rendered with: every Leapster 2 BIOS (the same instruments; their
# tables are found wherever each keeps them, biosbank2sf2.program_table, musicrender.freq_table).
LEAPSTER2_BIOSES = {0xFA94D9A7: "0.6 (152-12206)", 0x4D223022: "Connected B5 (152-12076)",
                    0x57BDE604: "CIP3 m9 (152-12659)"}


def music_bios_problem(bios):
    """Why `bios` can't render the menu music, or None if it can."""
    if not bios or not os.path.isfile(bios):
        return "no Leapster 2 BIOS given (--bios)"
    if zlib.crc32(open(bios, "rb").read()) not in LEAPSTER2_BIOSES:
        return (f"{os.path.basename(bios)} is not a Leapster 2 BIOS (0.6 152-12206, Connected B5 152-12076 or "
                f"CIP3 m9 152-12659)")
    return None


HOMEBREW_MANIFEST = "app.txt"


def is_homebrew(path):
    """A homebrew package: a folder with app.txt (docs/homebrew.md)."""
    return os.path.isfile(os.path.join(path, HOMEBREW_MANIFEST))


def read_manifest(pkg):
    """app.txt: `key=value` lines (# comments); name and id are required."""
    m = {}
    for line in open(os.path.join(pkg, HOMEBREW_MANIFEST), encoding="utf-8-sig"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            m[k.strip().lower()] = v.strip()
    for k in ("name", "id"):
        if not m.get(k):
            raise ValueError(f"{HOMEBREW_MANIFEST} has no {k}=")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", m["id"]):
        raise ValueError("id= must be 1-16 letters, digits, _ or -")
    m.setdefault("image", "game.bin")
    return m


def copy_tree(src, dst, keep_existing=False):
    """Copies the folder src into dst (files only; keep_existing: never replace a file)."""
    import shutil
    for root, _, files in os.walk(src):
        d = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(d, exist_ok=True)
        for f in files:
            if not (keep_existing and os.path.exists(os.path.join(d, f))):
                shutil.copyfile(os.path.join(root, f), os.path.join(d, f))


def add_homebrew(out_dir, pkg, used):
    """Puts a homebrew package on the card: its image as Leapster/Apps/<id>/game.bin, files/ into that
    folder, card/ at the card's top (files already there are kept). Returns (title, menu path)."""
    m = read_manifest(pkg)
    image = open(os.path.join(pkg, m["image"]), "rb").read()
    if len(image) > 0x80_0000:
        raise ValueError(f"{m['image']} is larger than 8 MiB")
    if image[:4] != b"LEAP":
        raise ValueError(f"{m['image']} is not a Leapster 2 SD image (build it with the SDK's mkimage)")
    if m["id"].lower() in used:
        raise ValueError(f"another game on the card already uses the folder {m['id']}")
    d = os.path.join(out_dir, "Leapster", "Apps", m["id"])
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "game.bin"), "wb").write(image)
    if os.path.isdir(os.path.join(pkg, "files")):
        copy_tree(os.path.join(pkg, "files"), d)
    if os.path.isdir(os.path.join(pkg, "card")):
        copy_tree(os.path.join(pkg, "card"), out_dir, keep_existing=True)
    open(os.path.join(d, "meta.inf"), "wb").write(meta_inf(m["name"], m["id"], image))
    open(os.path.join(d, "icon.swf"), "wb").write(icongen.build_icon(m["name"]))
    used.add(m["id"].lower())
    return m["name"], f"{m['id']}\\game.bin"


def build(out_dir, dumps, menu="leaploader", music=None, welcome=None, music_loop=0.0, console="drums", short="",
          floor="", bios=None, homebrew=()):
    games, used, approval = [], {"leaploader"}, None  # (LeapLoader\home.txt: menugen.HOME_PATH)
    brewed = set()
    for pkg in homebrew:
        try:
            title, path = add_homebrew(out_dir, pkg, used)
        except (OSError, ValueError) as e:
            print(f"skip  {os.path.basename(os.path.normpath(pkg))}: homebrew: {e}")
            continue
        games.append((title, path))
        brewed.add(path)
        print(f"ok    {os.path.basename(os.path.normpath(pkg))} -> Leapster/Apps/{path.split(chr(92))[0]} ({title}, homebrew)")
    menu_name = "LeapLoader" if menu == "leaploader" else "SD Menu"  # named by the HINT + A + B prompt
    for path in dumps:
        image = open(path, "rb").read()
        label = os.path.basename(path)
        try:
            title = gamenames.known_name(image) or gamenames.from_filename(label) or title_of(image) or "Game"
            # The folder keeps the name earlier cards used (from the file name), so saves and the
            # recently played list stay with the game.
            folder = folder_name(re.sub(r"\s*[\(\[].*$", "", os.path.splitext(label)[0]).strip() or title, used)
            note, strict = "", True
            app_dir = f"b:\\Leapster\\Apps\\{folder}"
            fixed = sdpack.repair(image)
            if fixed is not image:
                import tempfile
                image, note = fixed, "; REPAIRED (dumping-tool marker removed)"
                with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as t:
                    t.write(image)
                try:
                    relocs = sdpack.relocs_for(t.name, image)  # nativescan reads the image from a file
                finally:
                    os.remove(t.name)
            else:
                relocs = sdpack.relocs_for(path, image)
            if not sdpack.checksum_ok(image):
                strict, note = False, "; CHECKSUM MISMATCH (dump may be damaged; converted anyway)"
            try:
                converted, _ = sdpack.convert(image, f"{app_dir}\\save.dat", relocs, strict, menu_name=menu_name,
                                              app_dir=app_dir)
                note += "".join(f"; {n}" for n in sdpack.convert.notes)
            except sdpack.Unsupported as e:
                if "save" not in str(e):
                    raise
                converted, _ = sdpack.convert(image, None, relocs, strict, menu_name=menu_name,
                                              app_dir=app_dir)  # plays, but cannot save
                note += f"; NO SAVES: {e}"
        except (sdpack.Unsupported, Exception) as e:
            print(f"skip  {label}: {e}")
            continue
        used.add(folder.lower())
        approval = approval or approval_fields(image)
        d = os.path.join(out_dir, "Leapster", "Apps", folder)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "game.bin"), "wb").write(converted)
        for name, data in sdpack.convert.files.items():  # resources kept on the card (images over 8 MiB)
            open(os.path.join(d, name), "wb").write(data)
        open(os.path.join(d, "meta.inf"), "wb").write(meta_inf(title, folder, image))
        open(os.path.join(d, "icon.swf"), "wb").write(icongen.build_icon(title))
        games.append((title, f"{folder}\\game.bin"))
        print(f"ok    {label} -> Leapster/Apps/{folder} ({title}){note}")
    if not games:
        raise SystemExit("no supported games: nothing to put on the card")
    d = os.path.join(out_dir, "Leapster", "System", "SDMenu")
    os.makedirs(d, exist_ok=True)
    if menu == "leaploader":
        seq = None
        if music:
            try:
                import musicrender
            except ImportError as e:  # numpy and scipy render the music
                missing = (e.name or "numpy").split(".")[0]
                musicrender, problem = None, f"Python is missing {missing} (pip install numpy scipy)"
            if musicrender:
                bios = bios or musicrender.DEFAULT_BIOS
                problem = music_bios_problem(bios)
            if problem:
                # The music is part of LeapLoader's menu (user's choice): no silent menu.
                raise SystemExit(f"the menu music can't be made: {problem}")
        if music:
            info = {}
            seq = musicrender.render(music, bios_path=bios, report=info, loop_start=music_loop,
                                     console_programs=console_programs(music, console),
                                     short_programs={int(p) for p in short.split(",") if p.strip()},
                                     velocity_floor={int(p.split(":")[0]): int(p.split(":")[1])
                                                     for p in floor.split(",") if p.strip()})
            print(f"music {os.path.basename(music)}: {info['seconds']:.1f} s, loops from {music_loop:.3f} s,"
                  f" {info['notes']} notes rendered"
                  f" with the BIOS's instruments, {len(seq) // 1024} KiB"
                  + (f"; drums played by the console: {info['seq_notes']} notes" if info.get("sequence") else ""))
        pcm = None
        if welcome:
            import sndgen
            pcm = sndgen.load_alaw(welcome)
        data, meta = menugen.build_menu(sorted(games, key=lambda g: g[0].lower()), approval, music=seq,
                                        welcome=pcm, music_loop=music_loop,
                                        music_seq=info.get("sequence") if music else None,
                                        seq_volume=musicrender.SEQ_VOLUME if music else None,
                                        homebrew=brewed), None
        what = (f"LeapLoader menu, {len(games)} games" + (", with music" if seq else "")
                + (f", welcome sound {len(pcm) / sndgen.ALAW_RATE:.1f} s" if pcm else ""))
    else:
        data, meta = leapfrog_menu(menu)
        what = f"LeapFrog's SD menu from {os.path.basename(menu)}"
    open(os.path.join(d, "SDMenu.bin"), "wb").write(data)
    if menu == "leaploader":
        home = os.path.join(out_dir, "Leapster", "Apps", *menugen.HOME_PATH.split("\\"))
        os.makedirs(os.path.dirname(home), exist_ok=True)
        open(home, "wb").write(menugen.HOME_TEXT)
    if meta:
        open(os.path.join(d, "META.INF"), "wb").write(meta)
    print(f"menu  {what} -> Leapster/System/SDMenu/SDMenu.bin")


if __name__ == "__main__":
    args = sys.argv[1:]
    menu, music, music_loop, console, short, floor, bios = "leaploader", None, 0.0, "drums", "", "", None
    welcome = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "welcome.alaw")
    while args[:1] in (["--menu"], ["--music"], ["--music-loop"], ["--welcome"], ["--console"], ["--short"], ["--floor"],
                       ["--bios"]):
        if args[0] == "--menu":
            menu = args[1]
        elif args[0] == "--music-loop":
            music_loop = float(args[1])
        elif args[0] == "--console":
            console = args[1]
        elif args[0] == "--short":
            short = args[1]
        elif args[0] == "--floor":
            floor = args[1]
        elif args[0] == "--bios":
            bios = args[1]
        elif args[0] == "--welcome":
            welcome = None if args[1] == "none" else args[1]
        else:
            music = args[1]
        args = args[2:]
    paths, brew = [], []
    for a in args[1:]:
        if os.path.isdir(a) and is_homebrew(a):
            brew.append(a)
        elif os.path.isdir(a):
            brew += sorted(os.path.join(a, f) for f in os.listdir(a) if is_homebrew(os.path.join(a, f)))
            paths += sorted(os.path.join(a, f) for f in os.listdir(a) if f.lower().endswith(".bin"))
        else:
            paths.append(a)
    build(args[0], paths, menu, music, welcome if welcome and os.path.exists(welcome) else None, music_loop, console,
          short, floor, bios, brew)
