# Wii forwarder (config-block edition)

Based on FIX94's Wii DOL forwarder with meta.xml support (zlib-style license, see `source/main.c`).

Altered: the target path and up to two extra arguments are read from a patchable
config block (`FWDCFG01` marker) instead of being hardcoded, so a single `boot.dol`
can be reused for many channels (emulators, or USB Loader GX game IDs). NTFS/EXT2
support was removed (FAT only).
