# SG-1000 Pac-Man prototype (incomplete)

The 48 KiB cartridge has the NES-derived title, maze, Pac-Man and four ghosts.
It is **not a complete or cycle-accurate NES port**: ghost navigation and
release are simplified, eaten ghosts respawn after a delay rather than returning
as eyes, and fruit, intermissions and the NES's level-specific speed/timer
profiles are not implemented. The NES source is 6502 code and cannot run
unchanged on the SG-1000's Z80.

## Controls and current behavior

Press either fire button at the title, then use joystick 1. Pac-Man continues
in his current direction when the stick is released; he can reverse mid-tile
and turns at tile centers. Near the top or bottom, the camera scrolls the maze
while the HUD stays fixed: the 27-row NES maze is taller than the TMS9918's
24-row screen.

The prototype includes walls and tunnel wrapping, dots and energizers,
10/50-point scoring, a frightened timer, flashing frightened ghosts, and
200/400/800/1600-point ghost chains. A ghost hit costs a life and respawns the
actors without resetting the dots; losing the last life returns to the title.
Clearing all 192 dots starts the next round with the maze restored. The HUD has
NES-derived score labels and life icons, a working score/high score, a one-time
extra life at 10,000, and a numeric round indicator. The high score is retained
across game overs while the machine stays powered on.

Pac-Man's and the ghosts' 16x16 masks are composed from the original NES CHR
and OAM flip attributes. SG-1000 sprites have one color, so ghost eye pixels
are transparent rather than white. The TMS9918 displays at most four sprites on
one scanline; ghost priority rotates to share the resulting flicker. Title and
maze colors are approximations because each background tile row supports only
two colors. Movement and audio are approximations, not exact NES behavior.

### Sound channels

The SN76489 channels are assigned independently so a pellet chomp does not cut
off the ghost warble or an event sound:

* tone 0: alternating pellet chomp with a short volume decay;
* tone 1: continuously sweeping ghost/frightened warble;
* tone 2: ghost-eaten, death, and level-clear effects;
* noise: currently muted.

The three event effects share tone 2, so a newer event replaces an earlier event
on that channel. The sounds are original SG-1000 approximations, not the NES
APU streams or a note-for-note transcription.

The prototype has been exercised with a Z80 emulator and a minimal VDP/PSG
model, not on real SG-1000 hardware or in a full system emulator.

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

* `src/sg1000/player.asm` implements Pac-Man movement, pellets, score output,
  camera, sprite and chomp.
* `src/sg1000/ghosts.asm` implements simplified ghost movement, collisions,
  frightened sprites and sprite-priority rotation.
* `src/sg1000/game.asm` manages lives, high score, game over and level reset;
  `src/sg1000/sound.asm` manages the siren and event-sound channels.
* `src/sg1000/maze_viewer.asm` sets up the TMS9918 title, maze and HUD;
  `scripts/sg1000/build_maze_viewer.py` builds the ROM and converts graphics.
* `src/sg1000/turn_candidates.asm` translates the NES ghost turn-candidate
  routine, but is not yet integrated into the simplified ghost logic.
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
