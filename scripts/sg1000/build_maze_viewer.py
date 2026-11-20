#!/usr/bin/env python3
"""Build a 48 KiB SG-1000 ROM for inspecting the extracted NES maze.

This diagnostic is not a Pac-Man port. It deliberately requires the user's
own extracted v1.0 assets and does not redistribute ROM data.
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
    parser.add_argument('--maze', type=Path, default=ROOT / 'assets/generated/maze/maze.rle')
    parser.add_argument('--chr', type=Path, default=ROOT / 'assets/generated/chr/pacman.chr')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sg1000/maze-viewer.sg')
    parser.add_argument('--assembler', default='pyz80')
    args = parser.parse_args()
    try:
        maze = args.maze.read_bytes()
        chr_data = args.chr.read_bytes()
        expected = [('maze', maze, '2076e1963bc3a0665cc0f831c459041fa88aea15'),
                    ('CHR', chr_data, '6255630a4d5634f1f03cbfb6266bf8c5f307205e')]
        for name, data, digest in expected:
            if hashlib.sha1(data).hexdigest() != digest:
                raise ValueError(f'{name} asset does not match Japan v1.0; run make split with your ROM')
        if not shutil.which(args.assembler):
            raise ValueError('pyz80 assembler not found; install scripts/sg1000/requirements-test.txt')
        reduced = build(maze, chr_data, args.output, args.assembler)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(f'Built diagnostic {args.output} (49152 bytes; {reduced} reduced color rows).')


if __name__ == '__main__':
    main()
