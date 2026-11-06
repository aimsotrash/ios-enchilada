#!/usr/bin/env python3
"""Byte offsets of the MSS firmware files inside the modem_a FAT image (xnu 0260 mss_fw[]).

  python3 -I tools/mss-fw-table.py backup/modem-fw/modem_a.img backup/modem-fw/modem_a/image
  python3 -I tools/mss-fw-table.py --tftp backup/modem-fw/modem_a.img backup/modem-fw/modem_a/image
  python3 -I tools/mss-fw-table.py --adsp backup/modem-fw/modem_a.img backup/modem-fw/modem_a/image

--tftp (xnu 0265 mss_tftp[]): every file the modem may ask the TFTP server for, i.e. all files
under image/ except the PIL images the apps side loads (X.mdt + X.bNN, mba.mbn), as
{ path relative to image/, offset, size }. A zero-length file gets offset 0.

--adsp (xnu 0300 adsp_fw[]): adsp.mdt and the adsp.bNN files of its PT_LOAD segments, in the
mss_fw[] format (no mba.mbn).

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


def wanted(image_dir, pil='modem'):
    mdt = open(os.path.join(image_dir, pil + '.mdt'), 'rb').read()
    phoff, = struct.unpack_from('<I', mdt, 28)
    phnum, = struct.unpack_from('<H', mdt, 44)
    names = (['mba.mbn'] if pil == 'modem' else []) + [pil + '.mdt']
    for i in range(phnum):
        p_type, _, _, _, filesz = struct.unpack_from('<5I', mdt, phoff + 32 * i)
        if p_type == 1 and filesz:               # PT_LOAD with bytes: X.bNN exists
            names.append('%s.b%02d' % (pil, i))
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


def tftp_files(image_dir):
    pil = {f[:-4] for f in os.listdir(image_dir) if f.endswith('.mdt')}
    out = []
    for d, _, files in os.walk(image_dir):
        for f in files:
            base, ext = os.path.splitext(f)
            seg = ext == '.mdt' or (len(ext) == 4 and ext[1] == 'b' and ext[2:].isdigit())
            if d == image_dir and ((base in pil and seg) or f == 'mba.mbn'):
                continue
            out.append(os.path.relpath(os.path.join(d, f), image_dir))
    return sorted(out)


def main():
    tftp = sys.argv[1:2] == ['--tftp']
    pil = 'adsp' if sys.argv[1:2] == ['--adsp'] else 'modem'
    args = sys.argv[2:] if tftp or pil != 'modem' else sys.argv[1:]
    if len(args) != 2:
        sys.exit(__doc__)
    with open(args[0], 'rb') as f:
        img = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    if tftp:
        for name in tftp_files(args[1]):
            data = open(os.path.join(args[1], name), 'rb').read()
            at = find(img, data) if data else 0
            if at < 0:
                sys.exit('%s: not one contiguous run in the image' % name)
            print('\t{ "%s", %#x, %#x },' % (name, at, len(data)))
        return
    rows = []
    for name in wanted(args[1], pil):
        data = open(os.path.join(args[1], name), 'rb').read()
        at = find(img, data)
        if at < 0:
            sys.exit('%s: not one contiguous run in the image' % name)
        rows.append((name, at, len(data), zlib.crc32(data)))
    for name, at, size, crc in rows:
        print('\t{ "%s", %#x, %#x, %#010x },' % (name, at, size, crc))


if __name__ == '__main__':
    main()
