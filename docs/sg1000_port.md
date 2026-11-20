# SG-1000 Pac-Man prototype (incomplete)

The 48 KiB cartridge has the NES-derived title, maze, Pac-Man and four ghosts.
It is **not a complete or cycle-accurate NES port**: intermissions, two-player
mode and the full NES audio engine are not implemented. Returning eyes use a
precomputed shortest route rather than the NES's navigation, and the NES cached
PPU probe pipeline, corner-turn substeps, tunnel wrapping and some collision and
animation details are still simplified. The NES source is 6502 code and cannot
run unchanged on the SG-1000's Z80.

## Controls and current behavior

The title starts on black and scrolls upward into view in eight-pixel steps;
pressing either fire button skips the animation and starts play. The Namco
wordmark is red with a small registered mark at its upper right. The title also
shows “1985” and “UNLICENSED BY NINTENDO NOR SEGA.” Use joystick 1. Pac-Man continues
in his current direction when the stick is released; he can reverse mid-tile
and turns at tile centers. Near the top or bottom, the camera scrolls the maze
while the HUD stays fixed: the 27-row NES maze is taller than the TMS9918's
24-row screen.

The prototype includes walls and tunnel wrapping, dots and energizers,
10/50-point scoring, a frightened timer, flashing frightened ghosts, and
200/400/800/1600-point ghost chains. Eating a ghost briefly freezes the action,
shows its NES-derived point sprite, and then sends it home as eyes. During the
pause all actors, animations, and gameplay timers are frozen. Only the ghost-eaten
sound plays; the returning-eyes wail starts and pellet audio resumes when
the pause ends. While eyes are returning, their wail takes priority over the
frightened-ghost sound. This
intentionally differs from the NES, where previously returning eyes keep moving. Fruit appears at the original pellet thresholds, with the
round-dependent fruit and scores; it uses two extra sprite layers rather than
erasing maze tiles. READY!, PLAYER and ONE use the NES sprite glyphs, drawn as
temporary maze background tiles to avoid the sprite-per-scanline limit; the
underlying map is restored before play. The NES-derived death sequence freezes
at the collision, hides the ghosts, plays the death sound and steps through the
original CHR/OAM frames before deducting a life. The actors then respawn without
resetting dots; losing the last life shows GAME OVER and returns to the title.
Clearing all 192 dots starts the next round with the maze restored. The HUD has
NES-derived score labels and life icons, a working score/high score, a one-time
extra life at 10,000, a numeric round indicator, and an eight-icon stage fruit
history at the NES HUD position, four icons per row. Background tiles avoid the
hardware sprite limit; the spare lives sit below the fruit and the round number
sits above it. The high score is retained
across game overs while the machine stays powered on.

Pac-Man's and the ghosts' 16x16 masks are composed from the original NES CHR
and OAM flip attributes. Each ghost uses separate colored-body and white-eye
sprites (blue and flashing white when frightened). The TMS9918 displays at most
four sprites on one scanline: layering increases dropout, and ghost priority
rotates to distribute the resulting flicker. Pac-Man and ghosts use the NTSC
stage speed fractions and Blinky's stage-specific dot thresholds from the NES
parameter tables. Ghosts use the reconstructed target formulas, turn ordering,
mode timers, frightened countdown and flashing, home bouncing/exiting, and
pellet/time-based release targets. The returning-eyes path and parts of movement/turn handling remain approximations.
Title and maze colors are approximations because each background tile row
supports only two colors.

### Sound channels

The SN76489 channels are assigned independently:

* tones 0 and 1: two-voice NES READY melody;
* tone 0: alternating NES pellet sound streams during play;
* tone 1: looping NES ghost-state streams, selected by returning eyes,
  frightened mode, and the disassembly's pellet-count bands;
* tone 2: NES ghost-eaten, fruit, extra-life, and death streams;
* noise: currently muted.

The note and duration streams are checked against the NES asset manifest and
compiled by `scripts/sg1000/nes_audio.py`. APU timer values are translated to
PSG tone divisors. The original channel arbitration, triangle waveform, pulse
duty, sweep, envelopes and control-register behavior cannot be reproduced
exactly by the SN76489: the port uses fixed PSG volumes, folds event sounds
onto one channel, and approximates sustained notes. Newer event sounds replace
older ones. The original READY and effect streams therefore sound closer but
are not bit-identical NES APU output.

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
* `src/sg1000/ghosts.asm` implements ghost targeting, release, house movement,
  collisions, frightened sprites and sprite-priority rotation.
* `src/sg1000/fruit.asm` manages the bonus fruit, scoring and sprite layers.
* `src/sg1000/death.asm` manages the death freeze, animation and life transition;
  `src/sg1000/ghost_popup.asm` handles the ghost score freeze and popup.
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
