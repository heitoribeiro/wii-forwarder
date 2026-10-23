"""Make Wii Menu forwarder channels.

  game     channel for a game: the disc's own animated banner (opening.bnr) with a light icon
           (cover + short name), forwarder pointing to a loader with the game ID as argument
  app      channel for an app (emulator, tool): gradient banner with the app's icon
  retarget same channel, new forwarder target (e.g. move game channels from USB Loader GX to WiiFlow)

Inputs you provide (not included here): a template forwarder WAD (IOS58 + AHB access, e.g. the USB
Loader GX "UNEO" forwarder) for TMD/ticket/nandloader, this repo's forwarder boot.dol, and for icons and
app banners the banner content of the "WADder Base 1" template (content 0, saved as a file).

Examples
  python make_channel.py game --template fwd.wad --forwarder boot.dol --wadder wadder1.c0 \
      --title-id UG08 --target /apps/wiiflow/boot.dol --arg RMCE01 \
      --bnr opening.bnr --cover RMCE01.png --name "Mario Kart Wii" -o mkw.wad
  python make_channel.py app --template fwd.wad --forwarder boot.dol --wadder wadder1.c0 \
      --title-id UEWF --target /apps/wiiflow/boot.dol --name "WiiFlow Lite" \
      --subtitle "Emulators" --logo icon.png -o hub.wad
  python make_channel.py retarget old.wad --target /apps/wiiflow/boot.dol -o new.wad

Title IDs are 4 ASCII characters; pick ones that don't collide with installed channels.
Game IDs make WiiFlow Lite and USB Loader GX boot that game directly.
"""
import argparse, sys

import wiichan as wc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('game', 'app'):
        p = sub.add_parser(name)
        p.add_argument('--template', required=True, help='template forwarder WAD (TMD, ticket, nandloader)')
        p.add_argument('--forwarder', required=True, help="this repository's forwarder boot.dol")
        p.add_argument('--wadder', required=True, help='WADder Base 1 banner content (content 0)')
        p.add_argument('--title-id', required=True)
        p.add_argument('--target', required=True, help='app to start, e.g. /apps/wiiflow/boot.dol')
        p.add_argument('--arg', default='', help='argument for the app, e.g. a game ID')
        p.add_argument('--name', required=True)
        p.add_argument('--font', default=None, help='TrueType font for the texts')
        p.add_argument('-o', '--out', required=True)
        if name == 'game':
            p.add_argument('--bnr', required=True, help="the disc's opening.bnr")
            p.add_argument('--cover', required=True, help='front cover image for the icon')
            p.add_argument('--keep-disc-icon', action='store_true',
                           help="keep the disc's animated icon (heavy: several per page can freeze the Wii Menu)")
        else:
            p.add_argument('--subtitle', required=True, help='big banner text; also the channel name')
            p.add_argument('--logo', default=None, help="the app's icon.png")
            p.add_argument('--colors', default='10,25,45:0,140,120', help='gradient top:bottom as R,G,B:R,G,B')
    p = sub.add_parser('retarget')
    p.add_argument('wad')
    p.add_argument('--target', required=True)
    p.add_argument('--arg', default=None, help='new argument (default: keep the current one)')
    p.add_argument('-o', '--out', required=True)
    a = ap.parse_args()
    # Git Bash on Windows rewrites "/apps/..." into "C:/Program Files/Git/apps/...": such a channel would
    # boot to a black screen, so refuse it (run with MSYS_NO_PATHCONV=1 or from cmd/PowerShell).
    if not a.target.startswith('/'):
        sys.exit(f'--target must be a path on the Wii starting with "/", got {a.target!r}. '
                 'From Git Bash, run with MSYS_NO_PATHCONV=1.')

    if a.cmd == 'retarget':
        wad = wc.retarget_wad(open(a.wad, 'rb').read(), a.target, a.arg)
    else:
        template = open(a.template, 'rb').read()
        dol = wc.patch_forwarder(open(a.forwarder, 'rb').read(), a.target, a.arg)
        wadder = open(a.wadder, 'rb').read()
        if a.cmd == 'game':
            icon = None if a.keep_disc_icon else wc.light_game_icon(wadder, a.cover, a.name, a.font)
            tag = f'fwd_{a.arg}' if a.arg else 'fwd'
            c0 = wc.channel_banner_from_disc(open(a.bnr, 'rb').read(), tag, icon)
        else:
            top, bottom = [tuple(int(x) for x in c.split(',')) for c in a.colors.split(':')]
            folder = a.target.strip('/').split('/')[-2] if a.target.count('/') >= 2 else 'app'
            c0 = wc.app_banner(wadder, a.name, a.subtitle, (top, bottom), a.logo, f'fwd_{folder}', a.font)
        wad = wc.build_wad(template, a.title_id, c0, dol)
    open(a.out, 'wb').write(wad)
    print(a.out, len(wad), 'bytes')


if __name__ == '__main__':
    sys.exit(main())
