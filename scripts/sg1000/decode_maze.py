#!/usr/bin/env python3
"""Decode the v1.0 NES maze RLE asset into its 27 rows of 22 tile IDs.

This is the logical NES layout, not an SG-1000 screen: the TMS9918 Graphics II
screen has only 24 tile rows, so the port still needs a layout/rendering plan.
"""
import argparse
from pathlib import Path


def decode(data):
    rows = []
    offset = 0
    for row in range(27):
        tiles = bytearray()
        while len(tiles) < 22:
            if offset == len(data):
                raise ValueError(f'truncated maze at row {row}')
            token = data[offset]
            offset += 1
            run = (token >> 6) + 1
            if len(tiles) + run > 22:
                raise ValueError(f'run crosses row boundary at row {row}')
            tiles.extend([token & 0x3f] * run)
        rows.append(bytes(tiles))
    return b''.join(rows), offset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='extracted maze.rle')
    parser.add_argument('output', type=Path, help='decoded 594-byte tile map')
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        tiles, used = decode(raw)
        if used != len(raw):
            raise ValueError(f'{len(raw) - used} trailing bytes after maze')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(tiles)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
