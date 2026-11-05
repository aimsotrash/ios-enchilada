#!/usr/bin/env python3
"""Byte offsets of the MSS firmware files inside the modem_a FAT image (xnu 0260 mss_fw[]).

  python3 -I tools/mss-fw-table.py backup/modem-fw/modem_a.img backup/modem-fw/modem_a/image

The kernel reads each file straight from the modem_a partition (UFS LUN 4) at the offset printed
here, so a file must lie in the image as one contiguous byte run. That is checked the direct way:
the whole file is found, byte for byte, at a 4 KiB-aligned offset of the image (a fragmented
file is not found and the tool fails). Prints C initializers { name, offset, size, crc32 }; the
crc32 is zlib's, the same as libkern crc32(0, ...). Nothing is written; the firmware never
leaves the laptop.
"""
import mmap
import os
import struct
import sys
import zlib

ALIGN = 4096          # FAT16 here: 4096-byte sectors, 4 per cluster; data area sector aligned


def wanted(image_dir):
    mdt = open(os.path.join(image_dir, 'modem.mdt'), 'rb').read()
    phoff, = struct.unpack_from('<I', mdt, 28)
    phnum, = struct.unpack_from('<H', mdt, 44)
    names = ['mba.mbn', 'modem.mdt']
    for i in range(phnum):
        p_type, _, _, _, filesz = struct.unpack_from('<5I', mdt, phoff + 32 * i)
        if p_type == 1 and filesz:               # PT_LOAD with bytes: modem.bNN exists
            names.append('modem.b%02d' % i)
    return names


def find(img, data):
    start = 0
    while True:
        at = img.find(data[:512], start)
        if at < 0:
            return -1
        if at % ALIGN == 0 and img[at:at + len(data)] == data:
            return at
        start = at + 1


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], 'rb') as f:
        img = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    rows = []
    for name in wanted(sys.argv[2]):
        data = open(os.path.join(sys.argv[2], name), 'rb').read()
        at = find(img, data)
        if at < 0:
            sys.exit('%s: not one contiguous run in the image' % name)
        rows.append((name, at, len(data), zlib.crc32(data)))
    for name, at, size, crc in rows:
        print('\t{ "%s", %#x, %#x, %#010x },' % (name, at, size, crc))


if __name__ == '__main__':
    main()
