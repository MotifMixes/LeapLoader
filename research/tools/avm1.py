"""Minimal SWF (v5/v6, uncompressed) tag walker and AVM1 disassembler, for
reading ActionScript in LeapFrog BIOS/cartridge movies (research).

avm1.py IMAGE list                      list SWFs (offset, size, names found)
avm1.py IMAGE dump OFFSET [FILTER]      disassemble every action block in the SWF at OFFSET
                                         (FILTER: only blocks mentioning this string)
"""
import struct, sys, re

NAMES = {0x04:'NextFrame',0x05:'PrevFrame',0x06:'Play',0x07:'Stop',0x08:'ToggleQuality',0x09:'StopSounds',
0x0A:'Add',0x0B:'Subtract',0x0C:'Multiply',0x0D:'Divide',0x0E:'Equals',0x0F:'Less',0x10:'And',0x11:'Or',0x12:'Not',
0x13:'StringEquals',0x14:'StringLength',0x15:'StringExtract',0x17:'Pop',0x18:'ToInteger',0x1C:'GetVariable',
0x1D:'SetVariable',0x20:'SetTarget2',0x21:'StringAdd',0x22:'GetProperty',0x23:'SetProperty',0x24:'CloneSprite',
0x25:'RemoveSprite',0x26:'Trace',0x27:'StartDrag',0x28:'EndDrag',0x29:'StringLess',0x2A:'Throw',0x2B:'CastOp',
0x2C:'ImplementsOp',0x30:'RandomNumber',0x31:'MBStringLength',0x32:'CharToAscii',0x33:'AsciiToChar',0x34:'GetTime',
0x35:'MBStringExtract',0x36:'MBCharToAscii',0x37:'MBAsciiToChar',0x3A:'Delete',0x3B:'Delete2',0x3C:'DefineLocal',
0x3D:'CallFunction',0x3E:'Return',0x3F:'Modulo',0x40:'NewObject',0x41:'DefineLocal2',0x42:'InitArray',
0x43:'InitObject',0x44:'TypeOf',0x45:'TargetPath',0x46:'Enumerate',0x47:'Add2',0x48:'Less2',0x49:'Equals2',
0x4A:'ToNumber',0x4B:'ToString',0x4C:'PushDuplicate',0x4D:'StackSwap',0x4E:'GetMember',0x4F:'SetMember',
0x50:'Increment',0x51:'Decrement',0x52:'CallMethod',0x53:'NewMethod',0x54:'InstanceOf',0x55:'Enumerate2',
0x60:'BitAnd',0x61:'BitOr',0x62:'BitXor',0x63:'BitLShift',0x64:'BitRShift',0x65:'BitURShift',0x66:'StrictEquals',
0x67:'Greater',0x68:'StringGreater',0x69:'Extends',0x81:'GotoFrame',0x83:'GetURL',0x87:'StoreRegister',
0x88:'ConstantPool',0x8A:'WaitForFrame',0x8B:'SetTarget',0x8C:'GotoLabel',0x8D:'WaitForFrame2',0x8E:'DefineFunction2',
0x8F:'Try',0x94:'With',0x96:'Push',0x99:'Jump',0x9A:'GetURL2',0x9B:'DefineFunction',0x9D:'If',0x9E:'Call',0x9F:'GotoFrame2'}

def cstr(b, i):
    j = b.index(b'\0', i)
    return b[i:j].decode('latin-1'), j + 1

def disasm(b, start, end, pool, out, indent=''):
    i = start
    while i < end:
        op = b[i]; at = i; i += 1
        if op == 0:
            out.append(f'{indent}{at:06x}: End'); continue
        ln = 0; arg = ''
        if op >= 0x80:
            ln = struct.unpack_from('<H', b, i)[0]; i += 2
        body = b[i:i+ln]
        name = NAMES.get(op, f'op{op:02x}')
        if op == 0x88:
            n = struct.unpack_from('<H', body, 0)[0]; k = 2; pool[:] = []
            for _ in range(n):
                s, k = cstr(body, k); pool.append(s)
            arg = f'{n} strings'
        elif op == 0x96:
            k = 0; vals = []
            while k < ln:
                t = body[k]; k += 1
                if t == 0: s, k2 = cstr(body, k); vals.append(repr(s)); k = k2
                elif t == 1: vals.append(str(struct.unpack_from('<f', body, k)[0])); k += 4
                elif t == 2: vals.append('null')
                elif t == 3: vals.append('undefined')
                elif t == 4: vals.append(f'r{body[k]}'); k += 1
                elif t == 5: vals.append(str(bool(body[k]))); k += 1
                elif t == 6: hi, lo = struct.unpack_from('<II', body, k); vals.append(str(struct.unpack('<d', struct.pack('<II', lo, hi))[0])); k += 8
                elif t == 7: vals.append(str(struct.unpack_from('<i', body, k)[0])); k += 4
                elif t == 8: vals.append(repr(pool[body[k]]) if body[k] < len(pool) else f'c{body[k]}'); k += 1
                elif t == 9: c = struct.unpack_from('<H', body, k)[0]; vals.append(repr(pool[c]) if c < len(pool) else f'c{c}'); k += 2
                else: vals.append(f'?type{t}'); break
            arg = ', '.join(vals)
        elif op in (0x99, 0x9D):
            off = struct.unpack_from('<h', body, 0)[0]; arg = f'-> {i+ln+off:06x}'
        elif op == 0x9B:
            fn, k = cstr(body, 0); n = struct.unpack_from('<H', body, k)[0]; k += 2; ps = []
            for _ in range(n):
                p, k = cstr(body, k); ps.append(p)
            size = struct.unpack_from('<H', body, k)[0]
            out.append(f'{indent}{at:06x}: DefineFunction {fn}({", ".join(ps)})  [{size} bytes]')
            i += ln
            disasm(b, i, i + size, pool, out, indent + '    ')
            i += size; continue
        elif op == 0x87: arg = f'r{body[0]}'
        elif op in (0x8C,): arg = repr(cstr(body, 0)[0])
        elif op == 0x83:
            u, k = cstr(body, 0); t, _ = cstr(body, k); arg = f'{u!r}, {t!r}'
        elif op == 0x81: arg = str(struct.unpack_from('<H', body, 0)[0])
        elif op == 0x9F: arg = f'flags {body[0]:#x}'
        elif op == 0x9A: arg = f'method {body[0]:#x}'
        elif ln: arg = body.hex()
        out.append(f'{indent}{at:06x}: {name} {arg}')
        i += ln

def tags(b, start, end):
    i = start
    while i < end:
        code_len = struct.unpack_from('<H', b, i)[0]; i += 2
        code, ln = code_len >> 6, code_len & 0x3F
        if ln == 0x3F:
            ln = struct.unpack_from('<I', b, i)[0]; i += 4
        yield code, i, ln
        i += ln
        if code == 0: return

def action_blocks(b, start, end, path='root'):
    for code, i, ln in tags(b, start, end):
        if code == 12:  # DoAction
            yield path + '/DoAction', i, i + ln
        elif code == 59:  # DoInitAction
            yield path + f'/DoInitAction(sprite {struct.unpack_from("<H", b, i)[0]})', i + 2, i + ln
        elif code == 39:  # DefineSprite: id, frame count, tags
            sid = struct.unpack_from('<H', b, i)[0]
            yield from action_blocks(b, i + 4, i + ln, path + f'/sprite{sid}')
        elif code == 34:  # DefineButton2: button actions
            bid = struct.unpack_from('<H', b, i)[0]; k = i + 3
            off = struct.unpack_from('<H', b, k)[0]
            if off:
                k += off
                while True:
                    cond_size = struct.unpack_from('<H', b, k)[0]
                    cond = struct.unpack_from('<H', b, k + 2)[0]
                    stop = k + cond_size if cond_size else i + ln
                    yield path + f'/button{bid}(cond {cond:#06x})', k + 4, stop
                    if not cond_size: break
                    k += cond_size
        elif code == 26:  # PlaceObject2 with clip actions
            flags = b[i]
            if flags & 0x80:
                yield path + '/PlaceObject2-clipactions(raw)', i, i + ln

def swf_header_end(b, o):
    nbits = b[o + 8] >> 3
    rect_bytes = (5 + 4 * nbits + 7) // 8
    return o + 8 + rect_bytes + 4

def find_swfs(b):
    for m in re.finditer(b'FWS', b):
        o = m.start(); v = b[o + 3]
        if 4 <= v <= 8:
            ln = struct.unpack_from('<I', b, o + 4)[0]
            if 100 < ln <= len(b) - o:
                yield o, ln, v

if __name__ == '__main__':
    b = open(sys.argv[1], 'rb').read()
    if sys.argv[2] == 'list':
        want = sys.argv[3:] if len(sys.argv) > 3 else []
        for o, ln, v in find_swfs(b):
            seg = b[o:o + ln]
            hit = [w for w in want if w.encode() in seg]
            if not want or hit:
                print(f'{o:#08x} v{v} {ln:8} {hit}')
    else:
        o = int(sys.argv[3], 16); flt = sys.argv[4] if len(sys.argv) > 4 else None
        ln = struct.unpack_from('<I', b, o + 4)[0]
        for path, s, e in action_blocks(b, swf_header_end(b, o), o + ln):
            if path.endswith('(raw)'): continue
            if flt and flt.encode() not in b[s:e]: continue
            out = []
            try:
                disasm(b, s, e, [], out)
            except Exception as ex:
                out.append(f'!! {ex}')
            print(f'===== {path} [{s:#x}..{e:#x}]'); print('\n'.join(out))
