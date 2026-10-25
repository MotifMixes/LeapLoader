import struct, sys
# tags.py image [tag...]: show sub-entries of the given tags with a peek at their blobs
p = sys.argv[1]; want = {int(t, 16) for t in sys.argv[2:]}
d = open(p, 'rb').read(); B = 0x80000000; size = len(d)
u32 = lambda o: struct.unpack_from('<I', d, o)[0]; u16 = lambda o: struct.unpack_from('<H', d, o)[0]
leap = u32(0x140) - B
n = u16(leap + 6)
for i in range(n):
    tag, cnt, ptr = struct.unpack_from('<HHI', d, leap + 0x20 + 8 * i)
    if want and tag not in want: continue
    print(f'tag {tag:#06x} x{cnt}')
    for j in range(cnt):
        rid, fl, v = struct.unpack_from('<HHI', d, ptr - B + 8 * j)
        s = f'    id {rid:#06x} fl {fl:#06x} v {v:08x}'
        if B <= v < B + size:
            w = struct.unpack_from('<8I', d, v - B)
            s += '  -> ' + ' '.join(f'{x:08x}' for x in w)
        print(s)
