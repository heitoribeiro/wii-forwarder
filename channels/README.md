# Channel tools

Python 3 tools that turn this repository's forwarder into Wii Menu channels (WAD files), plus a
validator to run before installing them. Used to build 36 game channels and several app channels that
were installed and tested on a real Wii (System Menu 4.3U).

| File | Purpose |
|---|---|
| `make_channel.py` | `game` (disc banner + light icon), `app` (gradient banner with an app icon) and `retarget` (same channel, new target app) |
| `validate_wads.py` | checks a folder of WADs: title IDs, TMD, hashes, IMET/IMD5, layouts, textures, forwarder target |
| `wiichan.py` | the library behind both: forwarder config block, WAD assembly, banners, CMPR/RGB5A3 textures |
| `wiibnr.py` | U8 archives, IMD5 and LZ77 for banners |

Requirements: `pip install libWiiPy Pillow`.

You supply (not included, they are not ours to redistribute):
- a **template forwarder WAD** with IOS58 and AHB access (the USB Loader GX "UNEO" forwarder works);
  its TMD, ticket and nandloader are reused, the title ID is changed and the WAD is fakesigned;
- the **forwarder `boot.dol`** built by this repository's GitHub Action;
- the **WADder "Base 1" banner** (content 0 of a WADder-made channel) for icons and app banners;
- for game channels, the disc's **`opening.bnr`** (`wit extract GAME.wbfs out --files +/files/opening.bnr`)
  and a front **cover** (e.g. from GameTDB).

## Examples

```
python make_channel.py game --template fwd.wad --forwarder boot.dol --wadder wadder1.c0 ^
    --title-id UG08 --target /apps/wiiflow/boot.dol --arg RMCE01 ^
    --bnr opening.bnr --cover RMCE01.png --name "Mario Kart Wii" -o "Mario Kart Wii.wad"

python make_channel.py retarget old_channel.wad --target /apps/wiiflow/boot.dol -o new_channel.wad

python validate_wads.py my_wads --template fwd.wad
```

From Git Bash, prefix commands with `MSYS_NO_PATHCONV=1`: otherwise `/apps/...` becomes
`C:/Program Files/Git/apps/...`, and such a channel boots to a black screen. `make_channel.py` refuses
that, and `validate_wads.py` reports it.

## What we learned on hardware

- **Light icons.** A page of channels that keep the disc's animated icon made the Wii Menu freeze when
  scrolling (out of memory). `game` therefore replaces only the icon with a single small CMPR texture
  (cover + name, about 10 KB) and keeps the disc's animated banner. `--keep-disc-icon` turns that off.
- **Lower-case layout names.** The Wii Menu looks up `icon.brlyt`/`banner.brlyt` case-sensitively, the
  Disc Channel does not, so some discs ship `Icon.brlyt` and only freeze as a channel. They are renamed.
- **IMET sizes** are the payload sizes after the IMD5 header, decompressed, as in Nintendo's banners.
- **Which loader the channel starts matters.** WiiFlow Lite and USB Loader GX both boot a game directly
  when given its ID as argument. For Mario Kart Wii online, only WiiFlow worked on our console (USB Loader
  GX hung at the friend-server login); see the ftpii-br repository's `docs/NOTES.md`.
- Re-installing a WAD with the same title ID replaces the channel in place (same slot, no duplicate).
