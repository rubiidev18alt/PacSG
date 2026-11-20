import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "convert_chr", Path(__file__).resolve().parents[2] / "scripts/sg1000/convert_chr.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ConvertChrTests(unittest.TestCase):
    def test_bitplanes_and_bit_order(self):
        tile = bytes([0x80] + [0] * 7 + [0x40] + [0] * 7)
        patterns, colors, reduced = module.convert(tile, [1, 2, 1, 3])
        self.assertEqual(patterns[0], 0x80)
        self.assertEqual(colors[0], 0x21)
        self.assertEqual(reduced, 0)

    def test_three_colors_fail_or_reduce(self):
        tile = bytes([0x80] + [0] * 7 + [0x40] + [0] * 7)
        with self.assertRaisesRegex(ValueError, 'tile 0, row 0'):
            module.convert(tile, [1, 2, 3, 4])
        patterns, colors, reduced = module.convert(tile, [1, 2, 3, 4], True)
        self.assertEqual((patterns[0], colors[0], reduced), (0x80, 0x21, 1))

    def test_validation(self):
        with self.assertRaises(ValueError):
            module.convert(b'\0', [1, 2, 3, 4])
        with self.assertRaises(ValueError):
            module.convert(bytes(16), [0, 1, 2, 16])

    def test_same_mapped_colors_do_not_require_reduction(self):
        patterns, colors, reduced = module.convert(bytes([255] * 16), [1, 1, 1, 1])
        self.assertEqual(patterns, bytes(8))
        self.assertEqual(colors, bytes([0x11] * 8))
        self.assertEqual(reduced, 0)


if __name__ == '__main__':
    unittest.main()
