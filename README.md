# Wii forwarder (config-block edition)

Based on FIX94's Wii DOL forwarder with meta.xml support (zlib-style license, see `source/main.c`).

Altered: the target path and up to two extra arguments are read from a patchable
config block (`FWDCFG01` marker) instead of being hardcoded, so a single `boot.dol`
can be reused for many channels (emulators, or USB Loader GX game IDs). NTFS/EXT2
support was removed (FAT only).

## Channel tools

[`channels/`](channels/README.md) has the Python tools that turn this forwarder into Wii Menu channels
(game channels with the disc banner and a light icon, app channels, retargeting existing channels) and a
validator to run before installing them on a real Wii.
