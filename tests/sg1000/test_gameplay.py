"""Exercise gameplay events and independent PSG voices on the assembled ROM."""
from pathlib import Path
import tempfile
import unittest

from test_maze_viewer import ROOT, advance, make_machine
from build_maze_viewer import assets_from_rom, build, ghost_sprite_patterns, title_assets
from convert_chr import convert


class GameplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'pacman.nes'
        if not path.is_file():
            raise unittest.SkipTest('no local NES ROM')
        try:
            maze, cls.chr_data, logo, palette, _ = assets_from_rom(path.read_bytes())
            cls.logo, cls.palette = logo, palette
        except ValueError:
            raise unittest.SkipTest('local ROM is not a supported revision')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'game.sg'
            build(maze, cls.chr_data, output, logo=logo, title_palette=palette)
            cls.rom = output.read_bytes()

    def new_game(self):
        cpu, vdp = make_machine(self.rom)
        advance(cpu, vdp, 60)
        vdp.pad = 0xef
        advance(cpu, vdp, 15)
        vdp.pad = 0xff
        return cpu, vdp

    def test_title_disclaimer_and_wordmark_use_expected_tiles(self):
        patterns, colors, names = title_assets(self.chr_data, self.logo, self.palette)
        def cell(row, column):
            tile = names[row * 32 + column]
            offset = (row // 8) * 2048 + tile * 8
            return patterns[offset:offset + 8], colors[offset:offset + 8]
        for row, text in ((19, 'UNOFFICIAL FAN PORT,'), (20, 'NOT LICENSED BY')):
            left = (32 - len(text)) // 2
            for x, character in enumerate(text):
                if character == ' ':
                    continue
                if character == ',':
                    self.assertEqual(cell(row, left + x)[0], bytes([0, 0, 0, 0, 0, 24, 24, 16]))
                else:
                    bitmap = self.chr_data[ord(character) * 16:(ord(character) + 1) * 16]
                    expected, expected_color, _ = convert(bitmap, [1, 15, 1, 6], True)
                    self.assertEqual(cell(row, left + x), (expected, expected_color))
        for x in range(8):
            tile = 0x23 + x
            bitmap = self.chr_data[tile * 16:(tile + 1) * 16]
            if x == 7:
                bitmap = bytes(value & 0xf0 for value in bitmap)
            p, c, _ = convert(bitmap, [1, 9, 15, 11], True)
            self.assertEqual(cell(22, 12 + x), (p, c))
        self.assertEqual(names[22 * 32 + 20], 0)  # no trailing T/emblem

    def test_ghosts_move_and_psg_voices_are_independent(self):
        cpu, vdp = self.new_game()
        start_y = cpu.memory[0xc291]
        advance(cpu, vdp, 30)
        self.assertNotEqual(cpu.memory[0xc291], start_y)
        self.assertEqual(vdp.ram[14336 + 288:14336 + 608], ghost_sprite_patterns(self.chr_data))
        self.assertEqual(vdp.ram[14336 + 608:14336 + 928], ghost_sprite_patterns(self.chr_data, eyes=True))
        self.assertEqual(vdp.ram[6948], 208)
        # Fire a separate event while Pac-Man consumes a pellet. Within the
        # same window the chomp (0), siren (1), and event (2) all write their
        # own SN76489 volume registers; no channel-1/2 mute is issued.
        for ghost in range(4):
            cpu.memory[0xc290 + ghost * 8 + 3] = 255
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 12
        cpu.memory[0xc264], cpu.memory[0xc261] = 1, 0
        cpu.memory[0xc282], cpu.memory[0xc283] = 20, 1
        start = len(vdp.psg)
        advance(cpu, vdp, 8, ghosts_disabled=True)
        writes = vdp.psg[start:]
        self.assertIn(148, writes)  # chomp channel 0
        self.assertIn(185, writes)  # siren channel 1
        self.assertIn(212, writes)  # event channel 2
        self.assertNotIn(191, writes)  # channel 1 mute
        self.assertNotIn(223, writes)  # channel 2 mute

    def test_four_ghosts_and_rotating_sprite_priority(self):
        cpu, vdp = self.new_game()
        # Park Pac-Man facing a wall, away from all four ghost spawn points.
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 28, 1
        cpu.memory[0xc260], cpu.memory[0xc261] = 0, 0
        for ghost in range(4):
            cpu.memory[0xc290 + ghost * 8 + 3] = 0
        advance(cpu, vdp, 1)
        self.assertEqual([vdp.ram[6919 + 8 * n] & 15 for n in range(4)], [8, 13, 7, 10])
        self.assertEqual([vdp.ram[6923 + 8 * n] & 15 for n in range(4)], [15] * 4)
        for n in range(4):
            self.assertEqual(vdp.ram[6916 + 8*n:6918 + 8*n], vdp.ram[6920 + 8*n:6922 + 8*n])
            self.assertEqual(vdp.ram[6922 + 8*n] - vdp.ram[6918 + 8*n], 40)
        before = [(cpu.memory[0xc290 + n * 8], cpu.memory[0xc291 + n * 8]) for n in range(4)]
        cpu.memory[0xc261] = 8
        advance(cpu, vdp, 5)
        self.assertEqual([vdp.ram[6919 + 8 * n] & 15 for n in range(4)], [13, 7, 10, 8])
        after = [(cpu.memory[0xc290 + n * 8], cpu.memory[0xc291 + n * 8]) for n in range(4)]
        for old, new in zip(before, after):
            self.assertNotEqual(old, new)

    def test_power_pellet_and_ghost_scoring_chain(self):
        cpu, vdp = self.new_game()
        for ghost in range(1, 4):
            cpu.memory[0xc290 + ghost * 8 + 3] = 255
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 28  # power pellet
        cpu.memory[0xc264], cpu.memory[0xc260], cpu.memory[0xc261] = 1, 0, 0
        cpu.memory[0xc290], cpu.memory[0xc291] = 52, 68
        cpu.memory[0xc292], cpu.memory[0xc293] = 1, 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc27f], 165)
        self.assertEqual(cpu.memory[0xc2d4], 1)
        self.assertEqual(cpu.memory[0xc292], 3)  # reversed on energizer
        self.assertEqual(cpu.memory[0xc000 + 3 * 22 + 2], 7)
        self.assertEqual(vdp.ram[6919] & 15, 4)  # blue frightened ghost
        for expected in (250, 650, 1450, 3050):
            cpu.memory[0xc290], cpu.memory[0xc291] = 20, 28
            cpu.memory[0xc292], cpu.memory[0xc293] = 1, 0
            advance(cpu, vdp, 1)
            digits = cpu.memory[0xc270:0xc276]
            score = sum(digit * 10 ** (i + 1) for i, digit in enumerate(digits))
            self.assertEqual(score, expected)
            self.assertGreater(cpu.memory[0xc293], 0)  # ghost waiting to respawn
            self.assertEqual(cpu.memory[0xc27e], 3)
        self.assertEqual(vdp.ram[6390:6397], b'   3050')
        self.assertEqual(cpu.memory[0xc280], 3)  # capped chain index

    def test_mode_timer_reverses_and_pauses_for_frightened(self):
        cpu, vdp = self.new_game()
        for ghost in range(4):
            cpu.memory[0xc290 + ghost * 8 + 3] = 0
            cpu.memory[0xc290 + ghost * 8 + 2] = 1
            cpu.memory[0xc290 + ghost * 8 + 5] = 0
        cpu.memory[0xc2d0], cpu.memory[0xc2d1], cpu.memory[0xc2d2] = 0, 1, 59
        cpu.memory[0xc27f] = 5
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc2d0], 0)
        self.assertEqual(cpu.memory[0xc2d2], 59)
        cpu.memory[0xc27f] = 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc2d0], 1)
        self.assertEqual(cpu.memory[0xc2d1], 20)
        self.assertEqual([cpu.memory[0xc292 + n * 8] for n in range(4)], [3] * 4)

    def test_frightened_long_timer_rollover(self):
        cpu, vdp = self.new_game()
        cpu.memory[0xc27f], cpu.memory[0xc2d4] = 1, 1
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc27f], 255)
        self.assertEqual(cpu.memory[0xc2d4], 0)

    def test_death_lives_and_highscore_persists_after_game_over(self):
        cpu, vdp = self.new_game()
        for ghost in range(1, 4):
            cpu.memory[0xc290 + ghost * 8 + 3] = 255
        # Leave a consumed dot behind to verify that a death does not reset it.
        cpu.memory[0xc000 + 5 * 22 + 2] = 7
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 28, 1
        cpu.memory[0xc261], cpu.memory[0xc27f] = 0, 0
        cpu.memory[0xc290], cpu.memory[0xc291] = 20, 28
        cpu.memory[0xc293] = 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc27e], 2)
        self.assertEqual(vdp.ram[6518:6528], b'READY     ')
        self.assertGreater(cpu.memory[0xc281], 0)
        self.assertEqual(cpu.memory[0xc000 + 5 * 22 + 2], 7)
        self.assertEqual(vdp.ram[6742:6750], bytes([60, 61, 32, 32, 32, 32, 32, 32]))
        # Simulate another hit on the last life and a previously earned high.
        high = bytes([1, 2, 3, 4, 5, 6])
        cpu.set_memory_block(0xc285, high)
        cpu.memory[0xc27e], cpu.memory[0xc281] = 1, 0
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 28, 1
        cpu.memory[0xc261], cpu.memory[0xc27f] = 0, 0
        cpu.memory[0xc290], cpu.memory[0xc291], cpu.memory[0xc293] = 20, 28, 0
        for ghost in range(1, 4):
            cpu.memory[0xc290 + ghost * 8 + 3] = 255
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc27e], 0)
        self.assertEqual(vdp.ram[6518:6528], b'GAME OVER ')
        self.assertEqual(cpu.memory[0xc28c], 1)
        advance(cpu, vdp, 160)  # game over resets to title
        self.assertEqual(vdp.psg[-4:], [159, 191, 223, 255])
        self.assertEqual(bytes(cpu.memory[0xc285:0xc28b]), high)
        vdp.pad = 0xef
        advance(cpu, vdp, 15)
        self.assertEqual(bytes(cpu.memory[0xc285:0xc28b]), high)
        self.assertEqual(vdp.ram[6262:6269], b'6543210')

    def test_high_score_and_one_time_extra_life(self):
        cpu, vdp = self.new_game()
        cpu.set_memory_block(0xc270, bytes([9, 9, 9, 0, 0, 0]))  # 9990
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 12, 1
        cpu.memory[0xc260], cpu.memory[0xc261] = 0, 0
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc27e], 4)
        self.assertEqual(cpu.memory[0xc28b], 1)
        self.assertEqual(vdp.ram[6742:6750], bytes([60, 61, 60, 61, 60, 61, 32, 32]))
        self.assertEqual(vdp.ram[6390:6397], b'  10000')
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 28, 12, 1
        cpu.memory[0xc261] = 0
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc27e], 4)  # no second 1UP
        self.assertEqual(vdp.ram[6262:6269], b'  10010')

    def test_last_pellet_starts_next_level(self):
        cpu, vdp = self.new_game()
        cpu.memory[0xc27c] = 1
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 12, 1
        cpu.memory[0xc260], cpu.memory[0xc261] = 0, 0
        advance(cpu, vdp, 5, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc27d], 2)
        self.assertEqual(cpu.memory[0xc27c], 192)
        self.assertEqual(cpu.memory[0xc000 + 22 + 2], 3)
        self.assertEqual(cpu.memory[0xc27e], 3)
        self.assertEqual(vdp.ram[6390:6397], b'     10')
        self.assertEqual(vdp.ram[6812:6814], b' 2')
        self.assertGreater(cpu.memory[0xc281], 0)
        self.assertEqual(cpu.memory[0xc283], 3)  # level-clear sound
        self.assertEqual(vdp.ram[6518:6528], b'CLEAR     ')
        advance(cpu, vdp, 95, ghosts_disabled=True)
        self.assertEqual(vdp.ram[6518:6528], b'          ')


if __name__ == '__main__':
    unittest.main()
