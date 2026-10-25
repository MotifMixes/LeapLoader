"""Prototype (research): gives SD-loaded games working saves.

On a cartridge, games save through the BIOS natives LF_*CartridgeMemory*, which
reach the cartridge's I2C save chip. Booted from SD there is no chip. This module:

1. builds an ActionScript "shim": functions on _level0 that behave like those
   natives (semantics read from BIOS 0.6, 0x400A_0528-0x400A_0896) but keep the
   save memory in RAM, loaded once from a file on the SD card (SD_ReadText, BIOS
   0x4002_C054) and written back (SD_WriteText, 0x4002_BF54) by a small clip on
   the next frame after any change, so a burst of writes costs one SD write;
2. renames the natives in every movie of the game to same-length paths to those
   functions ("_level0:__ll..."), so no movie changes size.

Native semantics reproduced:
  ReadBytes(addr, n):   n bytes little-endian; n=1 and n=2 sign-extended, n>=3 as int32
  WriteBytes(addr, v, n): n bytes of int(v), little-endian
  ReadString(addr, n):  up to n bytes, stopping at NUL
  WriteString(addr, s, n): exactly n bytes: s, zero padded (truncated to n)
  GetCartridgeMemorySize(): the cartridge's EEPROM size (its 0x1005/3 descriptor; 256 on the titles seen)
Addresses wrap at the memory size, as on the cartridges' 24LC02B (8-bit word address):
1st Grade's eraseAllCartData clears addresses 0..size inclusive (an off-by-one).
  ReadFloat(addr):      4 bytes little-endian as an IEEE single (BIOS 0x400A_07C0: read 4, widen
                        with 0x400E_F8E0); erased memory (FF FF FF FF) reads as NaN
  WriteFloat(addr, v):  v rounded to an IEEE single (0x400A_060C: 0x400E_F98C), 4 bytes little-endian

Performance notes (BIOS 0.6 in Ribbit, research/sdboot-emu micro-benchmarks):
  ~0.35 ms per loop step, ~1.3 ms per ActionScript function call, ~0.55 ms per native
  call, and ~36 ms for a call that rebuilds a 512-character string. So the memory is
  kept as arrays (numbers, and the same bytes as 2-character hex strings): reads and
  writes touch only array elements, and saving is one native join(""). String.split
  is never used: in this player it aborts the script after a few uses (VERIFIED-EMU).
  Temporaries are DefineLocal (0x3C) so the game's timeline variables are never
  touched, and no two locals differ only in case (Flash 5 identifiers are
  case-insensitive).

Save file: \\Leapster\\Apps\\<game>\\save.dat, 2 hex characters per byte (512 for 256 bytes).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swfgen import AS, method  # noqa: E402

NATIVES = {
    "LF_ReadCartridgeMemoryBytes": "RB",
    "LF_WriteCartridgeMemoryBytes": "WB",
    "LF_ReadCartridgeMemoryString": "RS",
    "LF_WriteCartridgeMemoryString": "WS",
    "LF_GetCartridgeMemorySize": "SZ",
    "LF_ReadCartridgeMemoryFloat": "RF",
    "LF_WriteCartridgeMemoryFloat": "WF",
}
FLOAT_NATIVES = ()  # shimmed since 2026-10-25 (4-byte IEEE single, as BIOS 0x400A_060C/0x400A_07C0)
PREFIX = "_level0:"


HEX_NOTE = """String methods (substr, parseInt, charCodeAt) cost ~12 ms per character of their string
on the Leapster's player, so parsing a save with them held every game's start up by ~3 s (1st Grade,
VERIFIED-EMU); the loaders use the StringExtract / CharToAscii opcodes and a hex -> value table."""


def hex_values(a):
    """__llHV["00".."ff"] = 0..255, from __llHT (lowercase hex, as the save files hold)."""
    a.push("__llHV").push(0, "Object").op("newobject").raw(0x1D)
    a.push("__llk", 0).raw(0x1D)  # (the game's _level0: no plain names)
    a.label("hv")
    a.getvar("__llHV").getvar("__llHT").getvar("__llk").op("getmember").getvar("__llk").op("setmember")
    a.push("__llk").getvar("__llk").push(1).op("add").raw(0x1D)
    a.getvar("__llk").push(256).op("lt").if_true("hv")


def shim_name(native):
    """The function name whose "_level0:" path has exactly the native's length."""
    n = len(native) - len(PREFIX)
    return ("__ll" + NATIVES[native] + "_" * n)[:n]


def rename_map():
    return {n.encode(): (PREFIX + shim_name(n)).encode() for n in NATIVES}


def g(name):
    """Push the value of _level0's variable `name`."""
    return AS().push("_level0:" + name).raw(0x1C)


def build_shim(save_path, size):
    """ActionScript for the main movie's first frame: the shim functions on _level0.
    Memory: _level0.__llM (numbers) and _level0.__llH (the same bytes as hex strings)."""
    if size % 32 or size & (size - 1):
        raise ValueError("save memory size must be a power of two and a multiple of 32 bytes")
    a = AS()
    a.push("__llPath", save_path).raw(0x1D)
    a.push("__llSize", size).raw(0x1D)
    a.push("__llDirty", False).raw(0x1D)
    # __llHT[v] = hex string of v, built natively by InitArray.
    a.push("__llHT")
    a.push(*[f"{v:02x}" for v in reversed(range(256))])
    a.push(256).op("initarray").raw(0x1D)

    # function __llLoad(): load the memory once (erased, 0xFF, where the file has no data).
    ld = AS()
    ld.code.extend(g("__llM").code)
    ld.push(None).op("eq").op("not").if_true("have")
    ld.push("m").push(*([255] * size)).push(size).op("initarray").raw(0x3C)
    ld.push("h").push(*(["ff"] * size)).push(size).op("initarray").raw(0x3C)
    ld.push("s").call("SD_ReadText", g("__llPath")).raw(0x3C)
    ld.getvar("s").op("typeof").push("string").op("eq").op("not").if_true("store")
    ld.getvar("s").push("length").op("getmember").push(2 * size).op("lt").if_true("store")
    hex_values(ld)
    ld.push("c", 0).raw(0x3C)
    ld.label("chunk")
    ld.getvar("c").push(size // 32).op("lt").op("not").if_true("store")
    ld.push("line")
    ld.getvar("s").getvar("c").push(64).op("mul").push(1).op("add").push(64).op("substr")  # (opcode: see HEX_NOTE)
    ld.raw(0x3C)
    ld.push("i", 0).raw(0x3C)
    ld.label("byte")
    ld.getvar("i").push(32).op("lt").op("not").if_true("next")
    ld.push("x")
    ld.getvar("line").getvar("i").push(2).op("mul").push(1).op("add").push(2).op("substr")
    ld.raw(0x3C)
    ld.push("v").code.extend(g("__llHV").code)
    ld.getvar("x").op("getmember").raw(0x3C)
    ld.getvar("v").op("typeof").push("number").op("eq").op("not").if_true("skip")
    ld.push("k").getvar("c").push(32).op("mul").getvar("i").op("add").raw(0x3C)
    ld.getvar("m").getvar("k").getvar("v").op("setmember")
    ld.getvar("h").getvar("k").getvar("x").op("setmember")
    ld.label("skip")
    ld.push("i").getvar("i").push(1).op("add").raw(0x3C)
    ld.jump("byte")
    ld.label("next")
    ld.push("c").getvar("c").push(1).op("add").raw(0x3C)
    ld.jump("chunk")
    ld.label("store")
    ld.push("_level0").raw(0x1C).push("__llM").getvar("m").op("setmember")
    ld.push("_level0").raw(0x1C).push("__llH").getvar("h").op("setmember")
    ld.label("have")
    a.define_function("__llLoad", [], ld)

    def load_local(f):
        """mem = _level0.__llM, loading it first if needed (one path lookup per call)."""
        f.push("mem").code.extend(g("__llM").code)
        f.raw(0x3C)
        f.getvar("mem").push(None).op("eq").op("not").if_true("loaded")
        f.call("_level0:__llLoad").op("pop")
        f.push("mem").code.extend(g("__llM").code)
        f.raw(0x3C)
        f.label("loaded")

    def tables(f):
        f.push("hex").code.extend(g("__llH").code)
        f.raw(0x3C)
        f.push("ht").code.extend(g("__llHT").code)
        f.raw(0x3C)

    def byte_at(f, index_as):
        f.getvar("mem")
        f.code.extend(index_as.code)
        f.push(size - 1).op("and").op("getmember")

    def put(f, index_as, value_as):
        """mem[k] = b; hex[k] = ht[b] (locals k, b)."""
        f.push("k")
        f.code.extend(index_as.code)
        f.push(size - 1).op("and").raw(0x3C)
        f.push("b")
        f.code.extend(value_as.code)
        f.push(255).op("and").raw(0x3C)
        f.getvar("mem").getvar("k").getvar("b").op("setmember")
        f.getvar("hex").getvar("k").getvar("ht").getvar("b").op("getmember").op("setmember")

    def mark_dirty(f):
        f.push("_level0").raw(0x1C).push("__llDirty", True).op("setmember")

    # Size.
    sz = AS()
    sz.code.extend(g("__llSize").code)
    a.define_function(shim_name("LF_GetCartridgeMemorySize"), [], sz.op("return"))

    # ReadBytes(addr, n)
    rb = AS()
    load_local(rb)
    rb.push("v", 0).raw(0x3C)
    rb.push("i", 0).raw(0x3C)
    rb.label("loop")
    rb.getvar("i").getvar("n").op("lt").op("not").if_true("done")
    rb.push("v").getvar("v")
    byte_at(rb, AS().getvar("addr").getvar("i").op("add"))
    rb.getvar("i").push(8).op("mul").op("shl").op("or").raw(0x3C)
    rb.push("i").getvar("i").push(1).op("add").raw(0x3C)
    rb.jump("loop")
    rb.label("done")
    for n, top in ((1, 128), (2, 32768)):
        rb.getvar("n").push(n).op("eq").op("not").if_true(f"s{n}")
        rb.getvar("v").push(top).op("lt").if_true(f"s{n}")
        rb.push("v").getvar("v").push(2 * top).op("sub").raw(0x3C)
        rb.label(f"s{n}")
    rb.getvar("v").op("return")
    a.define_function(shim_name("LF_ReadCartridgeMemoryBytes"), ["addr", "n"], rb)

    # WriteBytes(addr, value, n)
    wb = AS()
    load_local(wb)
    tables(wb)
    wb.push("i", 0).raw(0x3C)
    wb.label("loop")
    wb.getvar("i").getvar("n").op("lt").op("not").if_true("done")
    put(wb, AS().getvar("addr").getvar("i").op("add"), AS().getvar("value").getvar("i").push(8).op("mul").op("shr"))
    wb.push("i").getvar("i").push(1).op("add").raw(0x3C)
    wb.jump("loop")
    wb.label("done")
    mark_dirty(wb)
    a.define_function(shim_name("LF_WriteCartridgeMemoryBytes"), ["addr", "value", "n"], wb)

    # ReadString(addr, n)
    rs = AS()
    load_local(rs)
    rs.push("out", "").raw(0x3C)
    rs.push("i", 0).raw(0x3C)
    rs.label("loop")
    rs.getvar("i").getvar("n").op("lt").op("not").if_true("done")
    rs.push("c")
    byte_at(rs, AS().getvar("addr").getvar("i").op("add"))
    rs.raw(0x3C)
    rs.getvar("c").push(0).op("eq").if_true("done")
    rs.push("out").getvar("out").getvar("c").op("chr").op("add").raw(0x3C)
    rs.push("i").getvar("i").push(1).op("add").raw(0x3C)
    rs.jump("loop")
    rs.label("done")
    rs.getvar("out").op("return")
    a.define_function(shim_name("LF_ReadCartridgeMemoryString"), ["addr", "n"], rs)

    # WriteString(addr, str, n)
    ws = AS()
    load_local(ws)
    tables(ws)
    ws.push("txt").getvar("str").op("tostring").raw(0x3C)
    ws.push("L").getvar("txt").push("length").op("getmember").raw(0x3C)
    ws.push("i", 0).raw(0x3C)
    ws.label("loop")
    ws.getvar("i").getvar("n").op("lt").op("not").if_true("done")
    ws.push("c", 0).raw(0x3C)
    ws.getvar("i").getvar("L").op("lt").op("not").if_true("put")
    ws.push("c")
    ws.getvar("txt").getvar("i").push(1).op("add").push(1).op("substr").op("ord")
    ws.raw(0x3C)
    ws.label("put")
    put(ws, AS().getvar("addr").getvar("i").op("add"), AS().getvar("c"))
    ws.push("i").getvar("i").push(1).op("add").raw(0x3C)
    ws.jump("loop")
    ws.label("done")
    mark_dirty(ws)
    a.define_function(shim_name("LF_WriteCartridgeMemoryString"), ["addr", "str", "n"], ws)

    def inc(f, name, by=1):
        f.push(name).getvar(name).push(by).op("add").raw(0x3C)

    # ReadFloat(addr): sign, exponent and mantissa from the 4 bytes.
    rf = AS()
    load_local(rf)
    for k in range(4):
        rf.push(f"b{k}")
        byte_at(rf, AS().getvar("addr").push(k).op("add"))
        rf.raw(0x3C)
    rf.push("e").getvar("b3").push(127).op("and").push(1).op("shl").getvar("b2").push(7).op("shr").op("or").raw(0x3C)
    rf.push("m").getvar("b2").push(127).op("and").push(16).op("shl")         .getvar("b1").push(8).op("shl").op("or").getvar("b0").op("or").raw(0x3C)
    rf.getvar("e").push(255).op("eq").op("not").if_true("finite")
    rf.push(0, 0).op("div").op("return")  # NaN (and infinities, which games do not store)
    rf.label("finite")
    rf.push("v").getvar("m").push(8388608).op("div").raw(0x3C)
    rf.getvar("e").push(0).op("eq").op("not").if_true("normal")
    rf.push("v").getvar("v").push(2.0 ** -126).op("mul").raw(0x3C)  # denormal
    rf.jump("sign")
    rf.label("normal")
    rf.push("v").getvar("v").push(1).op("add").raw(0x3C)
    rf.push("k").getvar("e").push(127).op("sub").raw(0x3C)
    rf.label("up")
    rf.getvar("k").push(0).op("gt").op("not").if_true("down")
    rf.push("v").getvar("v").push(2).op("mul").raw(0x3C)
    inc(rf, "k", -1)
    rf.jump("up")
    rf.label("down")
    rf.getvar("k").push(0).op("lt").op("not").if_true("sign")
    rf.push("v").getvar("v").push(2).op("div").raw(0x3C)
    inc(rf, "k")
    rf.jump("down")
    rf.label("sign")
    rf.getvar("b3").push(128).op("lt").if_true("pos")
    rf.push("v", 0).getvar("v").op("sub").raw(0x3C)
    rf.label("pos")
    rf.getvar("v").op("return")
    a.define_function(shim_name("LF_ReadCartridgeMemoryFloat"), ["addr"], rf)

    # WriteFloat(addr, value): normalise to 1 <= v < 2 (or a denormal), round the mantissa.
    wf = AS()
    load_local(wf)
    tables(wf)
    wf.push("v").getvar("value").op("tonumber").raw(0x3C)
    wf.push("s", 0).raw(0x3C)
    wf.getvar("v").push(0).op("lt").op("not").if_true("abs")
    wf.push("s", 1).raw(0x3C)
    wf.push("v", 0).getvar("v").op("sub").raw(0x3C)
    wf.label("abs")
    wf.push("e", 0).raw(0x3C)
    wf.push("m", 0).raw(0x3C)
    wf.getvar("v").push(0).op("eq").if_true("pack")
    wf.push("e", 127).raw(0x3C)
    wf.label("big")
    wf.getvar("v").push(2).op("lt").if_true("small")
    wf.getvar("e").push(254).op("lt").op("not").if_true("small")
    wf.push("v").getvar("v").push(2).op("div").raw(0x3C)
    inc(wf, "e")
    wf.jump("big")
    wf.label("small")
    wf.getvar("v").push(1).op("lt").op("not").if_true("norm")
    wf.getvar("e").push(1).op("gt").op("not").if_true("denorm")
    wf.push("v").getvar("v").push(2).op("mul").raw(0x3C)
    inc(wf, "e", -1)
    wf.jump("small")
    wf.label("denorm")
    wf.push("e", 0).raw(0x3C)
    wf.push("m").getvar("v").push(8388608).op("mul").push(0.5).op("add").op("int").raw(0x3C)
    wf.jump("pack")
    wf.label("norm")
    wf.push("m").getvar("v").push(1).op("sub").push(8388608).op("mul").push(0.5).op("add").op("int").raw(0x3C)
    wf.getvar("m").push(8388608).op("lt").if_true("pack")
    wf.push("m", 0).raw(0x3C)
    inc(wf, "e")
    wf.label("pack")
    put(wf, AS().getvar("addr"), AS().getvar("m"))
    put(wf, AS().getvar("addr").push(1).op("add"), AS().getvar("m").push(8).op("shr"))
    put(wf, AS().getvar("addr").push(2).op("add"),
        AS().getvar("m").push(16).op("shr").push(127).op("and").getvar("e").push(1).op("and").push(7).op("shl").op("or"))
    put(wf, AS().getvar("addr").push(3).op("add"),
        AS().getvar("s").push(7).op("shl").getvar("e").push(1).op("shr").op("or"))
    mark_dirty(wf)
    a.define_function(shim_name("LF_WriteCartridgeMemoryFloat"), ["addr", "value"], wf)
    return a


def build_flusher(size=256):
    """onClipEvent(enterFrame) actions: write the memory to the card once after changes."""
    f = AS()
    f.code.extend(g("__llDirty").code)
    f.op("not").if_true("end")
    f.push("_level0").raw(0x1C).push("__llDirty", False).op("setmember")
    f.call("SD_WriteText", g("__llPath"),
           AS().push("", 1).push("_level0").raw(0x1C).push("__llH").op("getmember").push("join").op("callmethod")).op("pop")
    f.label("end")
    return f


# ---- Games with native code: a save chip in RAM (eestub.py) behind the BIOS EEPROM interface.
EE_NATIVE = "__llEE"
KEYS_FLAG = 1 << 29  # eestub.KEYS_FLAG: __llEE's result while HINT + A + B are held


def build_ee_loader(save_path, size):
    """ActionScript for the main movie's first frame (native-code games): install the RAM chip;
    the stub reads the save file itself (eestub.load). And _level0.__llEEFlush(force): once a frame
    (the stub writes the file after eestub.QUIET frames without changes, or at once if `force`),
    and HINT + A + B held -> _level0.__llK for the watcher (ingame.py).
    Until 2026-10-25 this was ActionScript: the file was read byte by byte into the chip at start
    (seconds) and written from a hex copy joined into one string (a 2 KB chip: 4096 characters,
    which froze Cars for ~10 s and ended its HINT + A + B script before it got back to the menu)."""
    a = AS()
    a.call(EE_NATIVE, 0).op("pop")
    fl = AS()
    fl.push("r").call(EE_NATIVE, AS().getvar("force").op("tonumber")).raw(0x3C)
    fl.push("_level0").raw(0x1C).push("__llK").getvar("r").push(KEYS_FLAG).op("lt").op("not").op("setmember")
    a.define_function("__llEEFlush", ["force"], fl)
    return a


def build_ee_flusher(force=False):
    """The enterFrame call (force=False), or the final write before leaving (force=True)."""
    return AS().call("_level0:__llEEFlush", force).op("pop")
