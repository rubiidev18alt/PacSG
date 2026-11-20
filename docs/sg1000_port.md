# SG-1000 port work (incomplete)

There is **no playable game cartridge** yet. A 48 KiB diagnostic cartridge
that displays the original maze can be built, but it is not Pac-Man. The NES source is
6502 code and cannot run on the SG-1000 Z80. The current port work consists of:

* `src/sg1000/turn_candidates.asm`, a Z80 translation of the NES ghost turn
  candidate routine, tested in a Z80 emulator against the original algorithm.
* `src/sg1000/maze.asm`, the original 27-by-22 RLE decoder translated to
  Z80, writing a RAM tile map rather than the NES PPU.
* `src/sg1000/score.asm`, the six-digit decimal score addition portion of the
  NES scoring code. This does not include HUD updates, high scores or extra
  lives. Both routines are tested by executing assembled Z80 code.
* `scripts/sg1000/convert_chr.py`, which converts raw NES CHR tiles into
  TMS9918 Graphics II pattern and color bytes using an explicitly supplied
  four-color mapping. It rejects rows using more than two mapped colors unless
  `--lossy` is requested; the latter maps discarded colors to the most common
  color. Color 0 on the TMS9918 is transparent/backdrop, not an opaque color.
  The resulting files are not a ready-to-upload screen: NES palette selection,
  tile bank placement and sprite conversion must be handled separately.
* `src/sg1000/maze_viewer.asm` and `scripts/sg1000/build_maze_viewer.py`
  build a 48 KiB SG-1000 diagnostic ROM. It displays a 24-row window of the
  NES maze and scrolls with joystick 1 up/down. The fixed color mapping is
  approximate and can lose colors; there are no actors or gameplay. The ROM
  has been boot-tested in a Z80 emulator with a minimal VDP model, not on real
  hardware or in a full SG-1000 emulator.
* `scripts/sg1000/decode_maze.py`, which decodes the original compressed 27 by
  22 tile NES maze asset. The SG-1000's 32 by 24 tile display cannot show this
  map unchanged; adapting the layout is still necessary.

No original asset is included. Run `make split` with the original v1.0 ROM and
Retrolarium Kit to obtain the inputs. For example:

```
python3 scripts/sg1000/decode_maze.py assets/generated/maze/maze.rle build/sg1000/maze.bin
python3 scripts/sg1000/convert_chr.py assets/generated/chr/pacman.chr build/sg1000/chr --palette 1 4 15 10
```

The example palette is only a mapping example, not the game's palette. The CHR
contains multiple NES palettes, so converting the whole file with one mapping
will not reproduce its colors. The converter will fail if any tile row has
more than two colors; `--lossy` allows inspection at the cost of fidelity.

Run the tests with Python 3 and the two pinned test dependencies:

```
python3 -m venv .venv
.venv/bin/pip install -r scripts/sg1000/requirements-test.txt
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m unittest discover -s tests/sg1000 -v
```

The rest of the game, sound, input, VDP renderer, memory layout and a 48 KiB
ROM build and emulator/hardware validation remain to be done.

## Diagnostic cartridge

Once assets are extracted and `pyz80` is on PATH, run:

```
make sg1000-maze-viewer
```

This writes `build/sg1000/maze-viewer.sg`, a raw 49,152-byte ROM, padded with
`FF`. It verifies the Japan v1.0 maze and CHR hashes. It is a maze viewer,
**not a playable port**. Its tile colors are a lossy approximation; the NES
uses palette attributes that are not represented in this diagnostic.
