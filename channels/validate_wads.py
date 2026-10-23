"""Check forwarder channel WADs before installing them on a real Wii.

python validate_wads.py FOLDER [--template template.wad]

Per WAD: unique title ID, channel type, fakesigned, IOS58 + boot index 1 + 3 contents, content hashes,
IMET header MD5 and sizes, IMD5 hashes, layouts present (lower-case names the Wii Menu needs), every
texture a layout references exists and fits its TPL, forwarder target and argument. With --template,
the nandloader must be identical to the template's.
"""
import argparse, glob, hashlib, os, struct, sys

import libWiiPy

from wiibnr import u8_parse, imd5_unwrap
from wiichan import forwarder_config, LAYOUT_NAMES

# GX texture formats: (block width, block height, bits per pixel)
BLOCK = {0: (8, 8, 4), 1: (8, 4, 8), 2: (8, 4, 8), 3: (4, 4, 16), 4: (4, 4, 16), 5: (4, 4, 16), 6: (4, 4, 32),
         8: (8, 8, 4), 9: (8, 4, 8), 10: (4, 4, 16), 14: (8, 8, 4)}


def check_tpl(name, v):
    errs = []
    for i in range(struct.unpack('>I', v[4:8])[0]):
        io_, po = struct.unpack('>II', v[0xc + i * 8:0x14 + i * 8])
        h, w, f, do = struct.unpack('>HHII', v[io_:io_ + 12])
        if f not in BLOCK:
            errs.append(f'{name}: unknown format {f}')
            continue
        bw, bh, bpp = BLOCK[f]
        need = ((w + bw - 1) // bw) * ((h + bh - 1) // bh) * bw * bh * bpp // 8
        if do + need > len(v):
            errs.append(f'{name}: data too short')
        if f in (8, 9, 10) and po == 0:
            errs.append(f'{name}: palette format without palette')
        if not (0 < w <= 1024 and 0 < h <= 1024):
            errs.append(f'{name}: size {w}x{h}')
    return errs


def texture_refs(brlyt):
    i = brlyt.find(b'txl1')
    if i < 0:
        return []
    base, out = i + 12, []
    for k in range(struct.unpack('>H', brlyt[i + 8:i + 10])[0]):
        s = base + struct.unpack('>I', brlyt[base + k * 8:base + k * 8 + 4])[0]
        out.append(brlyt[s:brlyt.index(b'\0', s)].decode())
    return out


def check_part(outer, part):
    errs = []
    u = u8_parse(imd5_unwrap(outer[part]))
    for k, v in u.items():
        if k.endswith('.tpl'):
            errs += check_tpl(k.split('/')[-1], v)
    for lay in [k for k in u if k.endswith('.brlyt')]:
        for r in texture_refs(u[lay]):
            if not any(k.lower().endswith('/timg/' + r.lower()) for k in u):
                errs.append(f'missing texture {r}')
            elif not any(k.endswith('/timg/' + r) for k in u):
                errs.append(f'texture only with different case {r}')
    for k in u:
        if k.lower() in LAYOUT_NAMES and k not in LAYOUT_NAMES:
            errs.append(f'layout name must be lower case: {k}')
    want = 'arc/blyt/icon.brlyt' if part == 'meta/icon.bin' else 'arc/blyt/banner.brlyt'
    if want not in u:
        errs.append(f'missing {want}')
    return errs


def check_wad(path, nandloader=None, seen=None):
    t = libWiiPy.title.Title()
    t.load_wad(open(path, 'rb').read())
    errs = []
    tid = bytes.fromhex(t.tmd.title_id[8:]).decode(errors='replace')
    if seen is not None:
        if tid in seen:
            errs.append('duplicate title ID')
        seen.add(tid)
    if t.tmd.title_id[:8] != '00010001':
        errs.append('not a channel title')
    if not t.get_is_fakesigned():
        errs.append('not fakesigned')
    if t.tmd.boot_index != 1 or t.tmd.ios_tid != '000000010000003a' or t.tmd.num_contents != 3:
        errs.append('unexpected TMD (IOS58, boot index 1, 3 contents)')
    c = [t.get_content_by_index(i) for i in range(3)]  # verifies each content's SHA-1
    if nandloader is not None and c[1] != nandloader:
        errs.append('nandloader differs from template')
    b = c[0]
    if b[0x80:0x84] != b'IMET':
        errs.append('no IMET header')
    h = bytearray(b[0x40:0x640])
    md = bytes(h[0x5f0:])
    h[0x5f0:] = b'\0' * 16
    if hashlib.md5(h).digest() != md:
        errs.append('IMET MD5')
    outer = u8_parse(b[0x640:])
    for k, sz in zip(['meta/icon.bin', 'meta/banner.bin', 'meta/sound.bin'], struct.unpack('>III', b[0x8c:0x98])):
        v = outer.get(k)
        if v is None:
            errs.append('missing ' + k)
            continue
        expected = len(v) - 0x20 if k == 'meta/sound.bin' else len(imd5_unwrap(v))
        if expected != sz:
            errs.append(f'IMET size of {k}')
        if v[:4] == b'IMD5' and hashlib.md5(v[0x20:]).digest() != v[0x10:0x20]:
            errs.append('IMD5 of ' + k)
    for part in ('meta/icon.bin', 'meta/banner.bin'):
        errs += check_part(outer, part)
    target, arg, _ = forwarder_config(c[2])
    if not target.startswith('/'):
        errs.append(f'forwarder target {target!r} is not a Wii path')
    name = b[0x9c + 84:0x9c + 168].decode('utf-16-be', errors='replace').strip('\0')
    return tid, target, arg, name, t.get_title_size_blocks(), errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--template', help='template WAD whose nandloader every channel must use')
    a = ap.parse_args()
    nand = None
    if a.template:
        tt = libWiiPy.title.Title()
        tt.load_wad(open(a.template, 'rb').read())
        nand = tt.get_content_by_index(1)
    ok, seen = True, set()
    for path in sorted(glob.glob(os.path.join(a.folder, '*.wad'))):
        tid, target, arg, name, blocks, errs = check_wad(path, nand, seen)
        ok &= not errs
        print(f"{'OK  ' if not errs else 'FAIL'} {tid} {target:28} {arg:7} {name[:30]:30} {blocks:3} blocks {errs or ''}")
    print('ALL OK' if ok else 'PROBLEMS FOUND')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
