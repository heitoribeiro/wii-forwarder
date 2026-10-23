"""Minimal helpers to read/write Wii channel banners (IMET + U8 + IMD5/LZ77 + TPL)."""
import struct, hashlib
from libWiiPy.archive import lz77

def u8_parse(data):
    assert data[:4] == b'U\xaa8-', data[:4]
    root_off, hdr_size, data_off = struct.unpack('>III', data[4:16])
    n = struct.unpack('>I', data[root_off+8:root_off+12])[0]
    nodes = [struct.unpack('>BxHII', data[root_off+i*12:root_off+i*12+12]) for i in range(n)]
    st = root_off + n*12
    def name(o): return data[st+o:data.index(b'\0', st+o)].decode()
    files, stack = {}, [(n, '')]
    for i in range(1, n):
        while stack and i >= stack[-1][0]: stack.pop()
        typ, noff, a, b = nodes[i]
        path = (stack[-1][1] + '/' if stack and stack[-1][1] else '') + name(noff)
        if typ == 1: stack.append((b, path))
        else: files[path] = data[a:a+b]
    return files

def u8_build(files):
    # build directory tree
    tree = {}
    for p in sorted(files):
        parts = p.split('/'); d = tree
        for x in parts[:-1]: d = d.setdefault(x, {})
        d[parts[-1]] = files[p]
    nodes, names = [], bytearray(b'\0')
    def walk(d, parent):
        for k in sorted(d, key=lambda s: s.lower()):
            noff = len(names); names.extend(k.encode() + b'\0')
            if isinstance(d[k], dict):
                idx = len(nodes); nodes.append(['d', noff, parent, 0]); walk(d[k], idx); nodes[idx][3] = len(nodes)
            else: nodes.append(['f', noff, d[k], 0])
    nodes.append(['d', 0, 0, 0]); walk(tree, 0); nodes[0][3] = len(nodes)
    hdr_size = len(nodes)*12 + len(names)
    data_off = (0x20 + hdr_size + 31) & ~31
    out_nodes, blob = bytearray(), bytearray()
    for typ, noff, a, b in nodes:
        if typ == 'd': out_nodes += struct.pack('>BBHII', 1, noff >> 16, noff & 0xffff, a, b)
        else:
            off = data_off + len(blob)
            out_nodes += struct.pack('>BBHII', 0, noff >> 16, noff & 0xffff, off, len(a)); blob += a
            blob += b'\0' * (-len(blob) % 32)
    head = b'U\xaa8-' + struct.pack('>III', 0x20, hdr_size, data_off) + b'\0'*16
    body = head + out_nodes + names
    return bytes(body + b'\0'*(data_off-len(body)) + blob)

def imd5_unwrap(data):
    if data[:4] == b'IMD5': data = data[0x20:]
    if data[:4] == b'LZ77': data = _lz77_dec(data)
    return data

def _lz77_dec(d):
    # Nintendo LZ77 type 0x10 with "LZ77" magic prefix
    d = d[4:]
    assert d[0] == 0x10
    size = d[1] | d[2] << 8 | d[3] << 16
    out = bytearray(); i = 4
    while len(out) < size:
        flags = d[i]; i += 1
        for b in range(8):
            if len(out) >= size: break
            if flags & (0x80 >> b):
                x = d[i] << 8 | d[i+1]; i += 2
                ln = (x >> 12) + 3; disp = (x & 0xfff) + 1
                for _ in range(ln): out.append(out[-disp])
            else: out.append(d[i]); i += 1
    return bytes(out)

def imd5_wrap(data):
    return b'IMD5' + struct.pack('>I', len(data)) + b'\0'*8 + hashlib.md5(data).digest() + data
