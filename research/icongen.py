"""Prototype (research): generates a game icon for LeapFrog's own SD menus.

LeapFrog's SD menu (SDMenu.bin from LSTR-0x00130001 or the factory card's
0x00130006) shows each game in \\Leapster\\Apps\\ as a round button drawn from the
SWF named by `Icon=` in the game's meta.inf, at its own size: LeapFrog's icons are
160 x 160 movies whose artwork is a disc about 36 pixels across centred at (18, 18)
(dSTAR_Icon.swf), which the menu rings with its button. This one is drawn from
scratch: a disc in a colour picked from the title, the title in pixel letters, a shine.

Usage: python icongen.py OUT.swf "Title"
"""
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pixelfont import ADVANCE  # noqa: E402
from swfgen import define_font, define_shape_layers, define_text, place, show_frame, swf  # noqa: E402

SIZE = 36          # disc diameter (pixels)
LINE_H = 9
MAX_CHARS = 5      # per line: 5 x 6 pixels fits inside the disc
COLOURS = [0x1E6FD9, 0xD9361E, 0x2FA84F, 0x8A3FC7, 0xE08A12, 0x139C9C, 0xC7337A, 0x5A6B7D]
SHADOW = 0x101820


def lines_of(title, max_lines=3):
    """Words wrapped to MAX_CHARS per line; long words are cut."""
    words = [w for w in title.replace("-", " ").replace(":", " ").split() if w]
    out = []
    for w in words:
        if out and len(out[-1]) + 1 + len(w) <= MAX_CHARS:
            out[-1] += " " + w
        else:
            out.append(w[:MAX_CHARS])
    return out[:max_lines] or ["?"]


def disc_rows(cx, cy, r):
    """A filled pixel circle as one rectangle per row."""
    out = []
    for y in range(-r, r):
        half = int((r * r - (y + 0.5) ** 2) ** 0.5 + 0.5)
        if half > 0:
            out.append((cx - half, cy + y, 2 * half, 1))
    return out


def build_icon(title):
    colour = COLOURS[(zlib.crc32(title.encode("latin-1", "replace")) >> 16) % len(COLOURS)]
    lines = lines_of(title.upper())
    c = SIZE // 2
    top = c - (LINE_H * len(lines)) // 2 + 8
    text = []
    for i, s in enumerate(lines):
        text.append((c - (ADVANCE * len(s) - 1) // 2, top + i * LINE_H, s))
    tags = [define_font(1),
            define_shape_layers(2, [(colour, disc_rows(c, c, c))]),
            define_shape_layers(3, [(0xFFFFFF, [(c - 7, 3, 14, 1), (c - 10, 4, 20, 1)])]),
            define_text(4, 1, [(x + 1, y + 1, SHADOW, s) for x, y, s in text]),
            define_text(5, 1, [(x, y, 0xFFFFFF, s) for x, y, s in text]),
            place(1, 2, 0, 0), place(2, 3, 0, 0), place(3, 4, 0, 0), place(4, 5, 0, 0), show_frame()]
    return swf(tags, frame_rate=8, bg=0xFFFFFF)


if __name__ == "__main__":
    open(sys.argv[1], "wb").write(build_icon(sys.argv[2]))
