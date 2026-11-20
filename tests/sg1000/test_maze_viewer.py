"""Boot the diagnostic ROM in a Z80 emulator with a minimal TMS9918 model."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import z80

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'scripts/sg1000'))
from build_maze_viewer import assets_from_rom, build, title_assets
from decode_maze import decode


class VDP:
    def __init__(self):
        self.ram = bytearray(16384)
        self.registers = [0] * 8
        self.latch = None
        self.address = 0
        self.pad = 255

    def output(self, port, value):
        if port & 255 == 191:
            if self.latch is None:
                self.latch = value
            else:
                if value & 128:
                    self.registers[value & 7] = self.latch
                else:
                    self.address = ((value & 63) << 8 | self.latch) & 16383
                self.latch = None
        elif port & 255 == 190:
            self.ram[self.address] = value
            self.address = (self.address + 1) & 16383

    def input(self, port):
        if port & 255 == 191:
            self.latch = None
            return 128
        return self.pad


class ViewerTests(unittest.TestCase):
    def test_reject_unrecognized_rom(self):
        with self.assertRaisesRegex(ValueError, 'verified'):
            assets_from_rom(bytes(24592))

    def test_uploaded_rom_boots_with_real_maze(self):
        path = ROOT / 'pacman.nes'
        if not path.is_file():
            self.skipTest('no local NES ROM')
        try:
            maze, chr_data, logo, palette, _ = assets_from_rom(path.read_bytes())
        except ValueError:
            self.skipTest('local ROM is not a supported revision')
        expected, used = decode(maze)
        self.assertEqual(used, len(maze))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'real.sg'
            build(maze, chr_data, path, logo=logo, title_palette=palette)
            rom = path.read_bytes()
        cpu, vdp = z80.Z80Machine(), VDP()
        cpu.set_memory_block(0, rom)
        cpu.set_input_callback(vdp.input)
        cpu.set_output_callback(vdp.output)
        for _ in range(60):
            cpu.ticks_to_stop = 1000000
            cpu.run()
        patterns, colors, names = title_assets(chr_data, logo, palette)
        self.assertEqual(vdp.ram[0:6144], patterns)
        self.assertEqual(vdp.ram[8192:14336], colors)
        self.assertEqual(vdp.ram[6144:6912], names)
        vdp.pad = 0xef  # fire 1 starts the maze viewer
        for _ in range(60):
            cpu.ticks_to_stop = 1000000
            cpu.run()
        vdp.pad = 0xff
        for row in range(24):
            self.assertEqual(vdp.ram[6144 + row * 32:6144 + row * 32 + 22],
                             expected[row * 22:(row + 1) * 22])
        # HUD font is white, not maze blue; tunnel blanks stay black.
        for bank in range(3):
            color_base = 8192 + bank * 2048
            self.assertIn(0xf1, vdp.ram[color_base + ord('H') * 8:color_base + (ord('H') + 1) * 8])
            self.assertEqual(vdp.ram[color_base + 4 * 8:color_base + 5 * 8], bytes([0x11] * 8))

    def test_rom_boot_and_scrolling(self):
        # Unique tile value per row lets us detect camera scroll.
        maze = bytes(token for row in range(27)
                     for token in ([192 + row] * 5 + [64 + row]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.sg'
            # Nonzero CHR makes the blank-tile override observable.
            logo = bytes(range(138))
            palette = bytes([0x0f, 0x20, 0x0f, 0x06, 0x0f, 0x26, 0x20, 0x27,
                             0x0f, 0x06, 0x0f, 0x26, 0x0f, 0x06, 0x20, 0x26])
            build(maze, bytes([255]) * 8192, path, logo=logo, title_palette=palette)
            rom = path.read_bytes()
        self.assertEqual(len(rom), 49152)
        cpu, vdp = z80.Z80Machine(), VDP()
        cpu.set_memory_block(0, rom)
        cpu.set_input_callback(vdp.input)
        cpu.set_output_callback(vdp.output)
        for _ in range(60):
            cpu.ticks_to_stop = 1000000
            cpu.run()
        self.assertEqual(vdp.registers, [2, 192, 6, 255, 3, 54, 7, 1])
        _, _, title_names = title_assets(bytes([255]) * 8192, logo, palette)
        self.assertEqual(vdp.ram[6144:6912], title_names)
        vdp.pad = 0xef  # fire 1
        for _ in range(60):
            cpu.ticks_to_stop = 1000000
            cpu.run()
        vdp.pad = 0xff
        self.assertEqual(vdp.ram[6912], 208)
        # The margin/maze blank tile must render black in all three banks,
        # regardless of the NES CHR pixels or the generic palette mapping.
        for bank in range(3):
            offset = bank * 2048 + 0x2d * 8
            self.assertEqual(vdp.ram[offset:offset + 8], bytes(8))
            self.assertEqual(vdp.ram[8192 + offset:8192 + offset + 8], bytes([0x11] * 8))
        self.assertEqual(vdp.registers[7] & 15, 1)  # black VDP backdrop
        self.assertEqual(vdp.ram[6144 + 2 * 32 + 22:6144 + 2 * 32 + 25], b'1UP')
        self.assertEqual(vdp.ram[6144 + 6 * 32 + 22:6144 + 6 * 32 + 32], b'HIGH SCORE')
        for row in range(24):
            self.assertEqual(vdp.ram[6144 + row * 32:6144 + row * 32 + 22],
                             bytes([row]) * 22)
        vdp.pad = 0xfd  # down
        for _ in range(70):
            cpu.ticks_to_stop = 1000000
            cpu.run()
        self.assertEqual(cpu.memory[0xc260], 3)
        for row in range(24):
            self.assertEqual(vdp.ram[6144 + row * 32:6144 + row * 32 + 22],
                             bytes([row + 3]) * 22)
        self.assertEqual(vdp.ram[6144 + 6 * 32 + 22:6144 + 6 * 32 + 32], b'HIGH SCORE')
        vdp.pad = 0xfe  # up
        for _ in range(70):
            cpu.ticks_to_stop = 1000000
            cpu.run()
        self.assertEqual(cpu.memory[0xc260], 0)


if __name__ == '__main__':
    unittest.main()
