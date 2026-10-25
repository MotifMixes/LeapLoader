import re, sys
# usage: bstrings.py <file> <regex> [minlen]
data = open(sys.argv[1], 'rb').read()
pat = re.compile(sys.argv[2], re.I)
n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
for m in re.finditer(rb'[\x20-\x7e\t]{%d,}' % n, data):
    s = m.group().decode('ascii')
    if pat.search(s):
        print(f'{0x40000000 + m.start():08x}  {s[:200]}')
