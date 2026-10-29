"""Prototype (research): generates LeapLoader's SD menu, SDMenu.bin, for the
Leapster 2. The stock home screen's SD icon boots it (docs/sd-boot-proof.md);
it lists the games installed under \\Leapster\\Apps\\ and starts the chosen
one with the BIOS's BT_StartSDGame, which reboots into it.

Look: in the style of the console's own menus (purple sky with sparkles, glossy
green pill buttons, yellow glow on the selection, chunky shadowed text), with
Ribbit's frog as the mascot. Titles too long for their pill scroll (marquee)
while selected. All artwork is drawn here from scratch.

On the right of the list: a magnifying glass (opens the search keyboard) and up/down arrows
that move a page at a time (the D-pad's left/right do the same).

Buttons: Home goes back to the console (Sign In). Pause opens the options: Search
(an on-screen keyboard laid out like the console's name entry), Resume, Music on/off,
Sort A-Z / recently played, Leapster Home, About. Music, sort order and the recently
played games are kept in b:\\Leapster\\System\\SDMenu\\LeapLoader.txt.

Usage: python menugen.py OUT.bin APPROVAL_SOURCE.bin "Title|folder\\game.bin" ...
APPROVAL_SOURCE is one of the user's own cartridge dumps (its approval fields
are copied; see swfgen.approval_fields).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pixelfont import ADVANCE  # noqa: E402
from swfgen import (RAW_FIRST_HANDLE, SEQ_FIRST_HANDLE, AS, approval_fields, bitmap_rects, define_button, define_font, define_shape_layers,  # noqa: E402
                    define_sprite, define_text, do_action, method, pack_rib, place, place_enterframe, rounded_rects,
                    set_property, show_frame, swf, tag)

VERSION = "0.2.3"  # matches the desktop app (app/Cargo.toml; user, 2026-10-25); the menu was called v0.3.0 in earlier notes

TOP = 44            # list area top
PITCH = 24          # row pitch
PILL_X, PILL_W, PILL_H = 10, 140, 20  # (option rows)
ROW_W = 122         # game rows: narrower, the tool column is on their right
VISIBLE = 4         # rows visible
TEXT_X = 7          # title inset inside the pill
AVAIL = ROW_W - 2 * TEXT_X  # visible title width (pixels)
# Tool column (touch): search, page up, page down.
TOOL_X, TOOL_W = 138, 19
SEARCH_Y, UP_Y, DOWN_Y = TOP + 1, TOP + 25, TOP + VISIBLE * PITCH - 23
FOOTER = 150        # thin bar with the version number
PAUSE = 30          # marquee pause at the ends (frames, 20 fps); a newly selected title scrolls at once
SCROLL = 2          # marquee speed (pixels per frame)
SELECT_SOUND = 28   # lfh() number of LPSR_BROM_MenuSelect_6: the sign-in screen's chooseName plays it
LETTER_SOUND = 29   # lfh() number the sign-in keyboard plays for each letter (playEnterLetterSFX)
# The home screen's D-pad (doDPadNarr, BIOS movie 0x5B_01B8): lfh(29) for a move back, lfh(27) for a move on
# (LPSR_BROM_MenuUp_6 / MenuDown_6; lfh() of the names themselves plays the BIOS's error beep).
MOVE_UP_SOUND, MOVE_DOWN_SOUND = 29, 27
FLASH = 6           # frames a touched tool key stays lit
OK_DELAY = 8        # frames the OK key blinks before the search runs
BLINK = 2           # selection glow blinks on/off every BLINK frames while the sound plays
RAW_VOLUME = 127    # LF_SetRawVolume while the welcome sound starts (BIOS default 100 = voice volume 0x273E;
                    # 127 = 0x7FFF, +10 dB, VERIFIED-EMU), then back to 100 for the BIOS's own sounds
# Music: a rendered clip (musicrender.py) in two raw sounds, the intro (start to the loop point) and the
# loop (loop point to the end). Joins: tick() runs once a frame (50 ms), so it
# is late by up to a frame; it stops the part playing and starts the loop part where the music has got
# to, from one of MUSIC_JOINS entry points MUSIC_JOIN_MS apart (handles sharing the clip's bytes; the
# clip gets a copy of the loop's start after its end so the last entries have audio to play).
# Each part also runs on for RAW_RUNON bytes past its join: for a raw sound of 64 KiB or more the BIOS
# does not write the real end's low half but reads it back from the voice's start-low register
# (0x0180_40C8 + 8 x voice; BIOS 0x4003_64F8). Ribbit reads 0 there, so such a sound stopped at the
# 64 KiB boundary below its end (VERIFIED-EMU: 7 s early); what the hardware returns is UNVERIFIED.
# With 64 KiB more audio after the join, the part can only end after the join, whatever comes back.
RAW_RUNON = 0x10000 + 0x400
MUSIC_JOIN_MS, MUSIC_JOINS = 1, 80
MUSIC_JOIN_BACK = 8     # the first entries start this many steps before the loop point
MUSIC_JOIN_LEAD_MS = 7.0  # the next part comes in this much behind the music's place (it repeated 46-60
                          # samples at each join in Ribbit, VERIFIED-EMU), so an entry this much further on is used
MUSIC_VOLUME = 127  # LF_SetRawVolume while a music part starts (127 = voice volume 0x7FFF; back to 100 after)
LAUNCH_DELAY = 10   # frames from the choice to BT_StartSDGame: the sound ends ~390 ms after it (Ribbit)

# LF_BUTTON_*, as the games define them (button events, type 3).
BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT, BTN_A, BTN_B, BTN_HOME = 256, 512, 1024, 2048, 4096, 8192, 16384
# Pause is a system button (events of type 5: sysButton, bIsPressed, newSysValue), LF_PAUSE_BUTTON = 8,
# as the BIOS's UI_HandleSystemButtons reads it (VERIFIED-FW). onSys passes it to onBtn as this bit.
SYS_PAUSE, BTN_PAUSE = 8, 1 << 20
# Home: BT_StartSDGame with a file that does not exist. The console restarts, the SD copy fails
# ("CopyGameFromSdFatToRam failed") and the BIOS boots normally: logo, then Sign In (VERIFIED-EMU).
# BT_Execute("System"/"Application") and BT_SetNextBoot(0/1) do nothing from the SD menu.
# A file that does not exist makes the BIOS beep for ~7 s first ("CopyGameFromSdFatToRam failed",
# then a second restart). A file that exists but is no game is turned down at once, without a sound,
# and the console boots normally (VERIFIED-EMU 2026-10-25), so mkcard puts HOME_TEXT there.
HOME_PATH = "LeapLoader\\home.txt"
HOME_TEXT = b"LeapLoader: the menu's Home button points the console here to go back to the Leapster menu.\r\n"
SETTINGS = "b:\\Leapster\\System\\SDMenu\\LeapLoader.txt"  # "LL1|music|sort|recent path|...|"
RECENT_MAX = 10      # (the settings file is parsed one character at a time)

# Options (Pause): row 0 is the search box.
OPT_Y, OPT_PITCH, OPT_H = 30, 18, 15
OPTIONS = ["Search", "Resume", "Music", "Sort", "Leapster Home", "About"]
# Keyboard: the console's name-entry layout, 7 x 4 letter keys, then delete and OK.
KEYS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ. "
KEY_X, KEY_Y, KEY_PITCH, KEY_W = 3, 30, 22, 20
WIDE_Y, WIDE_W, DEL_X, CLR_X, OK_X = 120, 40, 3, 60, 117  # bottom row: delete, clear, OK
QMAX = 12           # longest search text
PAGE_SLOTS = 5      # page number glyphs ("20/20")
QCHARS = KEYS + "0123456789/"  # glyph frames: 1 = empty, 2 + i = QCHARS[i] (digits: the page number)

# Palette
SKY = [0x2E0B57, 0x3A0F6B, 0x48157D, 0x561C8D, 0x64239A, 0x7029A5, 0x7C30AE, 0x8837B6, 0x943FBD, 0x9F47C3]
SPARKLE = 0xFBE9FF
PILL_SHADOW, PILL_RIM, PILL_FILL, PILL_SHINE = 0x24083F, 0x147A2E, 0x2FB548, 0x7EDF80
GLOW = 0xFFD21F
TITLE, TITLE_SHADOW = 0xA090F0, 0x24083F  # title: the desktop app's heading purple (ui.rs PURPLE_LIGHT)
ROW_TEXT, ROW_SHADOW = 0xFFFFFF, 0x0E4D1E
FOOT_BG, FOOT_TEXT, FOOT_DIM = 0x24083F, 0xFFFFFF, 0xD7B8F0
FROG, FROG_DARK, FROG_WHITE = 0x3CBE5A, 0x10331A, 0xFFFFFF
BOX, BOX_RIM, BOX_TEXT, BOX_DIM = 0xFFFFFF, 0x24083F, 0x24083F, 0x9A86B0
KEY_FACE, KEY_SHINE, KEY_RIM, KEY_TEXT = 0xFFF3D6, 0xFFFFFF, 0x24083F, 0x3A0F6B

FROG_ART = [
    "..GGG......GGG..",
    ".GGGGG....GGGGG.",
    ".GdwGGGGGGGGdwG.",
    ".GddGGGGGGGGddG.",
    "GGGGGGGGGGGGGGGG",
    "GGGGGdGGGGdGGGGG",
    "GGGGGGGGGGGGGGGG",
    "GGdGGGGGGGGGGdGG",
    "GGGddddddddddGGG",
    "GGGGddddddddGGGG",
    "GGGGGGddddGGGGGG",
    ".GGGGGGGGGGGGGG.",
    "..GGGGGGGGGGGG..",
]

ICON_SEARCH = [
    "...####.....",
    "..##..##....",
    ".##....##...",
    ".#......#...",
    ".#......#...",
    ".##....##...",
    "..##..##....",
    "...#####....",
    ".......###..",
    "........###.",
    ".........###",
    "..........##",
]
ICON_UP = [
    ".....##.....",
    "....####....",
    "...######...",
    "..########..",
    ".##########.",
    "############",
    "....####....",
    "....####....",
    "....####....",
]
ICON_DOWN = ICON_UP[::-1]
# Homebrew badge (blue disc "B", white check "W"), right end of a homebrew game's row.
BADGE = [
    "...BBBB...",
    ".BBBBBBBB.",
    ".BBBBBBWB.",
    "BBBBBBWWBB",
    "BBWBBWWBBB",
    "BBWWWWBBBB",
    ".BBWWBBBB.",
    ".BBBBBBBB.",
    "...BBBB...",
]
BADGE_BLUE = 0x1D9BF0
BADGE_X = PILL_X + ROW_W - 4 - len(BADGE[0])

SPARKLES = [(12, 6), (58, 3), (97, 9), (148, 4), (30, 52), (152, 60), (4, 88), (156, 110), (6, 128), (80, 50),
            (118, 2), (40, 12)]

# Character ids
ID_FONT, ID_SKY_LIST, ID_SKY_TOP, ID_FROG = 1, 2, 3, 4
ID_PILL_BACK, ID_PILL_FILL, ID_PILL_SHINE, ID_GLOW, ID_PILL_HIT, ID_TEXT_MASK = 5, 6, 7, 8, 9, 10
ID_LIST, ID_HI, ID_TICKER, ID_FOOTER_BAR, ID_FOOTER_TEXT = 20, 21, 22, 15, 16
ID_HEAD_GAMES, ID_HEAD_SEARCH, ID_NONE = 17, 18, 19
ID_GLYPH_LIGHT, ID_GLYPH_DARK, ID_QLINE_LIGHT, ID_QLINE_DARK = 40, 41, 42, 43
ID_GLYPH_FOOT, ID_QLINE_FOOT, ID_PAGE, ID_PAGE_TEXT = 44, 45, 46, 47
ID_SKY_FULL, ID_OPTIONS, ID_OPT_BACK, ID_OPT_FILL, ID_OPT_SHINE, ID_OPT_GLOW, ID_OPT_HIT, ID_BOX = 60, 61, 62, 63, 64, 65, 66, 67
ID_ABOUT, ID_KEYBOARD, ID_KEY, ID_KEY_WIDE, ID_KEY_OK, ID_KEY_GLOW, ID_KEY_GLOW_WIDE, ID_KEY_HIT, ID_KEY_HIT_WIDE = \
    80, 90, 91, 92, 93, 94, 95, 96, 97
ID_CURSOR, ID_TOOL_GLOW = 98, 99
ID_TOOL_BOX, ID_TOOL_HIT, ID_TOOL_SEARCH, ID_TOOL_UP, ID_TOOL_DOWN = 100, 101, 102, 103, 104
ID_BTN_SEARCH, ID_BTN_UP, ID_BTN_DOWN, ID_SPR_SEARCH, ID_SPR_UP, ID_SPR_DOWN = 105, 106, 107, 108, 109, 110
ID_BADGE, ID_TEXT_MASK_HB = 111, 112
TEXT_BASE = 200     # static texts of the overlays, allocated upwards (below 1000)
ROW_TEXT_BASE, ROW_INNER, ROW_MASKED, ROW_BUTTON, ROW_SPRITE = 1000, 3000, 5000, 7000, 9000
GLYPH_TEXT_LIGHT, GLYPH_TEXT_DARK = 11000, 11100
OPT_BUTTON, KEY_BUTTON = 11200, 11300
GLYPH_TEXT_FOOT = 11500


def sky_layers(y0, y1):
    band = 160 // len(SKY)
    layers = []
    for i, c in enumerate(SKY):
        a, b = max(i * band, y0), min((i + 1) * band if i < len(SKY) - 1 else 160, y1)
        if a < b:
            layers.append((c, [(0, a, 160, b - a)]))
    layers.append((SPARKLE, [(x, y, 1, 1) for x, y in SPARKLES if y0 <= y < y1]
                   + [(x - 1, y + 1, 3, 1) for x, y in SPARKLES[:4] if y0 <= y + 1 < y1]
                   + [(x, y + 2, 1, 1) for x, y in SPARKLES[:4] if y0 <= y + 2 < y1]))
    return layers


def ascii_upper(title):
    """A title as the search keys hold it: capitals, other characters as "?"."""
    return "".join(c.upper() if " " <= c <= "~" else "?" for c in title)


def shadowed_text(text_id, lines, color, shadow, scale=1, offset=1):
    """Two DefineTexts: the shadow (id) and the text (id + 1)."""
    return [define_text(text_id, 1, [(x + offset, y + offset, shadow, s) for (x, y, s) in lines], scale=scale),
            define_text(text_id + 1, 1, [(x, y, color, s) for (x, y, s) in lines], scale=scale)]


# ---------------------------------------------------------------- ActionScript helpers

def V(name):
    return AS().getvar(name)


def N(*vals):
    return AS().push(*vals)


def cat(*parts):
    """Concatenates assembled expressions (strings are pushed)."""
    a = AS()
    for p in parts:
        if isinstance(p, AS):
            a.code.extend(p.code)
        else:
            a.push(p)
    return a


def binop(x, y, op):
    return cat(x, y).op(op)


def setv(a, name, expr):
    a.push(name)
    a.code.extend(expr.code)
    return a.raw(0x1D)


def local(a, name, expr):
    a.push(name)
    a.code.extend(expr.code)
    return a.raw(0x3C)


def goto_frame(a, path_expr, frame_expr):
    """tellTarget(path) gotoAndStop(frame): SetTarget2, GotoFrame2 (stop), SetTarget ''."""
    a.code.extend(path_expr.code)
    a.raw(0x20)
    a.code.extend(frame_expr.code)
    a.raw(0x9F, b"\x00")
    return a.raw(0x8B, b"\x00")


def visible(a, path, expr):
    return set_property(a, path, 7, expr)


_labels = [0]


def fresh(prefix):
    _labels[0] += 1
    return f"{prefix}{_labels[0]}"


def if_(a, cond, then, otherwise=None):
    """if (cond) then [else otherwise]; `then`/`otherwise` are callables appending to `a`."""
    l_else, l_end = fresh("else"), fresh("end")
    a.code.extend(cond.code)
    a.op("not").if_true(l_else)
    then(a)
    if otherwise:
        a.jump(l_end)
    a.label(l_else)
    if otherwise:
        otherwise(a)
        a.label(l_end)
    return a


def for_(a, var, start, stop_expr, body):
    """for (var = start; var < stop; var++) body (var is a local)."""
    top, end = fresh("for"), fresh("rof")
    local(a, var, N(start) if not isinstance(start, AS) else start)
    a.label(top)
    a.code.extend(binop(V(var), stop_expr, "lt").code)
    a.op("not").if_true(end)
    body(a)
    setv(a, var, binop(V(var), N(1), "add"))
    a.jump(top)
    a.label(end)
    return a


def slen(x):
    """StringLength opcode. String *methods* cost ~12 ms per character of the string on the Leapster's
    player (indexOf on a 69-character title: 0.93 s) and a script running over ~6 s freezes the
    player (VERIFIED-EMU); the opcodes take well under 1 ms. So the menu uses only opcodes on strings."""
    return cat(x).op("strlen")


def extract(x, start1, count):
    """StringExtract opcode: `count` characters from 1-based `start1`."""
    return cat(x, start1, count).op("substr")


def pressed(bit):
    """(p & bit) != 0 as a boolean: combined with others by BitAnd/BitOr, which need 1/0."""
    return binop(binop(V("p"), N(bit), "and"), N(0), "eq").op("not")


def play_sound(a, n):
    return a.callv("LF_PlayAudioRaw", AS().call("lfh", n))


# ---------------------------------------------------------------- artwork pieces

def glyph_sprite(sprite_id, text_base, color, tags):
    """A one-character display: frame 1 empty, frame 2 + i shows QCHARS[i]."""
    frames = [do_action(AS().op("stop")), show_frame()]
    for i, c in enumerate(QCHARS):
        tags.append(define_text(text_base + i, 1, [(0, 8, color, c)]))
        frames += [tag(28, (1).to_bytes(2, "little")), place(1, text_base + i, 0, 0), show_frame()]
    tags.append(define_sprite(sprite_id, frames, frames=1 + len(QCHARS)))


def qline_sprite(sprite_id, glyph_id, tags):
    """QMAX glyphs in a row, named c0..c{QMAX-1}."""
    tags.append(define_sprite(sprite_id, [place(1 + k, glyph_id, k * ADVANCE, 0, name=f"c{k}") for k in range(QMAX)]
                              + [show_frame()]))


class TextIds:
    def __init__(self):
        self.next = TEXT_BASE

    def take(self, n=1):
        i = self.next
        self.next += n
        assert self.next < ROW_TEXT_BASE
        return i


def music_parts(music, loop_start):
    """(clip bytes, byte ranges): the intro, then MUSIC_JOINS entries into the loop part."""
    rate = 8000
    ls = int(round(loop_start * rate))
    step = MUSIC_JOIN_MS * rate // 1000
    extra = (MUSIC_JOINS + 2) * step + RAW_RUNON
    if not 0 <= ls < len(music) - extra:
        raise ValueError(f"music loop start {loop_start} s is not inside the song ({len(music) / rate:.2f} s)")
    data = music + music[ls:ls + extra]
    if ls < MUSIC_JOIN_BACK * step:
        raise ValueError("music loop start must be at least 8 ms into the song")
    ranges = [(0, ls + extra)] + [(ls + (k - MUSIC_JOIN_BACK) * step, len(music) + extra) for k in range(MUSIC_JOINS)]
    return data, ranges


def build_menu(games, approval, version=VERSION, music=None, welcome=None, music_loop=0.0, music_seq=None,
               seq_volume=None, homebrew=()):
    """`homebrew`: the paths (games' second fields) of homebrew apps; their rows get the blue check.
    `welcome`: an 8 kHz A-law clip (sndgen.load_alaw) played once when the menu starts.
    `music`: an 8 kHz A-law clip (musicrender.render) played from its start, then looped from
    `music_loop` seconds. `music_seq`: the parts the console plays with it (musicrender's
    report["sequence"], the drums), started with the clip by LF_PlayBgMIDI at LF_SetBgMIDIVolume
    `seq_volume`; it loops by itself, on the clip's 4 ms grid."""
    raw = [welcome] if welcome else []
    welcome_handle = RAW_FIRST_HANDLE
    intro_handle = RAW_FIRST_HANDLE + len(raw)
    if music:
        raw.append(music_parts(music, music_loop))
        intro_ms = round(music_loop * 1000)
        loop_ms = len(music) * 1000 / 8000 - music_loop * 1000
    total = len(games)
    ids = TextIds()
    tags = [define_font(ID_FONT)]
    # Sky: the part behind the list, the part above it (covers the scrolled list), and a full one.
    tags.append(define_shape_layers(ID_SKY_LIST, sky_layers(TOP - 2, FOOTER)))
    tags.append(define_shape_layers(ID_SKY_TOP, sky_layers(0, TOP - 2)))
    sky_bottom = ids.take()  # covers the next row between the last visible one and the footer
    tags.append(define_shape_layers(sky_bottom, sky_layers(TOP + VISIBLE * PITCH, FOOTER)))
    tags.append(define_shape_layers(ID_SKY_FULL, sky_layers(0, 160)))
    # Frog mascot.
    tags.append(define_shape_layers(ID_FROG, [(FROG, bitmap_rects(FROG_ART, "G", 2)), (FROG_DARK, bitmap_rects(FROG_ART, "d", 2)),
                                              (FROG_WHITE, bitmap_rects(FROG_ART, "w", 2))]))
    # Glossy pill: drop shadow, rim, fill, shine (list coordinates, pill at its row's origin).
    tags.append(define_shape_layers(ID_PILL_BACK, [
        (PILL_SHADOW, rounded_rects(PILL_X + 1, 2, ROW_W, PILL_H, 3)),
        (PILL_RIM, rounded_rects(PILL_X, 0, ROW_W, PILL_H, 3)),
    ]))
    tags.append(define_shape_layers(ID_PILL_FILL, [(PILL_FILL, rounded_rects(PILL_X + 1, 1, ROW_W - 2, PILL_H - 2, 2))]))
    tags.append(define_shape_layers(ID_PILL_SHINE, [(PILL_SHINE, rounded_rects(PILL_X + 4, 2, ROW_W - 8, 5, 2))]))
    # Selection glow (behind the pill) and the touch / mask areas.
    tags.append(define_shape_layers(ID_GLOW, [(GLOW, rounded_rects(PILL_X - 3, -3, ROW_W + 6, PILL_H + 7, 4))]))
    tags.append(define_shape_layers(ID_PILL_HIT, [(0x000000, [(PILL_X, 0, ROW_W, PILL_H)])]))
    # Tool column: a pill-style key per tool, its icon, and a touch button calling _root.tool(k).
    tags.append(define_shape_layers(ID_TOOL_BOX, [(PILL_SHADOW, rounded_rects(1, 2, TOOL_W, TOOL_W, 3)),
                                                  (PILL_RIM, rounded_rects(0, 0, TOOL_W, TOOL_W, 3)),
                                                  (PILL_FILL, rounded_rects(1, 1, TOOL_W - 2, TOOL_W - 2, 2))]))
    tags.append(define_shape_layers(ID_TOOL_HIT, [(0x000000, [(-2, -2, TOOL_W + 4, TOOL_W + 4)])]))
    glow_t = ids.take()
    tags.append(define_shape_layers(glow_t, [(GLOW, rounded_rects(-3, -3, TOOL_W + 6, TOOL_W + 7, 4))]))
    tags.append(define_sprite(ID_TOOL_GLOW, [place(1, glow_t, 0, 0), show_frame()]))
    for k, (icon_id, art, button_id, sprite_id) in enumerate([(ID_TOOL_SEARCH, ICON_SEARCH, ID_BTN_SEARCH, ID_SPR_SEARCH),
                                                              (ID_TOOL_UP, ICON_UP, ID_BTN_UP, ID_SPR_UP),
                                                              (ID_TOOL_DOWN, ICON_DOWN, ID_BTN_DOWN, ID_SPR_DOWN)]):
        oy = (TOOL_W - len(art)) // 2
        tags.append(define_shape_layers(icon_id, [(ROW_SHADOW, bitmap_rects(art, "#", 1, 4, oy + 1)),
                                                  (0xFFFFFF, bitmap_rects(art, "#", 1, 3, oy))]))
        press = AS().push(k, 1).getvar("_root").push("tool").op("callmethod").op("pop")
        tags.append(define_button(button_id, ID_TOOL_HIT, press))
        tags.append(define_sprite(sprite_id, [place(1, ID_TOOL_BOX, 0, 0), place(2, icon_id, 0, 0),
                                              place(3, button_id, 0, 0), show_frame()]))
    tags.append(define_shape_layers(ID_TEXT_MASK, [(0x000000, [(PILL_X + TEXT_X, 0, AVAIL, PILL_H)])]))
    tags.append(define_shape_layers(ID_TEXT_MASK_HB, [(0x000000, [(PILL_X + TEXT_X, 0, BADGE_X - 2 - PILL_X - TEXT_X,
                                                                     PILL_H)])]))
    by = (PILL_H - len(BADGE)) // 2
    tags.append(define_shape_layers(ID_BADGE, [(BADGE_BLUE, bitmap_rects(BADGE, "B", 1, BADGE_X, by)),
                                               (0xFFFFFF, bitmap_rects(BADGE, "W", 1, BADGE_X, by))]))
    # Header: title, then "My Games: <count>" or "Search:" + the search text.
    title_text = ids.take(2)
    tags += shadowed_text(title_text, [(4, 22, "LeapLoader")], TITLE, TITLE_SHADOW, scale=2, offset=2)
    t = ids.take(2)
    tags += shadowed_text(t, [(6, 36, f"My Games: {total}" if total else "No games yet")], 0xFFFFFF, TITLE_SHADOW)
    tags.append(define_sprite(ID_HEAD_GAMES, [place(1, t, 0, 0), place(2, t + 1, 0, 0), show_frame()]))
    # Search text glyphs: light (header) and dark (boxes).
    glyph_sprite(ID_GLYPH_LIGHT, GLYPH_TEXT_LIGHT, 0xFFFFFF, tags)
    glyph_sprite(ID_GLYPH_DARK, GLYPH_TEXT_DARK, BOX_TEXT, tags)
    qline_sprite(ID_QLINE_LIGHT, ID_GLYPH_LIGHT, tags)
    qline_sprite(ID_QLINE_DARK, ID_GLYPH_DARK, tags)
    t = ids.take(2)
    tags += shadowed_text(t, [(6, 36, "Search:")], GLOW, TITLE_SHADOW)
    tags.append(define_sprite(ID_HEAD_SEARCH, [place(1, t, 0, 0), place(2, t + 1, 0, 0),
                                               place(3, ID_QLINE_LIGHT, 6 + 8 * ADVANCE, 28, name="q"), show_frame()]))
    t = ids.take(2)
    tags += shadowed_text(t, [(6, 62, "No games found."), (6, 76, "Pause: search again")], 0xFFFFFF, TITLE_SHADOW)
    tags.append(define_sprite(ID_NONE, [place(1, t, 0, 0), place(2, t + 1, 0, 0), show_frame()]))
    # Footer: bar, A badge, hints, version.
    tags.append(define_shape_layers(ID_FOOTER_BAR, [(FOOT_BG, [(0, FOOTER, 160, 160 - FOOTER)])]))
    foot = [(160 - 4 - ADVANCE * (len(version) + 1), FOOTER + 8, FOOT_DIM, "v" + version)]
    tags.append(define_text(ID_FOOTER_TEXT, 1, foot))
    glyph_sprite(ID_GLYPH_FOOT, GLYPH_TEXT_FOOT, FOOT_DIM, tags)
    qline_sprite(ID_QLINE_FOOT, ID_GLYPH_FOOT, tags)
    tags.append(define_text(ID_PAGE_TEXT, 1, [(4, FOOTER + 8, FOOT_DIM, "Page")]))
    tags.append(define_sprite(ID_PAGE, [place(1, ID_PAGE_TEXT, 0, 0), place(2, ID_QLINE_FOOT, 4 + 5 * ADVANCE, FOOTER, name="q"),
                                        show_frame()]))

    # Rows: each a sprite r{i} (pill, title masked to the pill with marquee clip "m/t", touch button).
    list_tags = [place(1, ID_HI, 0, 0, name="hi")]
    for i, (title, path) in enumerate(games):
        hb = path in homebrew
        tid = ROW_TEXT_BASE + 2 * i
        tags += shadowed_text(tid, [(0, 14, title)], ROW_TEXT, ROW_SHADOW)
        tags.append(define_sprite(ROW_INNER + i, [place(1, tid, 0, 0), place(2, tid + 1, 0, 0), show_frame()]))
        tags.append(define_sprite(ROW_MASKED + i, [place(1, ID_TEXT_MASK_HB if hb else ID_TEXT_MASK, 0, 0, clip_depth=3),
                                                   place(2, ROW_INNER + i, PILL_X + TEXT_X, 0, name="t"), show_frame()]))
        press = AS().push(i, 1).getvar("_root").push("tap").op("callmethod").op("pop")
        tags.append(define_button(ROW_BUTTON + i, ID_PILL_HIT, press))
        tags.append(define_sprite(ROW_SPRITE + i, [place(1, ID_PILL_BACK, 0, 0), place(2, ID_PILL_FILL, 0, 0),
                                                   place(3, ID_PILL_SHINE, 0, 0), place(4, ROW_MASKED + i, 0, 0, name="m"),
                                                   place(5, ROW_BUTTON + i, 0, 0)]
                                  + ([place(6, ID_BADGE, 0, 0)] if hb else []) + [show_frame()]))
        list_tags.append(place(10 + i, ROW_SPRITE + i, 0, i * PITCH, name=f"r{i}"))
    list_tags.append(show_frame())
    tags.append(define_sprite(ID_HI, [place(1, ID_GLOW, 0, 0), show_frame()]))
    tags.append(define_sprite(ID_LIST, list_tags))
    tags.append(define_sprite(ID_TICKER, [show_frame()]))  # the marquee ticker clip

    # ---- Options (Pause)
    tags.append(define_shape_layers(ID_OPT_BACK, [(PILL_SHADOW, rounded_rects(PILL_X + 1, 2, PILL_W, OPT_H, 3)),
                                                  (PILL_RIM, rounded_rects(PILL_X, 0, PILL_W, OPT_H, 3))]))
    tags.append(define_shape_layers(ID_OPT_FILL, [(PILL_FILL, rounded_rects(PILL_X + 1, 1, PILL_W - 2, OPT_H - 2, 2))]))
    tags.append(define_shape_layers(ID_OPT_SHINE, [(PILL_SHINE, rounded_rects(PILL_X + 4, 2, PILL_W - 8, 4, 2))]))
    tags.append(define_shape_layers(ID_OPT_GLOW, [(GLOW, rounded_rects(PILL_X - 3, -3, PILL_W + 6, OPT_H + 7, 4))]))
    tags.append(define_shape_layers(ID_OPT_HIT, [(0x000000, [(PILL_X, 0, PILL_W, OPT_H)])]))
    tags.append(define_shape_layers(ID_BOX, [(PILL_SHADOW, rounded_rects(PILL_X + 1, 2, PILL_W, OPT_H, 3)),
                                             (BOX_RIM, rounded_rects(PILL_X, 0, PILL_W, OPT_H, 3))]))
    box_fill = ids.take()
    tags.append(define_shape_layers(box_fill, [(BOX, rounded_rects(PILL_X + 1, 1, PILL_W - 2, OPT_H - 2, 2))]))
    t = ids.take(2)
    tags += shadowed_text(t, [(4, 22, "Options")], TITLE, TITLE_SHADOW, scale=2, offset=2)
    glow_o = ids.take()  # (sprites, not shapes, can be moved by name)
    tags.append(define_sprite(glow_o, [place(1, ID_OPT_GLOW, 0, 0), show_frame()]))
    opt = [place(1, ID_SKY_FULL, 0, 0), place(2, ID_FROG, 124, 4), place(3, t, 0, 0), place(4, t + 1, 0, 0),
           place(5, glow_o, 0, OPT_Y, name="hi")]
    depth = 10
    labels = {"Resume": "Resume", "Leapster Home": "Leapster Home", "About": "About"}
    toggles = {"Music": [("mOn", "Music: On"), ("mOff", "Music: Off")],
               "Sort": [("sAz", "Sort: A-Z"), ("sRec", "Sort: Recent")]}
    for k, name in enumerate(OPTIONS):
        y = OPT_Y + k * OPT_PITCH
        if k == 0:
            dim = ids.take()
            tags.append(define_text(dim, 1, [(PILL_X + 6, 11, BOX_DIM, "Search...")]))
            ph = ids.take()
            tags.append(define_sprite(ph, [place(1, dim, 0, 0), show_frame()]))
            opt += [place(depth, ID_BOX, 0, y), place(depth + 1, box_fill, 0, y),
                    place(depth + 2, ph, 0, y, name="ph"), place(depth + 3, ID_QLINE_DARK, PILL_X + 6, y + 3, name="q")]
        else:
            opt += [place(depth, ID_OPT_BACK, 0, y), place(depth + 1, ID_OPT_FILL, 0, y), place(depth + 2, ID_OPT_SHINE, 0, y)]
            if name in labels:
                tid = ids.take(2)
                tags += shadowed_text(tid, [(PILL_X + 6, 11, labels[name])], ROW_TEXT, ROW_SHADOW)
                opt += [place(depth + 3, tid, 0, y), place(depth + 4, tid + 1, 0, y)]
            else:
                for j, (inst, text) in enumerate(toggles[name]):
                    tid = ids.take(2)
                    tags += shadowed_text(tid, [(PILL_X + 6, 11, text)], ROW_TEXT, ROW_SHADOW)
                    sid = ids.take()
                    tags.append(define_sprite(sid, [place(1, tid, 0, 0), place(2, tid + 1, 0, 0), show_frame()]))
                    opt.append(place(depth + 3 + j, sid, 0, y, name=inst))
        press = AS().push(k, 1).getvar("_root").push("optTap").op("callmethod").op("pop")
        tags.append(define_button(OPT_BUTTON + k, ID_OPT_HIT, press))
        opt.append(place(depth + 6, OPT_BUTTON + k, 0, y))
        depth += 10
    t = ids.take()
    tags.append(define_text(t, 1, foot))
    fb = ids.take()
    tags.append(define_shape_layers(fb, [(FOOT_BG, [(0, FOOTER, 160, 160 - FOOTER)])]))
    opt += [place(depth, fb, 0, 0), place(depth + 1, t, 0, 0)]
    depth += 10
    # About panel (inside the options).
    ab_box = ids.take()
    tags.append(define_shape_layers(ab_box, [(PILL_SHADOW, rounded_rects(9, 33, 144, 104, 4)),
                                             (GLOW, rounded_rects(8, 31, 144, 104, 4)),
                                             (FOOT_BG, rounded_rects(10, 33, 140, 100, 3))]))
    t = ids.take(2)
    lines = [(18, 48, f"LeapLoader v{version}"), (18, 62, f"{total} game{'s' if total != 1 else ''} on this card"),
             (18, 80, "Home: Leapster menu"), (18, 92, "Pause: options"), (18, 104, "HINT+A+B in a game:"),
             (18, 116, " back to LeapLoader"), (18, 130, "Press any button")]
    tags += shadowed_text(t, lines, 0xFFFFFF, 0x000000)
    tags.append(define_sprite(ID_ABOUT, [place(1, ab_box, 0, 0), place(2, t, 0, 0), place(3, t + 1, 0, 0), show_frame()]))
    opt += [place(depth, ID_ABOUT, 0, 0, name="ab"), show_frame()]
    tags.append(define_sprite(ID_OPTIONS, opt))

    # ---- Keyboard (Search)
    tags.append(define_shape_layers(ID_KEY, [(PILL_SHADOW, rounded_rects(1, 2, KEY_W, KEY_W, 3)),
                                             (KEY_RIM, rounded_rects(0, 0, KEY_W, KEY_W, 3)),
                                             (KEY_FACE, rounded_rects(1, 1, KEY_W - 2, KEY_W - 2, 2))]))
    tags.append(define_shape_layers(ID_KEY_WIDE, [(PILL_SHADOW, rounded_rects(1, 2, WIDE_W, KEY_W, 3)),
                                                  (KEY_RIM, rounded_rects(0, 0, WIDE_W, KEY_W, 3)),
                                                  (KEY_FACE, rounded_rects(1, 1, WIDE_W - 2, KEY_W - 2, 2))]))
    tags.append(define_shape_layers(ID_KEY_OK, [(PILL_SHADOW, rounded_rects(1, 2, WIDE_W, KEY_W, 3)),
                                                (PILL_RIM, rounded_rects(0, 0, WIDE_W, KEY_W, 3)),
                                                (PILL_FILL, rounded_rects(1, 1, WIDE_W - 2, KEY_W - 2, 2))]))
    tags.append(define_shape_layers(ID_KEY_GLOW, [(GLOW, rounded_rects(-3, -3, KEY_W + 6, KEY_W + 7, 4))]))
    tags.append(define_shape_layers(ID_KEY_GLOW_WIDE, [(GLOW, rounded_rects(-3, -3, WIDE_W + 6, KEY_W + 7, 4))]))
    tags.append(define_shape_layers(ID_KEY_HIT, [(0x000000, [(0, 0, KEY_W, KEY_W)])]))
    tags.append(define_shape_layers(ID_KEY_HIT_WIDE, [(0x000000, [(0, 0, WIDE_W, KEY_W)])]))
    tags.append(define_shape_layers(ID_CURSOR, [(BOX_TEXT, [(0, 0, ADVANCE - 1, 1)])]))
    kb_box = ids.take()
    tags.append(define_shape_layers(kb_box, [(PILL_SHADOW, rounded_rects(5, 6, 152, 20, 3)),
                                             (BOX_RIM, rounded_rects(4, 4, 152, 20, 3)),
                                             (BOX, rounded_rects(5, 5, 150, 18, 2))]))
    glow_k, glow_w, cursor = ids.take(), ids.take(), ids.take()
    tags.append(define_sprite(cursor, [place(1, ID_CURSOR, 0, 0), show_frame()]))
    tags.append(define_sprite(glow_k, [place(1, ID_KEY_GLOW, 0, 0), show_frame()]))
    tags.append(define_sprite(glow_w, [place(1, ID_KEY_GLOW_WIDE, 0, 0), show_frame()]))
    kb = [place(1, ID_SKY_FULL, 0, 0), place(2, kb_box, 0, 0), place(3, ID_QLINE_DARK, 10, 9, name="q"),
          place(4, cursor, 10, 18, name="cur"), place(5, glow_k, KEY_X, KEY_Y, name="kh"),
          place(6, glow_w, DEL_X, WIDE_Y, name="kw")]
    depth = 10
    for i, c in enumerate(KEYS):
        x, y = KEY_X + (i % 7) * KEY_PITCH, KEY_Y + (i // 7) * KEY_PITCH
        press = AS().push(i, 1).getvar("_root").push("keyTap").op("callmethod").op("pop")
        tags.append(define_button(KEY_BUTTON + i, ID_KEY_HIT, press))
        kb.append(place(depth, ID_KEY, x, y))
        if c != " ":
            tid = ids.take()
            tags.append(define_text(tid, 1, [(4, 16, KEY_TEXT, c)], scale=2))
            kb.append(place(depth + 1, tid, x, y))
        kb.append(place(depth + 2, KEY_BUTTON + i, x, y))
        depth += 3
    for i, (x, shape, text, color) in enumerate([(DEL_X, ID_KEY_WIDE, "<-", KEY_TEXT), (CLR_X, ID_KEY_WIDE, "CLR", KEY_TEXT),
                                                 (OK_X, ID_KEY_OK, "OK", 0xFFFFFF)]):
        k = len(KEYS) + i
        press = AS().push(k, 1).getvar("_root").push("keyTap").op("callmethod").op("pop")
        tags.append(define_button(KEY_BUTTON + k, ID_KEY_HIT_WIDE, press))
        tid = ids.take()
        tags.append(define_text(tid, 1, [((WIDE_W - 2 * ADVANCE * len(text)) // 2, 16, color, text)], scale=2))
        kb += [place(depth, shape, x, WIDE_Y), place(depth + 1, tid, x, WIDE_Y), place(depth + 2, KEY_BUTTON + k, x, WIDE_Y)]
        depth += 3
    kb.append(show_frame())
    tags.append(define_sprite(ID_KEYBOARD, kb))

    a = AS()
    # Data: paths relative to b:\Leapster\Apps\ (BT_StartSDGame's base folder), title widths, titles
    # in capitals (search), and path -> index.
    a.push("paths", *[p for _, p in reversed(games)], total).op("initarray").raw(0x1D)
    a.push("wid", *[ADVANCE * len(t) - 1 for t, _ in reversed(games)], total).op("initarray").raw(0x1D)
    # Search index: every position of every title in capitals, cut to QMAX characters, sorted
    # (StringLess order = character codes); sg = the game of each. A search is a binary search.
    suffixes = sorted({(ascii_upper(t)[i:i + QMAX], g) for g, (t, _) in enumerate(games)
                       for i in range(len(t)) if ascii_upper(t)[i] != " "})
    a.push("sk", *[k for k, _ in reversed(suffixes)], len(suffixes)).op("initarray").raw(0x1D)
    a.push("sg", *[g for _, g in reversed(suffixes)], len(suffixes)).op("initarray").raw(0x1D)
    a.push("kc", *[ord(c) for c in reversed(KEYS)], len(KEYS)).op("initarray").raw(0x1D)
    a.push("ci").push(0, "Object").op("newobject").raw(0x1D)
    for i, c in enumerate(QCHARS):
        a.getvar("ci").push(c, i).op("setmember")
    a.push("idx").push(0, "Object").op("newobject").raw(0x1D)
    for i, (_, p) in enumerate(games):
        a.getvar("idx").push(p, i).op("setmember")
    for name, value in (("total", total), ("n", 0), ("sel", 0), ("last", 0), ("mq", 0), ("go", -1), ("gt", 0),
                        ("mode", 0), ("osel", 0), ("ksel", 0), ("kfrom", 1), ("q", ""), ("qa", ""), ("srt", 0),
                        ("mus", 1 if music else 0), ("hasmus", 1 if music else 0), ("sn", len(suffixes)),
                        ("mt", 0), ("mseg", 0), ("mp", -1),
                        ("okt", 0), ("tft", 0), ("first", 0), ("pin", 0), ("vf", -1)):
        a.push(name, value).raw(0x1D)
    a.push("rec").push(0).op("initarray").raw(0x1D)
    a.push("ord").push(0).op("initarray").raw(0x1D)

    # function load(): settings from the card ("LL1|music|sort|recent path|...|").
    f = AS()
    local(f, "s", AS().call("SD_ReadText", SETTINGS))
    local(f, "v", N(0).op("initarray"))
    local(f, "st", N(1))

    def field(b):  # (no String.split: see slen)
        def cut(c):
            method(c, V("v"), "push", extract(V("s"), V("st"), binop(V("k"), V("st"), "sub"))).op("pop")
            setv(c, "st", binop(V("k"), N(1), "add"))
        if_(b, binop(extract(V("s"), V("k"), 1), N("|"), "eq"), cut)
    if_(f, binop(cat(V("s")).op("typeof"), N("string"), "eq"),
        lambda b: for_(b, "k", 1, binop(slen(V("s")), N(1), "add"), field))

    def got(b):
        setv(b, "mus", binop(binop(V("hasmus"), N(1), "eq"),
                             binop(cat(V("v"), N(1)).op("getmember"), N("1"), "eq"), "and"))
        setv(b, "srt", cat(binop(cat(V("v"), N(2)).op("getmember"), N("1"), "eq")).op("tonumber"))
        setv(b, "rec", method(AS(), V("v"), "slice", 3))
    if_(f, binop(cat(V("v"), N(0)).op("getmember"), N("LL1"), "eq"), got)
    a.define_function("load", [], f)

    # function save(): the settings back to the card.
    f = AS()
    local(f, "s", N("LL1|"))
    if_(f, V("mus"), lambda b: setv(b, "s", binop(V("s"), N("1|"), "add")),
        lambda b: setv(b, "s", binop(V("s"), N("0|"), "add")))
    if_(f, V("srt"), lambda b: setv(b, "s", binop(V("s"), N("1|"), "add")),
        lambda b: setv(b, "s", binop(V("s"), N("0|"), "add")))
    setv(f, "s", binop(binop(V("s"), method(AS(), V("rec"), "join", "|"), "add"), N("|"), "add"))
    f.call("SD_WriteText", SETTINGS, V("s")).op("pop")
    a.define_function("save", [], f)

    # function rebuild(): the order (A-Z or recently played first), filtered by the search text qa.
    f = AS()
    local(f, "base", N(0).op("initarray"))

    def recent_first(b):
        local(b, "seen", N(0, "Object").op("newobject"))

        def each_rec(c):
            local(c, "j", cat(V("idx"), cat(V("rec"), V("k")).op("getmember")).op("getmember"))

            def add(d):
                d.code.extend(cat(V("seen"), V("j"), N(True)).op("setmember").code)
                method(d, V("base"), "push", V("j")).op("pop")
            if_(c, binop(binop(cat(V("j")).op("typeof"), N("number"), "eq"),
                         cat(V("seen"), V("j")).op("getmember").op("not"), "and"), add)
        for_(b, "k", 0, cat(V("rec")).push("length").op("getmember"), each_rec)

        def each_game(c):
            if_(c, cat(V("seen"), V("k")).op("getmember").op("not"),
                lambda d: method(d, V("base"), "push", V("k")).op("pop"))
        for_(b, "k", 0, V("total"), each_game)

    def alphabetical(b):
        for_(b, "k", 0, V("total"), lambda c: method(c, V("base"), "push", V("k")).op("pop"))
    if_(f, V("srt"), recent_first, alphabetical)
    setv(f, "ord", N(0).op("initarray"))
    local(f, "hit", N(0, "Object").op("newobject"))

    def search(b):
        # First index whose key is not below qa, then every key starting with qa.
        local(b, "lo", N(0))
        local(b, "hi", V("sn"))
        top, end = fresh("bs"), fresh("sb")
        b.label(top)
        b.code.extend(binop(V("lo"), V("hi"), "lt").code)
        b.op("not").if_true(end)
        local(b, "mid", binop(binop(V("lo"), V("hi"), "add"), N(2), "div").op("int"))
        if_(b, binop(cat(V("sk"), V("mid")).op("getmember"), V("qa"), "slt"),
            lambda c: setv(c, "lo", binop(V("mid"), N(1), "add")), lambda c: setv(c, "hi", V("mid")))
        b.jump(top)
        b.label(end)
        local(b, "ql", slen(V("qa")))
        top, end = fresh("sc"), fresh("cs")
        b.label(top)
        b.code.extend(binop(binop(V("lo"), V("sn"), "lt"),
                            binop(extract(cat(V("sk"), V("lo")).op("getmember"), 1, V("ql")), V("qa"), "eq"), "and").code)
        b.op("not").if_true(end)
        b.code.extend(cat(V("hit"), cat(V("sg"), V("lo")).op("getmember"), N(True)).op("setmember").code)
        setv(b, "lo", binop(V("lo"), N(1), "add"))
        b.jump(top)
        b.label(end)
    if_(f, binop(V("qa"), N(""), "eq").op("not"), search)

    def each(b):
        local(b, "j", cat(V("base"), V("k")).op("getmember"))
        if_(b, binop(binop(V("qa"), N(""), "eq"), cat(V("hit"), V("j")).op("getmember"), "or"),
            lambda c: method(c, V("ord"), "push", V("j")).op("pop"))
    for_(f, "k", 0, V("total"), each)
    setv(f, "n", cat(V("ord")).push("length").op("getmember"))
    setv(f, "sel", N(0))
    # Rows: hide all, then lay out the shown ones.
    for_(f, "k", 0, V("total"), lambda b: visible(b, binop(N("/list/r"), V("k"), "add"), N(0)))

    def place_row(b):
        local(b, "j", cat(V("ord"), V("k")).op("getmember"))
        set_property(b, binop(N("/list/r"), V("j"), "add"), 1, binop(V("k"), N(PITCH), "mul"))
    for_(f, "k", 0, V("n"), place_row)
    setv(f, "vf", N(-1))  # rows shown: none yet (show() shows the ones in view)
    visible(f, "/hg", binop(V("qa"), N(""), "eq"))
    visible(f, "/hs", binop(V("qa"), N(""), "eq").op("not"))
    visible(f, "/none", binop(V("n"), N(0), "eq"))
    visible(f, "/pg", binop(V("n"), N(0), "gt"))
    visible(f, "/list/hi", binop(V("n"), N(0), "gt"))
    visible(f, "/tu", binop(V("n"), N(VISIBLE), "gt"))
    visible(f, "/td", binop(V("n"), N(VISIBLE), "gt"))
    f.call("qshow", "/hs/q", V("qa")).op("pop")
    if_(f, binop(V("n"), N(0), "gt"), lambda b: b.call("show").op("pop"))
    a.define_function("rebuild", [], f)

    # function qshow(path, s): the text s on the glyph line at path (c0..c{QMAX-1}).
    f = AS()

    def slot(b):
        local(b, "fr", N(1))
        if_(b, binop(V("k"), slen(V("s")), "lt"),
            lambda c: setv(c, "fr", binop(cat(V("ci"), extract(V("s"), binop(V("k"), N(1), "add"), 1)).op("getmember"),
                                          N(2), "add")))
        goto_frame(b, binop(binop(V("path"), N("/c"), "add"), V("k"), "add"), V("fr"))
    for_(f, "k", 0, N(QMAX), slot)
    a.define_function("qshow", ["path", "s"], f)
    # function pshow(s): the same for the page number ("nn/nn": PAGE_SLOTS glyphs), only when it changed
    # (a page turn has to be quick: taps faster than one queue up, 2026-10-25).
    f = AS()
    f.getvar("s").getvar("pgs_shown").op("eq").if_true("same")
    setv(f, "pgs_shown", V("s"))
    local(f, "path", N("/pg/q"))
    for_(f, "k", 0, N(PAGE_SLOTS), slot)
    f.label("same")
    a.define_function("pshow", ["s"], f)

    # function show(): highlight the selection, scroll it into view, restart the marquee.
    # pin: page() has already placed the list (first), keep it there.
    show = AS()
    show.getvar("pin").if_true("a2")
    show.push("first").getvar("sel").push(1).op("sub").raw(0x1D)
    show.getvar("first").getvar("n").push(VISIBLE).op("sub").op("gt").op("not").if_true("a1")
    show.push("first").getvar("n").push(VISIBLE).op("sub").raw(0x1D)
    show.label("a1")
    show.getvar("first").push(0).op("lt").op("not").if_true("a2")
    show.push("first", 0).raw(0x1D)
    show.label("a2")
    show.push("pin", 0).raw(0x1D)
    # Only the rows in view are visible: the player draws every visible row each frame, and with
    # 77 a page turn took ~0.5 s, so fast taps queued up and went on turning pages (user, 2026-10-25).
    def row_vis(on):
        def body(b):
            if_(b, binop(binop(V("k"), N(0), "lt").op("not"), binop(V("k"), V("n"), "lt"), "and"),
                lambda c: visible(c, binop(N("/list/r"), cat(V("ord"), V("k")).op("getmember"), "add"), N(on)))
        return body
    for_(show, "k", V("vf"), binop(V("vf"), N(VISIBLE + 1), "add"), row_vis(0))
    for_(show, "k", V("first"), binop(V("first"), N(VISIBLE + 1), "add"), row_vis(1))
    show.push("vf").getvar("first").raw(0x1D)
    set_property(show, "/list", 1, AS().push(TOP).getvar("first").push(PITCH).op("mul").op("sub"))
    set_property(show, "/list/hi", 1, AS().getvar("sel").push(PITCH).op("mul"))
    set_property(show, AS().push("/list/r").getvar("last").op("add").push("/m/t").op("add"), 0, AS().push(PILL_X + TEXT_X))
    show.push("last").getvar("ord").getvar("sel").op("getmember").raw(0x1D)
    # The page number: the page most of the list is on, the last page once the list is at its end.
    local(show, "pgs", binop(binop(V("n"), N(VISIBLE - 1), "add"), N(VISIBLE), "div").op("int"))
    local(show, "pgn", binop(binop(binop(V("first"), N(VISIBLE // 2), "add"), N(VISIBLE), "div").op("int"), N(1), "add"))
    if_(show, binop(binop(V("n"), N(VISIBLE), "sub"), V("first"), "gt").op("not"), lambda b: local(b, "pgn", V("pgs")))
    if_(show, binop(V("pgs"), V("pgn"), "lt"), lambda b: local(b, "pgn", V("pgs")))
    show.call("pshow", binop(binop(V("pgn"), N("/"), "add"), V("pgs"), "add")).op("pop")
    show.push("mq", PAUSE).raw(0x1D)  # scroll at once (later rounds pause first)
    a.define_function("show", [], show)

    # function musStart(): the music from its start (the intro part); tick() goes on with the loop part.
    f = AS()
    f.callv("LF_SetRawVolume", MUSIC_VOLUME)
    setv(f, "mp", AS().call("LF_PlayAudioRaw", AS().call("lfh", intro_handle)))  # its audio player
    f.callv("LF_SetRawVolume", 100)
    if music_seq:
        f.callv("LF_SetBgMIDIVolume", seq_volume)
        f.callv("LF_PlayBgMIDI", AS().call("lfh", SEQ_FIRST_HANDLE))
    f.push("mt").raw(0x34).raw(0x1D)  # mt = getTimer()
    setv(f, "mseg", N(0))
    a.define_function("musStart", [], f)

    # function musNext(): the intro or the loop part has played (el ms since its loop-point time mt);
    # the loop part from where the music has got to.
    f = AS()
    local(f, "due", N(loop_ms if music else 0))
    if_(f, binop(V("mseg"), N(0), "eq"), lambda b: setv(b, "due", N(intro_ms if music else 0)))
    local(f, "late", binop(binop(AS().raw(0x34), V("mt"), "sub"), V("due"), "sub"))
    if_(f, binop(V("late"), N(0), "lt").op("not"), lambda b: (
        local(b, "k", binop(binop(V("late"), N(MUSIC_JOIN_BACK * MUSIC_JOIN_MS + MUSIC_JOIN_MS / 2 + MUSIC_JOIN_LEAD_MS),
                                  "add"), N(MUSIC_JOIN_MS), "div").op("int")),
        if_(b, binop(V("k"), N(0), "lt"), lambda c: setv(c, "k", N(0))),
        if_(b, binop(V("k"), N(MUSIC_JOINS - 1), "gt"), lambda c: setv(c, "k", N(MUSIC_JOINS - 1))),
        # (LF_StopAllAudio only pauses the voices, which then stay taken: VERIFIED-EMU)
        b.callv("LF_StopAudioPlayer", V("mp")),
        b.callv("LF_SetRawVolume", MUSIC_VOLUME),
        setv(b, "mp", AS().call("LF_PlayAudioRaw", AS().call("lfh", binop(N(intro_handle + 1), V("k"), "add")))),
        b.callv("LF_SetRawVolume", 100),
        # mt: when the loop point would have played (entry k starts (k - MUSIC_JOIN_BACK) steps after it)
        setv(b, "mt", binop(AS().raw(0x34), binop(binop(V("k"), N(MUSIC_JOIN_BACK), "sub"), N(MUSIC_JOIN_MS), "mul"), "sub")),
        setv(b, "mseg", N(1))))
    a.define_function("musNext", [], f)

    # function tick(): every frame. While a game is starting (go >= 0): blink the glow, then
    # start it once the select sound has played. Then one marquee step for the selected title.
    tick = AS()
    if_(tick, binop(V("tft"), N(0), "gt"), lambda b: (
        setv(b, "tft", binop(V("tft"), N(1), "sub")),
        if_(b, binop(V("tft"), N(0), "eq"), lambda c: visible(c, "/tg", N(0)))))
    if_(tick, binop(V("okt"), N(0), "gt"), lambda b: (
        setv(b, "okt", binop(V("okt"), N(1), "sub")),
        visible(b, "/kb/kw", binop(binop(binop(V("okt"), N(BLINK), "div").op("int"), N(2), "mod"), N(0), "eq")),
        if_(b, binop(V("okt"), N(0), "eq"), lambda c: (visible(c, "/kb/kw", N(1)), c.call("kbDone").op("pop")))))
    if music:
        if_(tick, V("mus"), lambda b: b.call("musNext").op("pop"))
    tick.getvar("go").push(-1).op("eq").if_true("k_end")
    tick.push("gt").getvar("gt").push(1).op("add").raw(0x1D)
    set_property(tick, "/list/hi", 7, AS().getvar("gt").push(BLINK).op("div").op("int").push(2).op("mod").push(0).op("eq"))
    tick.getvar("gt").push(LAUNCH_DELAY).op("lt").if_true("k_end")
    set_property(tick, "/list/hi", 7, AS().push(1))
    tick.callv("BT_StartSDGame", AS().getvar("paths").getvar("go").op("getmember"))
    tick.push("go", -1).raw(0x1D)  # only reached if the BIOS did not reboot into the game
    tick.label("k_end")
    tick.getvar("n").push(0).op("gt").op("not").if_true("t_end")
    tick.push("w").getvar("wid").getvar("last").op("getmember").raw(0x3C)
    tick.getvar("w").push(AVAIL + 1).op("lt").if_true("t_end")
    tick.push("mq").getvar("mq").push(1).op("add").raw(0x1D)
    tick.push("off", 0).raw(0x3C)
    tick.getvar("mq").push(PAUSE).op("lt").if_true("t_set")
    tick.push("off").getvar("mq").push(PAUSE).op("sub").push(SCROLL).op("mul").raw(0x3C)
    tick.getvar("off").getvar("w").push(AVAIL).op("sub").op("gt").op("not").if_true("t_set")
    tick.push("off").getvar("w").push(AVAIL).op("sub").raw(0x3C)
    # the end reached: hold PAUSE frames, then start over (pausing at the start)
    tick.getvar("mq").getvar("w").push(AVAIL).op("sub").push(SCROLL).op("div").push(2 * PAUSE + 1).op("add").op("gt").op("not").if_true("t_set")
    tick.push("mq", 0).raw(0x1D)
    tick.label("t_set")
    set_property(tick, AS().push("/list/r").getvar("last").op("add").push("/m/t").op("add"), 0,
                 AS().push(PILL_X + TEXT_X).getvar("off").op("sub"))
    tick.label("t_end")
    a.define_function("tick", [], tick)

    # function launch(g): start game g (index into paths), as the BIOS's sign-in screen chooses a
    # name: the select sound plays and the highlight blinks, then tick() starts it. The game goes
    # first in the recently played list, which is saved now (the BIOS reboots into the game).
    f = AS()

    def start(b):
        setv(b, "go", V("g"))
        setv(b, "gt", N(0))
        local(b, "p", cat(V("paths"), V("g")).op("getmember"))
        local(b, "r", N(0).op("initarray"))
        method(b, V("r"), "push", V("p")).op("pop")

        def keep(c):
            if_(c, binop(binop(cat(V("rec"), V("k")).op("getmember"), V("p"), "eq").op("not"),
                         binop(cat(V("rec"), V("k")).op("getmember"), N(""), "eq").op("not"), "and"),
                lambda d: method(d, V("r"), "push", cat(V("rec"), V("k")).op("getmember")).op("pop"))
        for_(b, "k", 0, cat(V("rec")).push("length").op("getmember"), keep)
        setv(b, "rec", method(AS(), V("r"), "slice", 0, RECENT_MAX))
        b.call("save").op("pop")
        play_sound(b, SELECT_SOUND)
    if_(f, binop(V("go"), N(-1), "eq"), start)
    a.define_function("launch", ["g"], f)

    # function tap(i): a touched row (game i): select it, then start it.
    f = AS()

    def tapped(b):
        def find(c):
            if_(c, binop(cat(V("ord"), V("k")).op("getmember"), V("i"), "eq"), lambda d: setv(d, "sel", V("k")))
        for_(b, "k", 0, V("n"), find)
        b.call("show").op("pop")
        b.getvar("i").push(1, "launch").raw(0x3D).op("pop")
    if_(f, binop(binop(V("go"), N(-1), "eq"), binop(V("mode"), N(0), "eq"), "and"), tapped)
    a.define_function("tap", ["i"], f)

    # Options.
    f = AS()  # function optShow(): highlight and toggle labels
    set_property(f, "/pm/hi", 1, binop(N(OPT_Y), binop(V("osel"), N(OPT_PITCH), "mul"), "add"))
    visible(f, "/pm/mOn", V("mus"))
    visible(f, "/pm/mOff", V("mus").op("not"))
    visible(f, "/pm/sAz", V("srt").op("not"))
    visible(f, "/pm/sRec", V("srt"))
    visible(f, "/pm/ph", binop(V("qa"), N(""), "eq"))
    f.call("qshow", "/pm/q", V("qa")).op("pop")
    a.define_function("optShow", [], f)

    f = AS()  # function openOpt()
    setv(f, "mode", N(1))
    setv(f, "osel", N(0))
    visible(f, "/pm/ab", N(0))
    visible(f, "/pm", N(1))
    f.call("optShow").op("pop")
    a.define_function("openOpt", [], f)

    f = AS()  # function closeOpt()
    setv(f, "mode", N(0))
    visible(f, "/pm", N(0))
    a.define_function("closeOpt", [], f)

    f = AS()  # function optPick(k)
    play_sound(f, SELECT_SOUND)

    if_(f, binop(V("k"), N(0), "eq"), lambda b: b.call("openSearch", 1).op("pop"))
    if_(f, binop(V("k"), N(1), "eq"), lambda b: b.call("closeOpt").op("pop"))

    def music_toggle(b):
        setv(b, "mus", V("mus").op("not"))
        if_(b, V("mus"), lambda c: c.call("musStart").op("pop"),
            lambda c: (c.callv("LF_StopAudioPlayer", V("mp")), c.callv("LF_StopBgMIDI") if music_seq else None))
        b.call("save").op("pop")
        b.call("optShow").op("pop")
    if_(f, binop(binop(V("k"), N(2), "eq"), V("hasmus"), "and"), music_toggle)

    def sort_toggle(b):
        setv(b, "srt", binop(N(1), V("srt"), "sub"))
        b.call("save").op("pop")
        b.call("rebuild").op("pop")
        b.call("optShow").op("pop")
    if_(f, binop(V("k"), N(3), "eq"), sort_toggle)
    if_(f, binop(V("k"), N(4), "eq"), lambda b: b.callv("BT_StartSDGame", HOME_PATH))

    def about(b):
        setv(b, "mode", N(3))
        visible(b, "/pm/ab", N(1))
    if_(f, binop(V("k"), N(5), "eq"), about)
    a.define_function("optPick", ["k"], f)

    f = AS()  # function openSearch(from): the keyboard, from the list (0) or the options (1)
    setv(f, "kfrom", V("from"))
    setv(f, "mode", N(2))
    setv(f, "q", V("qa"))
    setv(f, "ksel", N(0))
    visible(f, "/kb", N(1))
    f.call("kbShow").op("pop")
    f.call("qshow", "/kb/q", V("q")).op("pop")
    a.define_function("openSearch", ["from"], f)

    f = AS()  # function moveSound(d): the BIOS's menu sound for a move back (d < 0) or on
    if_(f, binop(V("d"), N(0), "lt"), lambda b: play_sound(b, MOVE_UP_SOUND), lambda b: play_sound(b, MOVE_DOWN_SOUND))
    a.define_function("moveSound", ["d"], f)

    f = AS()  # function flashTool(k): light tool key k (0 search, 1 up, 2 down) for FLASH frames
    set_property(f, "/tg", 1, N(SEARCH_Y))
    if_(f, binop(V("k"), N(1), "eq"), lambda b: set_property(b, "/tg", 1, N(UP_Y)))
    if_(f, binop(V("k"), N(2), "eq"), lambda b: set_property(b, "/tg", 1, N(DOWN_Y)))
    visible(f, "/tg", N(1))
    setv(f, "tft", N(FLASH))
    a.define_function("flashTool", ["k"], f)

    f = AS()  # function page(d): a page up (-1) or down (+1)
    f.call("moveSound", V("d")).op("pop")
    if_(f, binop(V("n"), N(VISIBLE), "gt"), lambda b: if_(b, binop(V("d"), N(0), "lt"), lambda c: c.call("flashTool", 1).op("pop"),
                                                          lambda c: c.call("flashTool", 2).op("pop")))
    # The list moves a whole page (the next VISIBLE games, or up to the last/first ones) and the
    # selection keeps its row; show() then leaves the list where it is (pin).
    # Pages start at multiples of VISIBLE (the last one may show fewer new games), so going back
    # up from the end goes to the page before it.
    if_(f, binop(V("d"), N(0), "gt"),
        lambda b: setv(b, "nf", binop(binop(binop(V("first"), N(VISIBLE), "div").op("int"), N(VISIBLE), "mul"),
                                      N(VISIBLE), "add")),
        lambda b: setv(b, "nf", binop(binop(binop(binop(V("first"), N(VISIBLE - 1), "add"), N(VISIBLE), "div").op("int"),
                                            N(VISIBLE), "mul"), N(VISIBLE), "sub")))
    if_(f, binop(V("nf"), binop(V("n"), N(VISIBLE), "sub"), "gt"), lambda b: setv(b, "nf", binop(V("n"), N(VISIBLE), "sub")))
    if_(f, binop(V("nf"), N(0), "lt"), lambda b: setv(b, "nf", N(0)))
    # Round the end (user asked): down on the last page goes to the first, up on the first to the last.
    if_(f, binop(V("nf"), V("first"), "eq"),
        lambda b: if_(b, binop(V("d"), N(0), "gt"), lambda c: setv(c, "nf", N(0)),
                      lambda c: setv(c, "nf", binop(V("n"), N(VISIBLE), "sub"))))
    if_(f, binop(V("nf"), N(0), "lt"), lambda b: setv(b, "nf", N(0)))
    setv(f, "sel", binop(V("sel"), binop(V("nf"), V("first"), "sub"), "add"))
    if_(f, binop(V("sel"), binop(V("n"), N(1), "sub"), "gt"), lambda b: setv(b, "sel", binop(V("n"), N(1), "sub")))
    if_(f, binop(V("sel"), N(0), "lt"), lambda b: setv(b, "sel", N(0)))
    setv(f, "first", V("nf"))
    setv(f, "pin", N(1))
    f.call("show").op("pop")
    a.define_function("page", ["d"], f)

    f = AS()  # function tool(k): a touched tool key: 0 search, 1 page up, 2 page down

    def tool(b):
        if_(b, binop(V("k"), N(0), "eq"), lambda c: (play_sound(c, SELECT_SOUND), c.call("flashTool", 0).op("pop"),
                                                    c.call("openSearch", 0).op("pop")))
        if_(b, binop(binop(V("k"), N(1), "eq"), binop(V("n"), N(0), "gt"), "and"), lambda c: c.call("page", -1).op("pop"))
        if_(b, binop(binop(V("k"), N(2), "eq"), binop(V("n"), N(0), "gt"), "and"), lambda c: c.call("page", 1).op("pop"))
    if_(f, binop(binop(V("go"), N(-1), "eq"), binop(V("mode"), N(0), "eq"), "and"), tool)
    a.define_function("tool", ["k"], f)

    f = AS()  # function optTap(k): a touched option
    if_(f, binop(V("mode"), N(1), "eq"), lambda b: (setv(b, "osel", V("k")), b.call("optShow").op("pop"),
                                                    b.call("optPick", V("k")).op("pop")))
    a.define_function("optTap", ["k"], f)

    # Keyboard.
    nkeys = len(KEYS)
    f = AS()  # function kbShow(): key highlight and cursor

    def letter_glow(b):
        set_property(b, "/kb/kh", 0, binop(N(KEY_X), binop(binop(V("ksel"), N(7), "mod"), N(KEY_PITCH), "mul"), "add"))
        set_property(b, "/kb/kh", 1, binop(N(KEY_Y), binop(binop(V("ksel"), N(7), "div").op("int"), N(KEY_PITCH), "mul"),
                                           "add"))
        visible(b, "/kb/kh", N(1))
        visible(b, "/kb/kw", N(0))

    def wide_glow(b):
        set_property(b, "/kb/kw", 0, binop(N(DEL_X), binop(binop(V("ksel"), N(nkeys), "sub"), N(CLR_X - DEL_X), "mul"), "add"))
        visible(b, "/kb/kh", N(0))
        visible(b, "/kb/kw", N(1))
    if_(f, binop(V("ksel"), N(nkeys), "lt"), letter_glow, wide_glow)
    set_property(f, "/kb/cur", 0, binop(N(10), binop(slen(V("q")), N(ADVANCE), "mul"), "add"))
    a.define_function("kbShow", [], f)

    f = AS()  # function keyPress(k)

    def letter(b):
        if_(b, binop(slen(V("q")), N(QMAX), "lt"),
            lambda c: (setv(c, "q", binop(V("q"), cat(V("kc"), V("k")).op("getmember").op("chr"), "concat")),
                       goto_frame(c, binop(N("/kb/q/c"), binop(slen(V("q")), N(1), "sub"), "add"),
                                  binop(V("k"), N(2), "add")),
                       play_sound(c, LETTER_SOUND)))
    if_(f, binop(V("k"), N(nkeys), "lt"), letter)
    if_(f, binop(V("k"), N(nkeys), "eq"), lambda b: b.call("backspace").op("pop"))

    def clear(b):
        setv(b, "q", N(""))
        b.call("qshow", "/kb/q", V("q")).op("pop")
        play_sound(b, LETTER_SOUND)
    if_(f, binop(V("k"), N(nkeys + 1), "eq"), clear)

    def ok(b):  # the OK key blinks (tick), then kbDone() runs the search
        play_sound(b, SELECT_SOUND)
        setv(b, "ksel", N(nkeys + 2))
        setv(b, "okt", N(OK_DELAY))
    if_(f, binop(V("k"), N(nkeys + 2), "eq"), ok)
    f.call("kbShow").op("pop")
    a.define_function("keyPress", ["k"], f)

    f = AS()  # function kbDone(): the search text from the keyboard

    def done(b):
        # Spaces at the ends do not count.
        while_top, while_end = fresh("trim"), fresh("mirt")
        b.label(while_top)
        b.code.extend(binop(binop(slen(V("q")), N(0), "gt"), binop(extract(V("q"), slen(V("q")), 1), N(" "), "eq"), "and").code)
        b.op("not").if_true(while_end)
        setv(b, "q", extract(V("q"), 1, binop(slen(V("q")), N(1), "sub")))
        b.jump(while_top)
        b.label(while_end)
        setv(b, "qa", V("q"))
        visible(b, "/kb", N(0))
        b.call("closeOpt").op("pop")
        b.call("rebuild").op("pop")
    done(f)
    a.define_function("kbDone", [], f)

    f = AS()  # function backspace()
    if_(f, binop(slen(V("q")), N(0), "gt"),
        lambda b: (setv(b, "q", extract(V("q"), 1, binop(slen(V("q")), N(1), "sub"))),
                   goto_frame(b, binop(N("/kb/q/c"), slen(V("q")), "add"), N(1)),
                   play_sound(b, LETTER_SOUND)))
    a.define_function("backspace", [], f)

    f = AS()  # function keyTap(k): a touched key
    if_(f, binop(binop(V("mode"), N(2), "eq"), binop(V("okt"), N(0), "eq"), "and"),
        lambda b: (setv(b, "ksel", V("k")), b.call("keyPress", V("k")).op("pop")))
    a.define_function("keyTap", ["k"], f)

    # Buttons: function onBtn(bits, changed) on presses only; none while a game is starting.
    h = AS()
    local(h, "p", binop(V("bits"), V("changed"), "and"))
    l_end = fresh("btn")
    h.getvar("go").push(-1).op("eq").op("not").if_true(l_end)
    if_(h, pressed(BTN_HOME), lambda b: b.callv("BT_StartSDGame", HOME_PATH))

    def list_mode(b):
        if_(b, binop(pressed(BTN_DOWN), binop(V("sel"), binop(V("n"), N(1), "sub"), "lt"), "and"),
            lambda c: (setv(c, "sel", binop(V("sel"), N(1), "add")), c.call("moveSound", 1).op("pop"), c.call("show").op("pop")))
        if_(b, binop(pressed(BTN_UP), binop(V("sel"), N(0), "gt"), "and"),
            lambda c: (setv(c, "sel", binop(V("sel"), N(1), "sub")), c.call("moveSound", -1).op("pop"), c.call("show").op("pop")))
        if_(b, binop(pressed(BTN_RIGHT), binop(V("n"), N(0), "gt"), "and"), lambda c: c.call("page", 1).op("pop"))
        if_(b, binop(pressed(BTN_LEFT), binop(V("n"), N(0), "gt"), "and"), lambda c: c.call("page", -1).op("pop"))
        if_(b, binop(pressed(BTN_A), binop(V("n"), N(0), "gt"), "and"),
            lambda c: c.call("launch", cat(V("ord"), V("sel")).op("getmember")).op("pop"))
        if_(b, pressed(BTN_PAUSE), lambda c: c.call("openOpt").op("pop"))

    def opt_mode(b):
        if_(b, binop(pressed(BTN_DOWN), binop(V("osel"), N(len(OPTIONS) - 1), "lt"), "and"),
            lambda c: (setv(c, "osel", binop(V("osel"), N(1), "add")), c.call("optShow").op("pop")))
        if_(b, binop(pressed(BTN_UP), binop(V("osel"), N(0), "gt"), "and"),
            lambda c: (setv(c, "osel", binop(V("osel"), N(1), "sub")), c.call("optShow").op("pop")))
        if_(b, pressed(BTN_A), lambda c: c.call("optPick", V("osel")).op("pop"),
            lambda c: if_(c, binop(pressed(BTN_B), pressed(BTN_PAUSE), "or"), lambda d: d.call("closeOpt").op("pop")))

    def kb_mode(b):
        # D-pad on the 7 x 4 grid; the bottom row holds delete, clear and OK.
        def right(c):
            if_(c, binop(V("ksel"), N(nkeys), "lt"),
                lambda d: if_(d, binop(binop(V("ksel"), N(7), "mod"), N(6), "lt"), lambda e: setv(e, "ksel", binop(V("ksel"), N(1), "add"))),
                lambda d: if_(d, binop(V("ksel"), N(nkeys + 2), "lt"), lambda e: setv(e, "ksel", binop(V("ksel"), N(1), "add"))))

        def left(c):
            if_(c, binop(V("ksel"), N(nkeys), "lt"),
                lambda d: if_(d, binop(binop(V("ksel"), N(7), "mod"), N(0), "gt"), lambda e: setv(e, "ksel", binop(V("ksel"), N(1), "sub"))),
                lambda d: if_(d, binop(V("ksel"), N(nkeys), "gt"), lambda e: setv(e, "ksel", binop(V("ksel"), N(1), "sub"))))

        def down(c):  # columns 0-1 -> delete, 2-4 -> clear, 5-6 -> OK
            if_(c, binop(V("ksel"), N(nkeys - 7), "lt"), lambda d: setv(d, "ksel", binop(V("ksel"), N(7), "add")),
                lambda d: if_(d, binop(V("ksel"), N(nkeys), "lt"), lambda e: (
                    setv(e, "ksel", N(nkeys + 1)),
                    if_(e, binop(binop(V("ksel"), N(7), "mod"), N(2), "lt"), lambda g: setv(g, "ksel", N(nkeys))),
                    if_(e, binop(binop(V("ksel"), N(7), "mod"), N(4), "gt"), lambda g: setv(g, "ksel", N(nkeys + 2))))))

        def up(c):
            if_(c, binop(V("ksel"), N(nkeys), "lt"),
                lambda d: if_(d, binop(V("ksel"), N(7), "lt").op("not"), lambda e: setv(e, "ksel", binop(V("ksel"), N(7), "sub"))),
                lambda d: if_(d, binop(V("ksel"), N(nkeys), "eq"), lambda e: setv(e, "ksel", N(nkeys - 7)),
                              lambda e: if_(e, binop(V("ksel"), N(nkeys + 1), "eq"), lambda g: setv(g, "ksel", N(nkeys - 4)),
                                            lambda g: setv(g, "ksel", N(nkeys - 2)))))
        for bit, fn in ((BTN_RIGHT, right), (BTN_LEFT, left), (BTN_DOWN, down), (BTN_UP, up)):
            if_(b, pressed(bit), lambda c, fn=fn: (fn(c), c.call("kbShow").op("pop")))
        if_(b, pressed(BTN_A), lambda c: c.call("keyPress", V("ksel")).op("pop"))
        if_(b, pressed(BTN_B), lambda c: (c.call("backspace").op("pop"), c.call("kbShow").op("pop")))

        def cancel(c):
            setv(c, "mode", V("kfrom"))
            visible(c, "/kb", N(0))
        if_(b, pressed(BTN_PAUSE), cancel)

    def about_mode(b):
        def back(c):
            setv(c, "mode", N(1))
            visible(c, "/pm/ab", N(0))
        if_(b, binop(V("p"), N(BTN_A | BTN_B | BTN_PAUSE), "and"), back)
    # One mode per press: a handler may change `mode`, so each jumps to the end.
    _kb_mode = kb_mode

    def kb_mode(b):  # (no keys while the OK key blinks)
        if_(b, binop(V("okt"), N(0), "eq"), _kb_mode)
    for m, fn in enumerate((list_mode, opt_mode, kb_mode, about_mode)):
        skip = fresh("mode")
        h.code.extend(binop(V("mode"), N(m), "eq").code)
        h.op("not").if_true(skip)
        fn(h)
        h.jump(l_end)
        h.label(skip)
    h.label(l_end)
    a.define_function("onBtn", ["bits", "changed"], h)

    # Button events, as LeapFrog's LeapsterASLibrary registers them: an object
    # whose doRegister is LF_RegisterCallback, called with event type 3; the
    # player fills ret1/ret2 and calls doCall.
    ctor = AS().getvar("this").push("callbackFunction").getvar("cb").op("setmember") \
        .getvar("this").push("ret1", "").op("setmember").getvar("this").push("ret2", "").op("setmember") \
        .push(3, 1).getvar("this").push("doRegister").op("callmethod").op("pop")
    a.define_function("ButtonEvents", ["cb"], ctor)
    a.getvar("ButtonEvents").push("prototype").op("getmember").push("doRegister").getvar("LF_RegisterCallback").op("setmember")
    call = AS().getvar("this").push("ret2").op("getmember").getvar("this").push("ret1").op("getmember") \
        .push(2).getvar("this").push("callbackFunction").op("callmethod").op("pop")
    a.getvar("ButtonEvents").push("prototype").op("getmember").push("doCall").define_function("", [], call).op("setmember")
    a.push("buttonEvents").getvar("onBtn").push(1, "ButtonEvents").op("newobject").raw(0x1D)
    # System buttons (type 5): the player fills ret1..ret3 = sysButton, bIsPressed, newSysValue.
    ctor = AS().getvar("this").push("callbackFunction").getvar("cb").op("setmember")         .getvar("this").push("ret1", "").op("setmember").getvar("this").push("ret2", "").op("setmember")         .getvar("this").push("ret3", "").op("setmember")         .push(5, 1).getvar("this").push("doRegister").op("callmethod").op("pop")
    a.define_function("SystemEvents", ["cb"], ctor)
    a.getvar("SystemEvents").push("prototype").op("getmember").push("doRegister").getvar("LF_RegisterCallback").op("setmember")
    call = AS().getvar("this").push("ret3").op("getmember").getvar("this").push("ret2").op("getmember")         .getvar("this").push("ret1").op("getmember")         .push(3).getvar("this").push("callbackFunction").op("callmethod").op("pop")
    a.getvar("SystemEvents").push("prototype").op("getmember").push("doCall").define_function("", [], call).op("setmember")
    f = AS()  # function onSys(b, down, v): Pause pressed -> onBtn
    if_(f, binop(binop(V("b"), N(SYS_PAUSE), "eq"), V("down"), "and"),
        lambda c: c.call("onBtn", N(BTN_PAUSE), N(BTN_PAUSE)).op("pop"))
    a.define_function("onSys", ["b", "down", "v"], f)
    a.push("systemEvents").getvar("onSys").push(1, "SystemEvents").op("newobject").raw(0x1D)

    visible(a, "/pm", N(0))
    visible(a, "/tg", N(0))
    visible(a, "/kb", N(0))
    a.call("load").op("pop")
    a.call("rebuild").op("pop")
    if music:
        # Background music: the song rendered with the BIOS's instruments (musicrender.py), looping.
        if_(a, V("mus"), lambda b: b.call("musStart").op("pop"))
    if welcome:
        # On a voice, as the BIOS's own sounds: a SWF sound goes through the player's mix, which cuts
        # everything under ~300 Hz (sndgen.py).
        a.callv("LF_SetRawVolume", RAW_VOLUME)
        play_sound(a, welcome_handle)
        a.callv("LF_SetRawVolume", 100)
    a.op("stop")

    ticker = AS().call("_level0:tick").op("pop")
    tags += [place(1, ID_SKY_LIST, 0, 0), place(2, ID_LIST, 0, TOP, name="list"), place(3, ID_SKY_TOP, 0, 0),
             place(17, sky_bottom, 0, 0),
             place(4, ID_FROG, 124, 4), place(5, title_text, 0, 0), place(6, title_text + 1, 0, 0)]
    if total:
        tags += [place(12, ID_TOOL_GLOW, TOOL_X, SEARCH_Y, name="tg"), place(13, ID_SPR_SEARCH, TOOL_X, SEARCH_Y, name="ts"), place(14, ID_SPR_UP, TOOL_X, UP_Y, name="tu"),
                 place(15, ID_SPR_DOWN, TOOL_X, DOWN_Y, name="td")]
    tags += [place(7, ID_HEAD_GAMES, 0, 0, name="hg"), place(8, ID_HEAD_SEARCH, 0, 0, name="hs"),
             place(9, ID_NONE, 0, 0, name="none"), place(10, ID_FOOTER_BAR, 0, 0), place(11, ID_FOOTER_TEXT, 0, 0)]
    if total:
        tags.append(place(18, ID_PAGE, 0, 0, name="pg"))
    if total:
        tags.append(place_enterframe(16, ID_TICKER, ticker))
    tags += [place(20, ID_OPTIONS, 0, 0, name="pm"), place(21, ID_KEYBOARD, 0, 0, name="kb")]
    tags += [do_action(a), show_frame()]
    movie = swf(tags, bg=SKY[0], frame_rate=20)
    return pack_rib([movie], title="LeapLoader " + version, part="LL-MENU", approval=approval,
                    raw_sounds=raw, sequences=[music_seq] if music_seq else ())


if __name__ == "__main__":
    out, src, *items = sys.argv[1:]
    games = [tuple(x.split("|", 1)) for x in items]
    data = build_menu(games, approval_fields(open(src, "rb").read()))
    open(out, "wb").write(data)
    print(f"menu with {len(games)} games, {len(data)} bytes -> {out}")
