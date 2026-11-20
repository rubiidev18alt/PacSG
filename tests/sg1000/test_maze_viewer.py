"""Boot the diagnostic ROM in a Z80 emulator with a minimal TMS9918 model."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import z80

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'scripts/sg1000'))
from build_maze_viewer import build


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
    def test_rom_boot_and_scrolling(self):
        # Unique tile value per row lets us detect camera scroll.
        maze = bytes(token for row in range(27)
                     for token in ([192 + row] * 5 + [64 + row]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.sg'
            build(maze, bytes(8192), path)
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
        self.assertEqual(vdp.ram[6912], 208)
        for row in range(24):
            self.assertEqual(vdp.ram[6144 + row * 32 + 5:6144 + row * 32 + 27],
                             bytes([row]) * 22)
        vdp.pad = 0xfd  # down
        for _ in range(70):
            cpu.ticks_to_stop = 1000000
            cpu.run()
        self.assertEqual(cpu.memory[0xc260], 3)
        for row in range(24):
            self.assertEqual(vdp.ram[6144 + row * 32 + 5:6144 + row * 32 + 27],
                             bytes([row + 3]) * 22)
        vdp.pad = 0xfe  # up
        for _ in range(70):
            cpu.ticks_to_stop = 1000000
            cpu.run()
        self.assertEqual(cpu.memory[0xc260], 0)


if __name__ == '__main__':
    unittest.main()
