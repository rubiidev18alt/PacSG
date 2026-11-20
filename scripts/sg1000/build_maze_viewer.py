#!/usr/bin/env python3
"""Build a 48 KiB SG-1000 ROM for inspecting the extracted NES maze.

This diagnostic is not a Pac-Man port. It deliberately requires the user's
own NES ROM or extracted assets and does not redistribute ROM data.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

from convert_chr import convert
from decode_maze import decode

ROOT = Path(__file__).resolve().parents[2]

# Known ROMs are NROM-128 images. The USA release moves the maze pointer to
# FFF6; its content is identical to the original Japan v1.0 stream.
ROMS = {
    'adb4d7d7d28c89ca177aad231e0fdad992c0fbfb': (11400, 'Japan v1.0'),
    'e7d818e128593109b5c480497a050facc0744f1b': (11516, 'USA Namco'),
}
MAZE_SHA1 = '2076e1963bc3a0665cc0f831c459041fa88aea15'
CHR_SHA1 = {
    '6255630a4d5634f1f03cbfb6266bf8c5f307205e',
    '259b4d580d2fc11d5a61ad85f9fb717489986454',
}


def assets_from_rom(data):
    digest = hashlib.sha1(data).hexdigest()
    if digest not in ROMS or len(data) != 24592:
        raise ValueError('ROM must be a verified Japan v1.0 or USA Namco image')
    offset, revision = ROMS[digest]
    maze = data[offset:offset + 416]
    chr_data = data[16400:24592]
    if hashlib.sha1(maze).hexdigest() != MAZE_SHA1 or hashlib.sha1(chr_data).hexdigest() not in CHR_SHA1:
        raise ValueError('ROM asset hashes do not match manifest')
    return maze, chr_data, revision


def table(label, data):
    lines = [label + ':']
    for offset in range(0, len(data), 16):
        lines.append('    defb ' + ','.join(map(str, data[offset:offset + 16])))
    return '\n'.join(lines) + '\n'


def build(maze, chr_data, output, assembler='pyz80'):
    _, used = decode(maze)
    if used != len(maze):
        raise ValueError('maze stream has trailing bytes')
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    # Graphics II supports two colors per row. This fixed palette is a rough
    # preview only: NES palettes are selected per attribute block, not per tile.
    patterns, colors, reduced = convert(chr_data[:4096], [1, 4, 15, 15], True)
    with tempfile.TemporaryDirectory() as tmp:
        asm = Path(tmp) / 'viewer.asm'
        binary = Path(tmp) / 'viewer.bin'
        asm.write_text((ROOT / 'src/sg1000/maze_viewer.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/maze.asm').read_text() + '\n' +
                       table('maze_data', maze) + table('pattern_data', patterns) +
                       table('color_data', colors))
        subprocess.run([assembler, '--obj=' + str(binary), str(asm)], check=True)
        rom = binary.read_bytes()
    if len(rom) > 49152:
        raise ValueError('cartridge exceeds 48 KiB')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rom + bytes([255]) * (49152 - len(rom)))
    return reduced


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, help='verified Japan v1.0 or USA Namco NES ROM')
    parser.add_argument('--maze', type=Path, default=ROOT / 'assets/generated/maze/maze.rle')
    parser.add_argument('--chr', type=Path, default=ROOT / 'assets/generated/chr/pacman.chr')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sg1000/maze-viewer.sg')
    parser.add_argument('--assembler', default='pyz80')
    args = parser.parse_args()
    try:
        if args.rom:
            maze, chr_data, revision = assets_from_rom(args.rom.read_bytes())
            print(f'Using {revision} assets.')
        else:
            maze = args.maze.read_bytes()
            chr_data = args.chr.read_bytes()
            if hashlib.sha1(maze).hexdigest() != MAZE_SHA1:
                raise ValueError('maze asset does not match the verified maze')
            if hashlib.sha1(chr_data).hexdigest() not in CHR_SHA1:
                raise ValueError('CHR asset does not match Japan v1.0 or USA Namco')
        if not shutil.which(args.assembler):
            raise ValueError('pyz80 assembler not found; install scripts/sg1000/requirements-test.txt')
        reduced = build(maze, chr_data, args.output, args.assembler)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(f'Built diagnostic {args.output} (49152 bytes; {reduced} reduced color rows).')


if __name__ == '__main__':
    main()
