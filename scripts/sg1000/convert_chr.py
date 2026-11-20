#!/usr/bin/env python3
"""Convert NES planar tiles to TMS9918 Graphics II pattern/color bytes.

The NES palette is selected by the caller: CHR itself contains only 2-bit
indices, not RGB colors or per-tile palette assignments. The TMS9918 permits
only two colors per eight-pixel row; by default conversion fails rather than
silently corrupting rows that need more.
"""
import argparse
from collections import Counter
from pathlib import Path


def convert(data, palette, lossy=False):
    if len(data) % 16:
        raise ValueError("CHR length must be a multiple of 16 bytes")
    if len(palette) != 4 or any(not 0 <= c <= 15 for c in palette):
        raise ValueError("palette must contain four TMS9918 color indices (0..15)")
    patterns, colors, reduced = bytearray(), bytearray(), 0
    for tile in range(len(data) // 16):
        block = data[tile * 16:(tile + 1) * 16]
        for row in range(8):
            pixels = [palette[((block[row] >> bit) & 1) | (((block[row + 8] >> bit) & 1) << 1)]
                      for bit in range(7, -1, -1)]
            counts = Counter(pixels)
            if len(counts) > 2:
                if not lossy:
                    raise ValueError(f"tile {tile}, row {row} uses {len(counts)} colors; "
                                     "Graphics II allows only two (use --lossy to reduce)")
                reduced += 1
            # Most frequent colors survive; numeric color index breaks ties.
            ranked = sorted(counts, key=lambda c: (-counts[c], c))[:2]
            background = ranked[0]
            foreground = ranked[1] if len(ranked) == 2 else background
            pattern = sum((1 << (7 - x)) for x, color in enumerate(pixels)
                          if color == foreground and foreground != background)
            patterns.append(pattern)
            colors.append((foreground << 4) | background)
    return bytes(patterns), bytes(colors), reduced


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chr", type=Path, help="raw NES CHR data, not an iNES ROM")
    parser.add_argument("output", type=Path, help="output prefix for .patterns and .colors")
    parser.add_argument("--palette", nargs=4, type=int, required=True, metavar="COLOR",
                        help="TMS9918 color index for each NES pixel index (0..15)")
    parser.add_argument("--lossy", action="store_true", help="reduce rows with more than two colors")
    args = parser.parse_args()
    try:
        patterns, colors, reduced = convert(args.chr.read_bytes(), args.palette, args.lossy)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Path(str(args.output) + ".patterns").write_bytes(patterns)
    Path(str(args.output) + ".colors").write_bytes(colors)
    print(f"Converted {len(patterns) // 8} tiles; reduced {reduced} rows.")


if __name__ == "__main__":
    main()
