"""Assemble and execute the Z80 maze decoder against generated NES RLE."""
import random
import subprocess
import tempfile
import unittest
from pathlib import Path

import z80

ROOT = Path(__file__).resolve().parents[2]


class MazeZ80Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'maze.bin'
            subprocess.run(['pyz80', '--obj=' + str(output),
                            str(ROOT / 'src/sg1000/maze.asm')],
                           check=True, capture_output=True)
            cls.code = output.read_bytes()

    def test_decodes_rows_and_crosses_pages(self):
        rng = random.Random(1729)
        for _ in range(20):
            encoded, expected = bytearray(), bytearray()
            for row in range(27):
                remaining = 22
                while remaining:
                    run = rng.randint(1, min(4, remaining))
                    tile = rng.randrange(64)
                    encoded.append((run - 1) * 64 + tile)
                    expected.extend([tile] * run)
                    remaining -= run
            cpu = z80.Z80Machine()
            cpu.set_memory_block(0, self.code)
            cpu.set_memory_block(0x80f0, encoded)
            cpu.set_memory_block(0xc0f0, bytes([0x55] * 595))
            cpu.set_memory_block(0xff00, bytes([0, 0x40]))
            cpu.sp, cpu.hl, cpu.de = 0xff00, 0x80f0, 0xc0f0
            cpu.set_breakpoint(0x4000)
            cpu.ticks_to_stop = 1000000
            cpu.run()
            self.assertEqual(cpu.pc, 0x4000)
            self.assertEqual(bytes(cpu.memory[0xc0f0:0xc0f0 + 594]), expected)
            self.assertEqual(cpu.memory[0xc0f0 + 594], 0x55)
            self.assertEqual(cpu.hl, 0x80f0 + len(encoded))
            self.assertEqual(cpu.de, 0xc0f0 + 594)


if __name__ == '__main__':
    unittest.main()
