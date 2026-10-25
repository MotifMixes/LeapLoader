import struct, sys
# usage: leapdir.py image load_base
p, load = sys.argv[1], int(sys.argv[2], 16)
d = open(p, 'rb').read()
u16 = lambda o: struct.unpack_from('<H', d, o)[0]
u32 = lambda o: struct.unpack_from('<I', d, o)[0]
def off(a): return a - load
h = 0x100
print(f'RIB: base={u32(h+0x1c):08x} end={u32(h+0x20):08x} +24={u32(h+0x24):08x} ck={u32(h+0x28):08x} size={len(d):#x}')
leap = 0 if d[:4] == b'LEAP' else off(u32(0x140))
print(f'LEAP at file {leap:#x}: ver={u16(leap+4):#x} n={u16(leap+6)}  +8..+0x20: {d[leap+8:leap+0x20].hex()}')
n = u16(leap + 6)
for i in range(n):
    e = leap + 0x20 + 8 * i
    tag, cnt, ptr = u16(e), u16(e + 2), u32(e + 4)
    print(f'  tag {tag:#06x} count {cnt:3} ptr {ptr:08x}')
    for j in range(cnt):
        s = off(ptr) + 8 * j
        rid, fl, val = u16(s), u16(s + 2), u32(s + 4)
        inside = load <= val < load + len(d)
        extra = ''
        if inside:
            t = d[off(val):off(val) + 24]
            extra = ' ' + repr(t.split(b'\0')[0][:40]) if all(32 <= c < 127 for c in t.split(b'\0')[0][:8]) and t[0] else ' ' + t[:12].hex()
        print(f'     id {rid:#06x} flags {fl:#06x} value {val:08x}{" ->" if inside else ""}{extra}')
