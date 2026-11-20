"""Run the Z80 score accumulator on decimal carry and wrap cases."""
import random
import subprocess
import tempfile
import unittest
from pathlib import Path
import z80

ROOT = Path(__file__).resolve().parents[2]


class ScoreZ80Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'score.bin'
            subprocess.run(['pyz80', '--obj=' + str(output),
                            str(ROOT / 'src/sg1000/score.asm')],
                           check=True, capture_output=True)
            cls.code = output.read_bytes()

    def test_add_and_clear(self):
        rng = random.Random(123)
        cases = [(999999, 1), (0, 0), (999999, 999999), (9999, 1)]
        cases += [(rng.randrange(1000000), rng.randrange(1000000)) for _ in range(500)]
        def digits(n):
            return bytes(int(c) for c in f'{n:06d}'[::-1])
        for score, pending in cases:
            cpu = z80.Z80Machine()
            cpu.set_memory_block(0, self.code)
            cpu.set_memory_block(0xc100, digits(score) + b'\x55')
            cpu.set_memory_block(0xc200, digits(pending) + b'\x55')
            cpu.set_memory_block(0xff00, b'\x00\x40')
            cpu.sp, cpu.hl, cpu.de = 0xff00, 0xc100, 0xc200
            cpu.set_breakpoint(0x4000)
            cpu.ticks_to_stop = 10000
            cpu.run()
            self.assertEqual(cpu.pc, 0x4000)
            self.assertEqual(bytes(cpu.memory[0xc100:0xc106]), digits((score + pending) % 1000000))
            self.assertEqual(bytes(cpu.memory[0xc200:0xc206]), bytes(6))
            self.assertEqual((cpu.memory[0xc106], cpu.memory[0xc206]), (0x55, 0x55))


if __name__ == '__main__':
    unittest.main()
