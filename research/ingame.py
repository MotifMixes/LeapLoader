"""Prototype (research): in a game booted from SD, holding HINT + A + B brings up
"Back to the LeapLoader menu?" (or "Back to the SD Menu" with LeapFrog's menu); keeping them held until the bar fills returns to
the menu, letting go cancels (the prompt only says to keep holding).

Why not PAUSE: PAUSE is a system button. The BIOS pauses the game, reports PAUSE
and HINT as released at once while they are still held, and freezes the Flash
player (no frames), so no prompt could be shown (VERIFIED-EMU, 1st Grade).

How it works (all VERIFIED-EMU, BIOS 0.6):
* Several listeners can be registered for the same event: the game keeps its own.
  Button events (type 3) give (bits, changed): A 4096, B 8192, HOME 16384, HINT 32768.
  System buttons (type 5) give (code, state, x); PAUSE is code 8.
* The prompt is its own small movie, added to the end of the game's movie table (handle
  first + count, sdpack.add_saves) and loaded into _level OVERLAY_LEVEL (above every level
  the game uses) the way games load theirs: getURL(lfh("<handle>"), "_level<n>").
* Going back: pending saves are written, then BT_StartSDMenu (BIOS 0x40022C8C)
  points PlayGame.lnk at \\Leapster\\System\\SDMenu\\SDMenu.bin and the console
  reboots into it.

The watcher runs every frame from the save shim's flusher clip (saveshim.build_flusher).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swfgen import (AS, define_font, define_shape_layers, define_sprite, define_text, do_action, place,  # noqa: E402
                    rounded_rects, set_property, show_frame, swf)

OVERLAY_LEVEL = 999
HOLD_MS = 2500
BTN_A, BTN_B, BTN_HINT = 4096, 8192, 32768
COMBO = BTN_HINT | BTN_A | BTN_B

PANEL, PANEL_EDGE, TEXT, YELLOW = 0x3A0F6B, 0xFFD21F, 0xFFFFFF, 0xFFD21F
TRACK, BAR = 0x1B0533, 0x2FB548
BAR_X, BAR_Y, BAR_W, BAR_H = 26, 104, 108, 8


def build_overlay(menu_name="LeapLoader"):
    """The prompt movie (160 x 160; only its shapes are drawn over the game). `menu_name`: the menu
    HINT + A + B returns to (at most 10 characters at double size): "SD Menu" for LeapFrog's own."""
    tags = [define_font(1),
            define_shape_layers(2, [(PANEL_EDGE, rounded_rects(12, 34, 136, 88, 4)),
                                    (PANEL, rounded_rects(15, 37, 130, 82, 3)),
                                    ]),
            define_shape_layers(3, [(TRACK, rounded_rects(BAR_X - 2, BAR_Y - 2, BAR_W + 4, BAR_H + 4, 2))]),
            define_shape_layers(4, [(BAR, [(0, 0, BAR_W, BAR_H)])]),
            define_text(5, 1, [(22, 52, TEXT, "Back to the")]),
            define_text(6, 1, [(20, 72, YELLOW, menu_name)], scale=2),
            define_text(7, 1, [(22, 88, TEXT, "Keep holding"), (22, 99, YELLOW, "HINT + A + B")]),
            define_sprite(8, [place(1, 4, 0, 0), show_frame()])]
    a = AS()
    set_property(a, "bar", 2, AS().push(0))  # _xscale: empty until the watcher sets it
    a.op("stop")
    tags += [place(1, 2, 0, 0), place(2, 3, 0, 0), place(3, 8, BAR_X, BAR_Y, name="bar"),
             place(4, 5, 0, 0), place(5, 6, 0, 0), place(6, 7, 0, 0), do_action(a), show_frame()]
    return swf(tags, frame_rate=20)


def _events_class(a, name, etype, nrets):
    """A listener class as LeapFrog's LeapsterASLibrary builds them."""
    ctor = AS().getvar("this").push("callbackFunction").getvar("cb").op("setmember")
    for k in range(1, nrets + 1):
        ctor.getvar("this").push(f"ret{k}", "").op("setmember")
    ctor.push(etype, 1).getvar("this").push("doRegister").op("callmethod").op("pop")
    a.define_function(name, ["cb"], ctor)
    a.getvar(name).push("prototype").op("getmember").push("doRegister").getvar("LF_RegisterCallback").op("setmember")
    call = AS()
    for k in range(nrets, 0, -1):
        call.getvar("this").push(f"ret{k}").op("getmember")
    call.push(nrets).getvar("this").push("callbackFunction").op("callmethod").op("pop")
    a.getvar(name).push("prototype").op("getmember").push("doCall").define_function("", [], call).op("setmember")


def build_watcher(flush_as, overlay_handle, poll=False):
    """ActionScript for the main movie's first frame (on _level0). `flush_as` writes
    pending saves (the shim's flusher body); `overlay_handle`: the prompt movie's handle.
    `poll`: the game has the RAM chip stub, which reads the buttons each frame; the flusher puts the
    result in __llK (some games keep the button events from the listener: eestub.py)."""
    a = AS()
    a.push("__llKeys", False).raw(0x1D)
    a.push("__llHold", -1).raw(0x1D)
    a.define_function("__llBtn", ["bits", "ch"],
                      AS().push("__llKeys").getvar("bits").push(COMBO).op("and").push(COMBO).op("eq").raw(0x1D))
    _events_class(a, "__llBE", 3, 2)
    a.push("__llKB").getvar("__llBtn").push(1, "__llBE").op("newobject").raw(0x1D)

    go = AS()
    go.code.extend(flush_as.code)
    go.push("__llHold", -2).raw(0x1D)
    go.callv("BT_StartSDMenu")
    a.define_function("__llGo", [], go)

    t = AS()
    if poll:
        t.push("__llKeys").getvar("__llK").raw(0x1D)
    t.getvar("__llHold").push(-2).op("eq").if_true("end")          # already leaving
    t.getvar("__llKeys").op("not").if_true("up")
    t.getvar("__llHold").push(0).op("lt").op("not").if_true("held")
    t.push("__llHold").raw(0x34).raw(0x1D)                           # __llHold = getTimer()
    # loadMovieNum(lfh("<handle>"), OVERLAY_LEVEL), as games load theirs (GetURL2, method 0)
    t.call("lfh", str(overlay_handle)).push("_level" + str(OVERLAY_LEVEL)).raw(0x9A, b"\x00")
    t.label("held")
    t.push("p").raw(0x34).getvar("__llHold").op("sub").push(100).op("mul").push(HOLD_MS).op("div").raw(0x3C)
    t.getvar("p").push(100).op("lt").if_true("show")
    t.call("__llGo").op("pop")
    t.jump("end")
    t.label("show")
    set_property(t, f"_level{OVERLAY_LEVEL}/bar", 2, AS().getvar("p"))
    t.jump("end")
    t.label("up")
    t.getvar("__llHold").push(0).op("lt").if_true("end")
    t.push("__llHold", -1).raw(0x1D)
    t.raw(0x83, b"\x00" + f"_level{OVERLAY_LEVEL}".encode() + b"\x00")  # getURL("", "_level999"): unload
    t.label("end")
    a.define_function("__llTick", [], t)
    return a
