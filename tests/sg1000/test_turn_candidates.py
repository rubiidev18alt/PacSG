"""Execute the actual assembled Z80 routine against the 6502 algorithm."""
import random
import subprocess
import tempfile
import unittest
from pathlib import Path

import z80

ROOT = Path(__file__).resolve().parents[2]


class TurnCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'turn.bin'
            subprocess.run(['pyz80', '--obj=' + str(output),
                            str(ROOT / 'src/sg1000/turn_candidates.asm')],
                           check=True, capture_output=True)
            cls.code = output.read_bytes()

    def run_case(self, tiles, direction, exact, masked):
        cpu = z80.Z80Machine()
        cpu.set_memory_block(0, self.code)
        cpu.set_memory_block(0x8000, bytes(tiles))
        cpu.set_memory_block(0x9000, bytes([0x55] * 5))
        cpu.set_memory_block(0xff00, bytes([0, 0x40]))  # return to 4000h
        cpu.sp, cpu.hl, cpu.ix = 0xff00, 0x8000, 0x9000
        cpu.a, cpu.d, cpu.e = direction, exact, masked
        cpu.set_breakpoint(0x4000)
        cpu.ticks_to_stop = 10000
        cpu.run()
        self.assertEqual(cpu.pc, 0x4000)
        reverse = (direction + 2) & 3
        expected = [i for i, t in enumerate(tiles)
                    if i != reverse and (t == exact or (t & 0xf8) == 0
                                         or (t & 0xf8) == masked)]
        expected += [255] * (4 - len(expected))
        self.assertEqual(bytes(cpu.memory[0x9000:0x9004]), bytes(expected))
        self.assertEqual(cpu.memory[0x9004], 0x55)
        self.assertEqual((cpu.ix, cpu.de), (0x9000, exact * 256 + masked))

    def test_randomized_and_edge_cases(self):
        rng = random.Random(42)
        for direction in range(4):
            for tiles, exact, masked in [([0] * 4, 0x40, 0x48),
                                          ([0xff] * 4, 0x40, 0x48),
                                          ([0x20, 0x27, 0x28, 0x07], 0x27, 0x28)]:
                self.run_case(tiles, direction, exact, masked)
            for _ in range(200):
                self.run_case([rng.randrange(256) for _ in range(4)], direction,
                              rng.randrange(256), rng.randrange(32) * 8)


if __name__ == '__main__':
    unittest.main()
