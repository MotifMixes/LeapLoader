"""Read a FAT12/16/32 volume from a sparse sector file (records of u32 sector + 512 bytes).
sparsefat.py FILE ls            list every file (path, size, first cluster)
sparsefat.py FILE get PATH OUT  extract one file
sparsefat.py FILE info          partition / boot sector details"""
import struct, sys

def load(path):
    secs = {}
    with open(path, 'rb') as f:
        while True:
            h = f.read(4)
            if len(h) < 4: break
            secs[struct.unpack('<I', h)[0]] = f.read(512)
    return secs

class Vol:
    def __init__(self, secs):
        self.s = secs
        z = bytes(512)
        b0 = secs.get(0, z)
        self.base = 0
        if b0[510:512] == b'\x55\xaa' and b0[0] not in (0xEB, 0xE9):
            self.base = struct.unpack_from('<I', b0, 0x1C6)[0]
            self.ptype = b0[0x1C2]
        else:
            self.ptype = None
        bs = self.sec(0)
        self.bps, self.spc = struct.unpack_from('<H', bs, 11)[0], bs[13]
        self.res, self.nfats = struct.unpack_from('<H', bs, 14)[0], bs[16]
        self.rootents = struct.unpack_from('<H', bs, 17)[0]
        tot16, fat16 = struct.unpack_from('<H', bs, 19)[0], struct.unpack_from('<H', bs, 22)[0]
        self.total = tot16 or struct.unpack_from('<I', bs, 32)[0]
        self.fatsz = fat16 or struct.unpack_from('<I', bs, 36)[0]
        self.rootsecs = (self.rootents * 32 + 511) // 512
        self.first_data = self.res + self.nfats * self.fatsz + self.rootsecs
        clusters = (self.total - self.first_data) // self.spc
        self.kind = 12 if clusters < 4085 else 16 if clusters < 65525 else 32
        self.root_cluster = struct.unpack_from('<I', bs, 44)[0] if self.kind == 32 else None
        self.label = (bs[43:54] if self.kind != 32 else bs[71:82]).decode('latin-1')
        self.oem = bs[3:11].decode('latin-1')
    def sec(self, n):
        return self.s.get(self.base + n, bytes(512))
    def fat(self, c):
        if self.kind == 16:
            o = c * 2; return struct.unpack_from('<H', self.sec(self.res + o // 512), o % 512)[0]
        if self.kind == 32:
            o = c * 4; return struct.unpack_from('<I', self.sec(self.res + o // 512), o % 512)[0] & 0x0FFFFFFF
        o = c * 3 // 2
        lo = self.sec(self.res + o // 512)[o % 512]; hi = self.sec(self.res + (o + 1) // 512)[(o + 1) % 512]
        v = lo | hi << 8
        return v >> 4 if c & 1 else v & 0xFFF
    def chain(self, c):
        end = {12: 0xFF8, 16: 0xFFF8, 32: 0x0FFFFFF8}[self.kind]
        out = []
        while 2 <= c < end and len(out) < 1 << 20:
            out.append(c); c = self.fat(c)
        return out
    def read_clusters(self, c):
        data = b''
        for cl in self.chain(c):
            first = self.first_data + (cl - 2) * self.spc
            data += b''.join(self.sec(first + i) for i in range(self.spc))
        return data
    def dir_bytes(self, c):
        if c is None or c == 0:
            if self.kind == 32: return self.read_clusters(self.root_cluster)
            first = self.res + self.nfats * self.fatsz
            return b''.join(self.sec(first + i) for i in range(self.rootsecs))
        return self.read_clusters(c)
    def entries(self, c):
        raw = self.dir_bytes(c); lfn = []
        for i in range(0, len(raw), 32):
            e = raw[i:i + 32]
            if e[0] == 0: break
            if e[0] == 0xE5: lfn = []; continue
            if e[11] == 0x0F:
                part = e[1:11] + e[14:26] + e[28:32]
                lfn.insert(0, part.decode('utf-16le', 'replace').split('\x00')[0].replace('￿', '')); continue
            name = ''.join(lfn) if lfn else (e[0:8].decode('latin-1').rstrip() + ('.' + e[8:11].decode('latin-1').rstrip() if e[8:11].strip() else ''))
            lfn = []
            if e[11] & 0x08: continue
            cl = struct.unpack_from('<H', e, 26)[0] | struct.unpack_from('<H', e, 20)[0] << 16
            yield name, bool(e[11] & 0x10), struct.unpack_from('<I', e, 28)[0], cl
    def walk(self, c=None, path=''):
        for name, isdir, size, cl in self.entries(c):
            if name in ('.', '..'): continue
            p = path + '/' + name
            yield p, isdir, size, cl
            if isdir: yield from self.walk(cl, p)

if __name__ == '__main__':
    v = Vol(load(sys.argv[1]))
    cmd = sys.argv[2]
    if cmd == 'info':
        print(f'partition type {v.ptype} start {v.base}; FAT{v.kind}; {v.bps} B/sector; {v.spc} sec/cluster; total {v.total}; label {v.label!r}; oem {v.oem!r}')
    elif cmd == 'ls':
        for p, d, size, cl in v.walk():
            print(f'{"<dir>" if d else size:>10}  {p}')
    elif cmd == 'get':
        want = sys.argv[3].strip('/').lower()
        for p, d, size, cl in v.walk():
            if p.strip('/').lower() == want and not d:
                open(sys.argv[4], 'wb').write(v.read_clusters(cl)[:size]); print('ok', size); break
        else:
            print('not found')
