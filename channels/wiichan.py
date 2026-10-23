"""Build Wii Menu forwarder channels (WADs) around the forwarder in this repository.

A channel WAD has three contents: 0 = banner (IMET + U8 archive with icon.bin, banner.bin, sound.bin),
1 = the nandloader, 2 = the forwarder DOL. The TMD, ticket and nandloader are taken from a template
forwarder WAD (any working IOS58/AHBPROT forwarder channel); the forwarder DOL's config block decides
which app it starts and with which argument.

Lessons from real hardware:
- The Wii Menu runs out of memory when one page holds several channels with a disc's animated icon:
  light_game_icon() replaces the icon with one small CMPR texture (~10 KB) and keeps the disc banner.
- The Wii Menu looks up icon.brlyt / banner.brlyt case-sensitively (the Disc Channel does not), so some
  discs' banners need fix_layout_names().
- IMET sizes are the decompressed payload sizes (after the IMD5 header), as in Nintendo's banners.
"""
import os, struct

import libWiiPy
from PIL import Image, ImageDraw, ImageFont

from wiibnr import u8_parse, u8_build, imd5_unwrap, imd5_wrap

FONT_CANDIDATES = ['C:/Windows/Fonts/segoeuib.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                   '/Library/Fonts/Arial Bold.ttf']


def default_font():
    return next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)


# ---------- forwarder and WAD ----------
def patch_forwarder(dol, path, arg1='', arg2=''):
    """Write the target app path and up to two arguments into the forwarder's FWDCFG01 block."""
    d = bytearray(dol)
    i = d.find(b'FWDCFG01')
    assert i > 0 and d.count(b'FWDCFG01') == 1, 'not a forwarder built from this repository'
    p, a, b = path.encode(), arg1.encode(), arg2.encode()
    assert len(p) < 120 and len(a) < 64 and len(b) < 64
    d[i + 8:i + 128] = p.ljust(120, b'\0')
    d[i + 128:i + 192] = a.ljust(64, b'\0')
    d[i + 192:i + 256] = b.ljust(64, b'\0')
    return bytes(d)


def forwarder_config(dol):
    i = dol.find(b'FWDCFG01')
    return (dol[i + 8:i + 128].split(b'\0')[0].decode(), dol[i + 128:i + 192].split(b'\0')[0].decode(),
            dol[i + 192:i + 256].split(b'\0')[0].decode())


def build_wad(template_wad, title_id4, banner_c0, dol):
    t = libWiiPy.title.Title()
    t.load_wad(template_wad)
    t.set_content(banner_c0, 0)
    t.set_content(dol, 2)
    t.set_title_id('00010001' + title_id4.encode().hex())
    t.fakesign()
    return t.dump_wad()


def retarget_wad(wad, path, arg1=None):
    """Same channel (title ID, banner), new forwarder target; e.g. switch a loader's channels to WiiFlow."""
    t = libWiiPy.title.Title()
    t.load_wad(wad)
    dol = t.get_content_by_index(2)
    old_path, old_arg, _ = forwarder_config(dol)
    t.set_content(patch_forwarder(dol, path, old_arg if arg1 is None else arg1), 2)
    t.fakesign()
    return t.dump_wad()


# ---------- banners ----------
LAYOUT_NAMES = {'arc/blyt/icon.brlyt', 'arc/anim/icon.brlan', 'arc/blyt/banner.brlyt', 'arc/anim/banner.brlan'}


def _imet_with_sizes(imet600, outer):
    hdr = libWiiPy.archive.u8.IMETHeader()
    hdr.load(imet600)
    hdr.sizes = [len(imd5_unwrap(outer['meta/icon.bin'])), len(imd5_unwrap(outer['meta/banner.bin'])),
                 len(outer['meta/sound.bin']) - 0x20]
    return hdr


def fix_layout_names(bnr):
    """Return the disc banner with layout/animation file names in the case the Wii Menu expects."""
    outer = u8_parse(bnr[0x600:])
    changed = False
    for part in ('meta/icon.bin', 'meta/banner.bin'):
        inner = u8_parse(imd5_unwrap(outer[part]))
        renamed = {}
        for k, v in inner.items():
            want = k.lower() if k.lower() in LAYOUT_NAMES else k
            renamed[want] = v
            changed |= want != k
        if renamed.keys() != inner.keys():
            outer[part] = imd5_wrap(u8_build(renamed))
    if not changed:
        return bnr
    return _imet_with_sizes(bnr[:0x600], outer).dump() + u8_build(outer)


def gradient(w, h, c1, c2):
    img = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(c1[k] * (1 - t) + c2[k] * t) for k in range(3)) + (255,))
    return img


def light_game_icon(wadder_c0, cover_png, name, font=None):
    """icon.bin built on the WADder Base 1 template: game cover + short name, one CMPR texture."""
    font = font or default_font()
    inner = u8_parse(imd5_unwrap(u8_parse(wadder_c0[0x640:])['meta/icon.bin']))
    bg = gradient(170, 96, (245, 245, 250), (200, 210, 225))
    cover = Image.open(cover_png).convert('RGBA')
    scale = min(66 / cover.width, 92 / cover.height)
    cover = cover.resize((max(1, int(cover.width * scale)), max(1, int(cover.height * scale))), Image.LANCZOS)
    bg.alpha_composite(cover, (4, (96 - cover.height) // 2))
    d = ImageDraw.Draw(bg)
    words, lines_, cur = name.split(), [], ''
    f = ImageFont.truetype(font, 15)
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= 92:
            cur = t
        else:
            lines_.append(cur)
            cur = w
    lines_.append(cur)
    y = (96 - len(lines_) * 18) // 2
    for ln in lines_:
        d.text((74, y), ln, font=f, fill=(30, 35, 50, 255))
        y += 18
    inner['arc/timg/IconBack.tpl'] = make_tpl(bg.resize((176, 96)), 14)
    inner['arc/timg/WadderMainSmall.tpl'] = make_tpl(Image.new('RGBA', (4, 4), (0, 0, 0, 0)), 5)
    return imd5_wrap(u8_build(inner))


def channel_banner_from_disc(bnr, tag, light_icon=None):
    """Content 0 from a disc's opening.bnr; optionally swap in a light icon.bin."""
    assert bnr[0x40:0x44] == b'IMET' and bnr[0x600:0x604] == b'U\xaa8-', 'not an opening.bnr'
    bnr = fix_layout_names(bnr)
    if light_icon:  # the animated disc banner is kept, only the (heavy) icon is replaced
        outer = u8_parse(bnr[0x600:])
        outer['meta/icon.bin'] = light_icon
        bnr = _imet_with_sizes(bnr[:0x600], outer).dump() + u8_build(outer)
    return tag.encode().ljust(0x40, b'\0')[:0x40] + bnr


# ---------- textures ----------
def rgb5a3_encode(img, w, h):
    img = img.convert('RGBA').resize((w, h), Image.LANCZOS)
    px = img.load()
    out = bytearray()
    for by in range(0, (h + 3) // 4 * 4, 4):
        for bx in range(0, (w + 3) // 4 * 4, 4):
            for y in range(by, by + 4):
                for x in range(bx, bx + 4):
                    r, g, b, a = px[x, y] if x < w and y < h else (0, 0, 0, 0)
                    if a >= 0xE0:
                        v = 0x8000 | (r >> 3) << 10 | (g >> 3) << 5 | (b >> 3)
                    else:
                        v = (a >> 5) << 12 | (r >> 4) << 8 | (g >> 4) << 4 | (b >> 4)
                    out += struct.pack('>H', v)
    return bytes(out)


def replace_tpl(tpl, img):
    io_ = struct.unpack('>I', tpl[0x0c:0x10])[0]
    h, w, fmt, doff = struct.unpack('>HHII', tpl[io_:io_ + 12])
    assert fmt == 5
    data = rgb5a3_encode(img, w, h)
    assert doff + len(data) == len(tpl), (doff, len(data), len(tpl))
    return tpl[:doff] + data


def _rgb565(c):
    return (c[0] >> 3) << 11 | (c[1] >> 2) << 5 | (c[2] >> 3)


def _dxt1_block(px):
    """One 4x4 GX CMPR sub-block (DXT1, big-endian, opaque) from 16 RGB tuples."""
    lum = [p[0] * 3 + p[1] * 6 + p[2] for p in px]
    hi, lo = px[lum.index(max(lum))], px[lum.index(min(lum))]
    c0, c1 = _rgb565(hi), _rgb565(lo)
    if c0 == c1:
        return struct.pack('>HHI', c0, c1, 0)
    if c0 < c1:
        c0, c1, hi, lo = c1, c0, lo, hi
    pal = [hi, lo, tuple((2 * a + b) // 3 for a, b in zip(hi, lo)), tuple((a + 2 * b) // 3 for a, b in zip(hi, lo))]
    bits = 0
    for p in px:
        best = min(range(4), key=lambda k: sum((p[i] - pal[k][i]) ** 2 for i in range(3)))
        bits = bits << 2 | best
    return struct.pack('>HHI', c0, c1, bits)


def cmpr_encode(img):
    img = img.convert('RGB')
    w, h = img.size
    px = img.load()
    out = bytearray()
    for ty in range(0, (h + 7) // 8 * 8, 8):
        for tx in range(0, (w + 7) // 8 * 8, 8):
            for sy, sx in ((0, 0), (0, 4), (4, 0), (4, 4)):
                blk = [px[min(tx + sx + x, w - 1), min(ty + sy + y, h - 1)] for y in range(4) for x in range(4)]
                out += _dxt1_block(blk)
    return bytes(out)


def make_tpl(img, fmt):
    """Single-image TPL; fmt 14 = CMPR (opaque), 5 = RGB5A3."""
    w, h = img.size
    data = cmpr_encode(img) if fmt == 14 else rgb5a3_encode(img, w, h)
    # same layout as Nintendo's/WADder's TPLs: table at 0x0C, image header at 0x14, data at 0x40
    hdr = struct.pack('>III', 0x0020AF30, 1, 0x0C) + struct.pack('>II', 0x14, 0)
    img_hdr = struct.pack('>HHIIIIIIfBBBB', h, w, fmt, 0x40, 0, 0, 1, 1, 0.0, 0, 0, 0, 0)
    body = hdr + img_hdr
    return body + b'\0' * (0x40 - len(body)) + data


def text_center(img, text, size, y, color=(255, 255, 255, 255), font=None):
    font = font or default_font()
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(font, size)
    while d.textlength(text, font=f) > img.width * 0.9 and size > 8:
        size -= 2
        f = ImageFont.truetype(font, size)
    w = d.textlength(text, font=f)
    d.text(((img.width - w) / 2, y), text, font=f, fill=color)


def logo_image(logo_png, text, w, h, font=None):
    """Main picture: the app's icon.png if given, otherwise the name as text."""
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    if logo_png and os.path.exists(logo_png):
        ic = Image.open(logo_png).convert('RGBA')
        scale = min(w / ic.width, h / ic.height)
        ic = ic.resize((max(1, int(ic.width * scale)), max(1, int(ic.height * scale))), Image.LANCZOS)
        img.alpha_composite(ic, ((w - ic.width) // 2, (h - ic.height) // 2))
    else:
        text_center(img, text, int(h * 0.42), int(h * 0.25), font=font)
    return img


def app_banner(wadder_c0, name, subtitle, colors, logo_png, tag, font=None):
    """Banner + icon for an app channel (emulator, tool) on the WADder Base 1 template: gradient,
    subtitle, name and the app's icon. The channel name in the Wii Menu is the subtitle."""
    outer = u8_parse(wadder_c0[0x640:])
    new_outer = dict(outer)
    for part, back, main, (bw, bh), (mw, mh) in [
            ('meta/banner.bin', 'arc/timg/BannerBack.tpl', 'arc/timg/WadderMain.tpl', (832, 456), (242, 142)),
            ('meta/icon.bin', 'arc/timg/IconBack.tpl', 'arc/timg/WadderMainSmall.tpl', (170, 96), (98, 58))]:
        inner = u8_parse(imd5_unwrap(outer[part]))
        bg = gradient(bw, bh, *colors)
        if part == 'meta/banner.bin':
            text_center(bg, subtitle, 64, 40, font=font)
            text_center(bg, name, 40, bh - 100, (230, 230, 230, 255), font=font)
        inner[back] = replace_tpl(inner[back], bg)
        inner[main] = replace_tpl(inner[main], logo_image(logo_png, name, mw, mh, font=font))
        new_outer[part] = imd5_wrap(u8_build(inner))
    hdr = _imet_with_sizes(wadder_c0[0x40:0x640], new_outer)
    hdr.channel_names = [subtitle] * 10
    return tag.encode().ljust(0x40, b'\0') + hdr.dump() + u8_build(new_outer)
