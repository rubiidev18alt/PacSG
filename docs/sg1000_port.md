# SG-1000 port prototype (incomplete)

The 48 KiB cartridge shows the NES title and maze and lets Pac-Man move and eat
pellets. It is **not a complete Pac-Man port**: there are no ghosts, fruit,
frightened mode, deaths, level completion or intermissions. The high score,
lives and round labels are placeholders. The NES source is 6502 code and
cannot run directly on the SG-1000's Z80.

## Controls and current behavior

Press either fire button at the title, then use joystick 1. Pac-Man continues
in his current direction when the stick is released; he can reverse mid-tile
and turns at tile centers. Near the top or bottom, the camera scrolls the maze
vertically while the HUD stays fixed: the 27-row NES maze is taller than the
TMS9918's 24-row screen. The prototype has
wall checks, tunnel wrapping, pellet removal, 10/50-point scoring and a simple
alternating SN76489 chomp. Power pellets do not trigger frightened mode yet.

Pac-Man's nine 16x16 sprite masks are composed from the original NES CHR tiles
and NES OAM flip attributes; the SG-1000 sprite is single-color yellow. The
movement rate, turning and audio are approximations, **not cycle-accurate NES
behavior**. The title and maze colors are approximate because the TMS9918
supports only two colors per tile row. The prototype has been exercised with a
Z80 emulator and a minimal VDP/PSG model, not on real SG-1000 hardware or in a
full system emulator.

## Build

With `pyz80` on PATH, and either a verified Japan v1.0 or USA Namco ROM in
`pacman.nes`, run:

```
make sg1000-maze-viewer
# Or select another ROM path:
make sg1000-maze-viewer SG1000_ROM=path/to/file.nes
```

This writes `build/sg1000/maze-viewer.sg`, a raw 49,152-byte ROM, padded with
`FF`. The script verifies the ROM and extracted asset hashes. The USA Namco
release uses its regional CHR with the same maze. `roms/maze-viewer.sg` is the
corresponding prebuilt prototype.

Run the tests with Python 3 and the pinned test dependencies:

```
python3 -m venv .venv
.venv/bin/pip install -r scripts/sg1000/requirements-test.txt
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m unittest discover -s tests/sg1000 -v
```

## Source and tools

* `src/sg1000/player.asm` implements the current movement, pellet, score HUD,
  camera, sprite and chomp prototype.
* `src/sg1000/maze_viewer.asm` sets up the TMS9918 title, maze and HUD;
  `scripts/sg1000/build_maze_viewer.py` builds the ROM and converts graphics.
* `src/sg1000/turn_candidates.asm` translates the NES ghost turn-candidate
  routine, but is not yet integrated into the prototype.
* `src/sg1000/maze.asm` translates the original 27-by-22 RLE decoder to Z80;
  it writes a RAM tile map instead of the NES PPU.
* `src/sg1000/score.asm` translates the NES's six-digit decimal addition.
* `scripts/sg1000/decode_maze.py` decodes the extracted NES maze RLE on a host.
* `scripts/sg1000/convert_chr.py` converts NES tiles to TMS9918 Graphics II
  pattern/color bytes using a supplied palette; it can optionally reduce rows
  containing more than two mapped colors. TMS color 0 is backdrop/transparent.

To obtain individual v1.0 assets, run `make split` with the original v1.0 ROM
and Retrolarium Kit. For example:

```
python3 scripts/sg1000/decode_maze.py assets/generated/maze/maze.rle build/sg1000/maze.bin
python3 scripts/sg1000/convert_chr.py assets/generated/chr/pacman.chr build/sg1000/chr --palette 1 4 15 10
```

The example palette is not the game's palette. A single CHR conversion does not
capture NES per-attribute palette selection or sprite color handling.
