import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'decode_maze', Path(__file__).resolve().parents[2] / 'scripts/sg1000/decode_maze.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MazeTests(unittest.TestCase):
    def test_runs_and_row_boundaries(self):
        # Five runs of four and one run of two, repeated for all 27 rows.
        row = bytes([0xc1] * 5 + [0x42])
        tiles, used = module.decode(row * 27)
        self.assertEqual(tiles, (bytes([1] * 20 + [2] * 2)) * 27)
        self.assertEqual(used, len(row) * 27)

    def test_truncated_and_crossing(self):
        with self.assertRaisesRegex(ValueError, 'truncated'):
            module.decode(b'')
        with self.assertRaisesRegex(ValueError, 'crosses row'):
            module.decode(bytes([0xc1] * 6))


if __name__ == '__main__':
    unittest.main()
