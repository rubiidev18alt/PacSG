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
from nes_audio import STREAMS, psg_events

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
    converted pattern/color pairs globally so rows can move between TMS banks.
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
    # The NES CHR wordmark spells "namco"; keep it without a trailing T or
    # the original emblem and render the lettering red on black. The small
    # registered-trademark symbol sits above the wordmark's right edge.
    for x in range(8):
        cells[22][12 + x] = (0x23 + x, 4)  # special red wordmark palette
    cells[21][20] = (257, 0)  # small circled R, raised at the top right
    names = bytearray()
    patterns = bytearray(2048)
    colors = bytearray([0x11] * 2048)
    unique = {(bytes(8), bytes([0x11] * 8)): 0}
    for bank in range(3):
        for row in cells[bank * 8:bank * 8 + 8]:
            for cell in row:
                if cell is None:
                    names.append(0)
                    continue
                tile, pal = cell
                if tile == 256:  # comma absent from the NES title font
                    p = bytes([0, 0, 0, 0, 0, 0x18, 0x18, 0x10])
                    c = bytes([0x11] * 5 + [0xf1] * 3)
                elif tile == 257:  # 7x7 registered-trademark mark, red on black
                    p = bytes([0x78, 0x84, 0xb4, 0xb4, 0xac, 0x84, 0x78, 0])
                    c = bytes([0x81] * 8)
                else:
                    data = chr_data[tile * 16:(tile + 1) * 16]
                    if tile == 0x2a:  # last wordmark tile: remove emblem at x>=60
                        data = bytes(value & 0xf0 for value in data)
                    palette = [1, 8, 8, 8] if pal == 4 else palettes[pal]
                    p, c, _ = convert(data, palette, True)
                key = (p, c)
                if key not in unique:
                    index = len(unique)
                    if index >= 256:
                        raise ValueError('title graphics exceed a TMS pattern bank')
                    unique[key] = index
                    patterns[index * 8:(index + 1) * 8] = p
                    colors[index * 8:(index + 1) * 8] = c
                names.append(unique[key])
    return bytes(patterns) * 3, bytes(colors) * 3, bytes(names)


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


# NES death frames 12..1D from tbl_actor_sprite_tiles/attrs.
DEATH_FRAMES = (
    ((0x00, 0x00, 0x00, 0x00), (0x00, 0x40, 0x80, 0xc0)),
    ((0x09, 0x09, 0x0a, 0x0a), (0x00, 0x40, 0x00, 0x40)),
    ((0x0b, 0x0b, 0x0c, 0x0c), (0x00, 0x40, 0x00, 0x40)),
    *(((0x4c, 0x4c, tile, tile), (0x00, 0x00, 0x00, 0x40))
      for tile in range(0x0d, 0x14)),
    ((0x14, 0x15, 0x16, 0x17), (0, 0, 0, 0)),
    ((0x4c, 0x4c, 0x4c, 0x4c), (0, 0, 0, 0)),
)


def death_sprite_patterns(chr_data):
    """Compose the NES death OAM frames into 16x16 TMS masks."""
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    out = bytearray()
    for tiles, attrs in DEATH_FRAMES:
        quads = []
        for tile, attr in zip(tiles, attrs):
            data = chr_data[4096 + tile * 16:4096 + (tile + 1) * 16]
            rows = [data[y] | data[y + 8] for y in range(8)]
            if attr & 0x80:
                rows.reverse()
            if attr & 0x40:
                rows = [int(f'{v:08b}'[::-1], 2) for v in rows]
            quads.append(bytes(rows))
        for index in (0, 2, 1, 3):
            out.extend(quads[index])
    return bytes(out)


READY_GLYPHS = (0xc6, 0xc3, 0xc1, 0xba, 0xc7, 0xbb,
                0xb0, 0xb1, 0xb2, 0xb3, 0xb4, 0xb5,
                0xb6, 0xb7, 0xb4)


def ready_text_patterns(chr_data):
    """NES READY!, PLAYER and ONE sprite glyphs adapted as background tiles."""
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    result = bytearray()
    for tile in READY_GLYPHS:
        data = chr_data[4096 + tile * 16:4096 + (tile + 1) * 16]
        result.extend(data[y] | data[y + 8] for y in range(8))
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


def ghost_sprite_patterns(chr_data, *, eyes=False):
    """NES ghost masks, separated into body and eye layers for the TMS VDP."""
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    result = bytearray()
    for frame, (tiles, attrs) in enumerate(GHOST_FRAMES):
        quads = []
        for tile, attr in zip(tiles, attrs):
            data = chr_data[4096 + tile * 16:4096 + (tile + 1) * 16]
            # Normal body = NES color 3 and eyes = 2. Frightened body = 1
            # and its face = 3. Each plane is a separate one-color sprite.
            if eyes:
                rows = [(~data[y] & data[y + 8]) if frame < 8 else
                        (data[y] & data[y + 8]) for y in range(8)]
            else:
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


def fruit_sprite_patterns(chr_data):
    """Two disjoint TMS layers for the eight NES fruit actor frames 24..2B."""
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    result = bytearray()
    for layer in range(2):
        for fruit in range(8):
            tiles = [0x90 + fruit * 4 + n for n in range(4)]
            for quad in (0, 2, 1, 3):  # TMS TL, BL, TR, BR
                start = 4096 + tiles[quad] * 16
                data = chr_data[start:start + 16]
                for y in range(8):
                    lo, hi = data[y], data[y + 8]
                    # NES index 1 versus indices 2/3, both transparent at 0.
                    result.append((lo & ~hi) & 255 if layer == 0 else hi)
    return bytes(result)


# NES ghost score OAM frames 2D, 2F, 32 and 34: 200, 400, 800, 1600.
GHOST_SCORE_FRAMES = (
    (0x32, 0x2f, 0x33, 0x31),
    (0x36, 0x2f, 0x37, 0x31),
    (0x3c, 0x2f, 0x3d, 0x31),
    (0x42, 0x3f, 0x43, 0x41),
)


def ghost_score_sprite_patterns(chr_data):
    """Convert the original score-popup OAM quadrants to TMS sprite masks."""
    if len(chr_data) != 8192:
        raise ValueError('expected 8192 bytes of NES CHR data')
    result = bytearray()
    for tiles in GHOST_SCORE_FRAMES:
        for index in (0, 2, 1, 3):
            start = 4096 + tiles[index] * 16
            tile = chr_data[start:start + 16]
            result.extend(tile[y] | tile[y + 8] for y in range(8))
    return bytes(result)


def eye_routes(maze):
    """Shortest legal exit back to the ghost-house entrance for each tile."""
    from collections import deque
    tiles, _ = decode(maze)
    routes = bytearray([255] * (22 * 27))
    goal = 10 * 22 + 11
    routes[goal] = 254
    queue = deque([goal])
    directions = ((0, -1), (-1, 0), (0, 1), (1, 0))
    while queue:
        tile = queue.popleft()
        x, y = tile % 22, tile // 22
        for direction, (dx, dy) in enumerate(directions):
            nx, ny = x + dx, y + dy
            if y == 13 and nx in (-1, 22):
                nx %= 22
            if not (0 <= nx < 22 and 0 <= ny < 27):
                continue
            neighbor = ny * 22 + nx
            if tiles[neighbor] & 0xf0 or routes[neighbor] != 255:
                continue
            routes[neighbor] = direction ^ 2
            queue.append(neighbor)
    return bytes(routes)


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
    # Text uses background tiles to avoid the TMS9918's four-sprites-per-line
    # limit. These IDs do not occur in the decoded maze or the HUD.
    ready_patterns = ready_text_patterns(chr_data)
    patterns[0xe0 * 8:0xef * 8] = ready_patterns
    colors[0xe0 * 8:0xe6 * 8] = bytes([0xb1] * (6 * 8))  # yellow
    colors[0xe6 * 8:0xef * 8] = bytes([0x71] * (9 * 8))  # cyan
    title_patterns, title_colors, title_names = title_assets(chr_data, logo, title_palette)
    with tempfile.TemporaryDirectory() as tmp:
        asm = Path(tmp) / 'viewer.asm'
        binary = Path(tmp) / 'viewer.bin'
        asm.write_text((ROOT / 'src/sg1000/maze_viewer.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/maze.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/player.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/game.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/death.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/ghosts.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/ghost_popup.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/sound.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/fruit.asm').read_text() + '\n' +
                       (ROOT / 'src/sg1000/score.asm').read_text() + '\n' +
                       ''.join(table(name, psg_events(data)) for name, data in STREAMS.items()) +
                       table('maze_data', maze) + table('ghost_eye_routes', eye_routes(maze)) + table('pattern_data', patterns) +
                       table('color_data', colors) +
                       table('title_pattern_data', title_patterns) +
                       table('title_color_data', title_colors) +
                       table('title_name_data', title_names) +
                       table('pacman_sprite_data', pacman_sprite_patterns(chr_data) +
                             ghost_sprite_patterns(chr_data) +
                             ghost_sprite_patterns(chr_data, eyes=True) +
                             fruit_sprite_patterns(chr_data) +
                             death_sprite_patterns(chr_data) +
                             ghost_score_sprite_patterns(chr_data)))
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
