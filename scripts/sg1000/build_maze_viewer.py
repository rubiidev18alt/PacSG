#!/usr/bin/env python3
"""Build the 48 KiB SG-1000 Pac-Man movement prototype.

This prototype is not a complete Pac-Man port. It deliberately requires the user's
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
    'adb4d7d7d28c89ca177aad231e0fdad992c0fbfb': (11400, 687, 933, 'Japan v1.0'),
    'e7d818e128593109b5c480497a050facc0744f1b': (11516, 822, 1103, 'USA Namco'),
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
    offset, logo_offset, palette_offset, revision = ROMS[digest]
    maze = data[offset:offset + 416]
    chr_data = data[16400:24592]
    if hashlib.sha1(maze).hexdigest() != MAZE_SHA1 or hashlib.sha1(chr_data).hexdigest() not in CHR_SHA1:
        raise ValueError('ROM asset hashes do not match manifest')
    logo = data[logo_offset:logo_offset + 138]
    palette = data[palette_offset:palette_offset + 16]
    if (hashlib.sha1(logo).hexdigest() != '42099a7bf62e02a54e70705d6823cc308900ecea'
            or hashlib.sha1(palette).hexdigest() != 'ec25cd088056307b15869ede32e09480ed07142a'):
        raise ValueError('ROM title asset hashes do not match manifest')
    return maze, chr_data, logo, palette, revision


def table(label, data):
    lines = [label + ':']
    for offset in range(0, len(data), 16):
        lines.append('    defb ' + ','.join(map(str, data[offset:offset + 16])))
    return '\n'.join(lines) + '\n'


# Title attribute bytes from sub_upload_title_attribute_table. These map each
# 2x2-tile quadrant to an NES palette at the logo's original PPU coordinates.
TITLE_ATTRIBUTES = bytes([
    0x80, 0xa0, 0xa0, 0xa0, 0xa0, 0xa0, 0xa0, 0,
    0, 0x66, 0x55, 0x55, 0x55, 0x55, 0xdd, 0,
    8, 0x0a, 0x0a, 0x0a, 0x0a, 0x0a, 0x0a, 0,
])
# Closest TMS9918 colors to the four NES colors in this title palette.
TITLE_NES_TO_TMS = {0x0f: 1, 0x20: 15, 0x06: 6, 0x26: 9, 0x27: 11}


def title_assets(chr_data, logo, nes_palette):
    """Build independent Graphics II banks for a 24-row NES-logo title.

    Different NES palette attributes can apply to the same tile. Deduplicate
    converted pattern/color pairs per 8-row TMS bank, not by NES tile ID.
    """
    if len(logo) != 138 or len(nes_palette) != 16:
        raise ValueError('title requires the 138-byte logo and 16-byte palette')
    try:
        palettes = [[TITLE_NES_TO_TMS[c] for c in nes_palette[i:i + 4]]
                    for i in range(0, 16, 4)]
    except KeyError as exc:
        raise ValueError(f'unsupported NES title color {exc.args[0]:02x}') from exc
    # Blank is explicitly black: palette index 3 is not universally blank.
    cells = [[None for _ in range(32)] for _ in range(24)]
    for y in range(6):
        for x in range(23):
            ox, oy = x + 5, y + 7  # original NES logo location
            attr = TITLE_ATTRIBUTES[(oy // 4 - 1) * 8 + ox // 4]
            shift = ((oy // 2) % 2) * 4 + ((ox // 2) % 2) * 2
            cells[y + 4][x + 5] = (logo[y * 23 + x], (attr >> shift) & 3)
    for row, text in [(14, '1 PLAYER'), (16, 'PRESS BUTTON TO START'),
                      (19, 'UNOFFICIAL FAN PORT,'), (20, 'NOT LICENSED BY')]:
        start = (32 - len(text)) // 2
        for x, character in enumerate(text):
            if character != ' ':
                cells[row][start + x] = (256 if character == ',' else ord(character), 0)
    # NES title logo tiles spell "namco" followed by a trademark emblem.
    # Use the wordmark alone, with no trailing emblem or added T.
    for x in range(8):
        cells[22][12 + x] = (0x23 + x, 1)
    banks_pattern, banks_color, names = bytearray(), bytearray(), bytearray()
    for bank in range(3):
        patterns = bytearray(2048)
        colors = bytearray([0x11] * 2048)
        unique = {(bytes(8), bytes([0x11] * 8)): 0}
        for row in cells[bank * 8:bank * 8 + 8]:
            for cell in row:
                if cell is None:
                    names.append(0)
                    continue
                tile, pal = cell
                if tile == 256:  # comma absent from the NES title font
                    p = bytes([0, 0, 0, 0, 0, 0x18, 0x18, 0x10])
                    c = bytes([0x11] * 5 + [0xf1] * 3)
                else:
                    data = chr_data[tile * 16:(tile + 1) * 16]
                    if tile == 0x2a:  # last wordmark tile: remove emblem at x>=60
                        data = bytes(value & 0xf0 for value in data)
                    p, c, _ = convert(data, palettes[pal], True)
                key = (p, c)
                if key not in unique:
                    index = len(unique)
                    if index >= 256:
                        raise ValueError('title graphics exceed a TMS pattern bank')
                    unique[key] = index
                    patterns[index * 8:(index + 1) * 8] = p
                    colors[index * 8:(index + 1) * 8] = c
                names.append(unique[key])
        banks_pattern.extend(patterns)
        banks_color.extend(colors)
    return bytes(banks_pattern), bytes(banks_color), bytes(names)


# NES sprite composition frames 01..09 from tbl_actor_sprite_tiles and
# tbl_actor_sprite_attrs: closed, then two frames per NES direction
# (up, left, down, right). Each quad is 8x8, in NES OAM order TL,TR,BL,BR.
PACMAN_FRAMES = (
    ((0, 0, 0, 0), (0x00, 0x40, 0x80, 0xc0)),
    ((4, 4, 3, 3), (0x80, 0xc0, 0x80, 0xc0)),
    ((8, 8, 7, 7), (0x80, 0xc0, 0x80, 0xc0)),
    ((2, 1, 2, 1), (0x00, 0x00, 0x80, 0x80)),
    ((6, 5, 6, 5), (0x00, 0x00, 0x80, 0x80)),
    ((3, 3, 4, 4), (0x00, 0x40, 0x00, 0x40)),
    ((7, 7, 8, 8), (0x00, 0x40, 0x00, 0x40)),
    ((1, 2, 1, 2), (0x40, 0x40, 0xc0, 0xc0)),
    ((5, 6, 5, 6), (0x40, 0x40, 0xc0, 0xc0)),
)


def pacman_sprite_patterns(chr_data):
    """Rebuild NES Pac-Man's 16x16 frames as 1-bit TMS sprite masks."""
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    result = bytearray()
    for tiles, attrs in PACMAN_FRAMES:
        quads = []
        for tile, attr in zip(tiles, attrs):
            data = chr_data[4096 + tile * 16:4096 + (tile + 1) * 16]
            rows = [data[y] | data[y + 8] for y in range(8)]
            if attr & 0x80:
                rows.reverse()
            if attr & 0x40:
                rows = [int(f'{value:08b}'[::-1], 2) for value in rows]
            quads.append(bytes(rows))
        # TMS9918 16x16 sprite pattern order is TL, BL, TR, BR.
        for index in (0, 2, 1, 3):
            result.extend(quads[index])
    return bytes(result)


# Normal frames 0A..11 and frightened frames 1E..1F from the NES OAM tables.
GHOST_FRAMES = (
    ((0x18, 0x18, 0x19, 0x19), (0, 0x40, 0, 0x40)),
    ((0x18, 0x18, 0x1a, 0x1a), (0, 0x40, 0, 0x40)),
    ((0x1b, 0x1c, 0x1d, 0x1f), (0, 0, 0, 0)),
    ((0x1b, 0x1c, 0x1e, 0x20), (0, 0, 0, 0)),
    ((0x21, 0x21, 0x22, 0x22), (0, 0x40, 0, 0x40)),
    ((0x21, 0x21, 0x23, 0x23), (0, 0x40, 0, 0x40)),
    ((0x1c, 0x1b, 0x1f, 0x1d), (0x40, 0x40, 0x40, 0x40)),
    ((0x1c, 0x1b, 0x20, 0x1e), (0x40, 0x40, 0x40, 0x40)),
    ((0x24, 0x24, 0x25, 0x25), (0, 0x40, 0, 0x40)),
    ((0x24, 0x24, 0x26, 0x26), (0, 0x40, 0, 0x40)),
)


def ghost_sprite_patterns(chr_data):
    """NES ghost body masks; eye pixels are transparent on the 1-color VDP."""
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    result = bytearray()
    for frame, (tiles, attrs) in enumerate(GHOST_FRAMES):
        quads = []
        for tile, attr in zip(tiles, attrs):
            data = chr_data[4096 + tile * 16:4096 + (tile + 1) * 16]
            # Normal body is NES color 3; frightened body is NES color 1.
            rows = [data[y] & (data[y + 8] if frame < 8 else ~data[y + 8])
                    for y in range(8)]
            if attr & 0x80:
                rows.reverse()
            if attr & 0x40:
                rows = [int(f'{value:08b}'[::-1], 2) for value in rows]
            quads.append(bytes(rows))
        for index in (0, 2, 1, 3):
            result.extend(quads[index])
    return bytes(result)


def build(maze, chr_data, output, assembler='pyz80', *, logo, title_palette):
    _, used = decode(maze)
    if used != len(maze):
        raise ValueError('maze stream has trailing bytes')
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    # Graphics II supports two colors per row. This fixed palette is a rough
    # preview only: NES palettes are selected per attribute block, not per tile.
    patterns, colors, reduced = convert(chr_data[:4096], [1, 4, 15, 15], True)
    # In the NES maze, tile $2D is used as the blank surrounding tile. Its
    # CHR pixels are all palette index 3, which becomes black through the
    # original NES attribute palette. The fixed preview mapping makes those
    # pixels white, so give this particular tile an explicit black definition.
    patterns, colors = bytearray(patterns), bytearray(colors)
    patterns[0x2d * 8:0x2e * 8] = bytes(8)
    colors[0x2d * 8:0x2e * 8] = bytes([0x11] * 8)  # TMS color 1 = black
    # NES maze edge/tunnel tiles use the same index for black fills that the
    # global preview palette maps to white. Keep their blue outlines and map
    # the fill to black. HUD glyphs use a separate white-on-black mapping.
    for tile in (0x04, 0x05, 0x06, 0x21, 0x22):
        for row in range(tile * 8, tile * 8 + 8):
            fg, bg = colors[row] >> 4, colors[row] & 15
            colors[row] = ((1 if fg == 15 else fg) << 4) | (1 if bg == 15 else bg)
    for tile in list(range(0x30, 0x5b)) + list(range(0xb0, 0xbc)):
        for row in range(tile * 8, tile * 8 + 8):
            fg, bg = colors[row] >> 4, colors[row] & 15
            colors[row] = ((15 if fg == 4 else fg) << 4) | (15 if bg == 4 else bg)
    # NES life icon quadrants use index 3: render them Pac-Man yellow.
    for tile in range(0x3c, 0x40):
        for row in range(tile * 8, tile * 8 + 8):
            fg, bg = colors[row] >> 4, colors[row] & 15
            colors[row] = ((11 if fg == 15 else fg) << 4) | (11 if bg == 15 else bg)
    title_patterns, title_colors, title_names = title_assets(chr_data, logo, title_palette)
    with tempfile.TemporaryDirectory() as tmp:
        asm = Path(tmp) / 'viewer.asm'
        binary = Path(tmp) / 'viewer.bin'
        asm.write_text((ROOT / 'src/sg1000/maze_viewer.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/maze.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/player.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/game.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/ghosts.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/sound.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/score.asm').read_text() + '\n' +
                       table('maze_data', maze) + table('pattern_data', patterns) +
                       table('color_data', colors) +
                       table('title_pattern_data', title_patterns) +
                       table('title_color_data', title_colors) +
                       table('title_name_data', title_names) +
                       table('pacman_sprite_data', pacman_sprite_patterns(chr_data) +
                             ghost_sprite_patterns(chr_data)))
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
    parser.add_argument('--logo', type=Path, default=ROOT / 'assets/generated/title/logo-tiles.bin')
    parser.add_argument('--title-palette', type=Path, default=ROOT / 'assets/generated/palettes/title-background.bin')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/sg1000/maze-viewer.sg')
    parser.add_argument('--assembler', default='pyz80')
    args = parser.parse_args()
    try:
        if args.rom:
            maze, chr_data, logo, title_palette, revision = assets_from_rom(args.rom.read_bytes())
            print(f'Using {revision} assets.')
        else:
            maze = args.maze.read_bytes()
            chr_data = args.chr.read_bytes()
            logo = args.logo.read_bytes()
            title_palette = args.title_palette.read_bytes()
            if (hashlib.sha1(logo).hexdigest() != '42099a7bf62e02a54e70705d6823cc308900ecea'
                    or hashlib.sha1(title_palette).hexdigest() != 'ec25cd088056307b15869ede32e09480ed07142a'):
                raise ValueError('title assets do not match the verified ROM')
            if hashlib.sha1(maze).hexdigest() != MAZE_SHA1:
                raise ValueError('maze asset does not match the verified maze')
            if hashlib.sha1(chr_data).hexdigest() not in CHR_SHA1:
                raise ValueError('CHR asset does not match Japan v1.0 or USA Namco')
        if not shutil.which(args.assembler):
            raise ValueError('pyz80 assembler not found; install scripts/sg1000/requirements-test.txt')
        reduced = build(maze, chr_data, args.output, args.assembler, logo=logo, title_palette=title_palette)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(f'Built prototype {args.output} (49152 bytes; {reduced} reduced color rows).')


if __name__ == '__main__':
    main()
