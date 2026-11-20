"""Exercise gameplay events and independent PSG voices on the assembled ROM."""
from pathlib import Path
import tempfile
import unittest

from test_maze_viewer import ROOT, advance, make_machine
from build_maze_viewer import (assets_from_rom, build, death_sprite_patterns,
                               fruit_sprite_patterns, ghost_score_sprite_patterns,
                               ghost_sprite_patterns, pacman_sprite_patterns,
                               ready_text_patterns, title_assets)
from convert_chr import convert
from nes_audio import STREAMS, psg_events


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
        advance(cpu, vdp, 210)
        vdp.pad = 0xef
        advance(cpu, vdp, 15)
        vdp.pad = 0xff
        advance(cpu, vdp, 242)
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
            p, c, _ = convert(bitmap, [1, 8, 8, 8], True)
            self.assertEqual(cell(22, 12 + x), (p, c))
            # Neither foreground nor background uses a color other than red
            # or black, including rows which are entirely one color.
            self.assertTrue(all((v >> 4) in (1, 8) and (v & 15) in (1, 8) for v in c))
        self.assertEqual(cell(21, 20),
                         (bytes([0x78, 0x84, 0xb4, 0xb4, 0xac, 0x84, 0x78, 0]),
                          bytes([0x81] * 8)))
        self.assertEqual(names[22 * 32 + 20], 0)  # no trailing T/emblem

    def test_ghosts_move_and_psg_voices_are_independent(self):
        cpu, vdp = self.new_game()
        start = tuple(cpu.memory[0xc290:0xc292])
        advance(cpu, vdp, 30)
        self.assertNotEqual(tuple(cpu.memory[0xc290:0xc292]), start)
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
        self.assertEqual(cpu.memory[0xc27f], 225)
        self.assertEqual(cpu.memory[0xc2d4], 1)
        self.assertEqual(cpu.memory[0xc292], 3)  # reversed on energizer
        self.assertEqual(cpu.memory[0xc000 + 3 * 22 + 2], 7)
        self.assertEqual(vdp.ram[6919] & 15, 4)  # blue frightened ghost
        for index, expected in enumerate((250, 650, 1450, 3050)):
            cpu.memory[0xc290], cpu.memory[0xc291] = 20, 28
            cpu.memory[0xc292], cpu.memory[0xc293] = 1, 0
            cpu.memory[0xc296] = 0
            advance(cpu, vdp, 1)
            digits = cpu.memory[0xc270:0xc276]
            score = sum(digit * 10 ** (i + 1) for i, digit in enumerate(digits))
            self.assertEqual(score, expected)
            self.assertEqual(cpu.memory[0xc296], 6)  # NES score popup state
            self.assertEqual(vdp.ram[6914], 228 + 4 * index)
            self.assertEqual(cpu.memory[0xc31a], 40 if index == 0 else 38)
            self.assertEqual(cpu.memory[0xc27e], 3)
            advance(cpu, vdp, cpu.memory[0xc31a])
            self.assertEqual(cpu.memory[0xc296], 1)  # returns as eyes
        self.assertEqual(vdp.ram[6390:6397], b'   3050')
        self.assertEqual(cpu.memory[0xc280], 3)  # capped chain index

    def test_ghost_score_popup_freezes_actors_and_gameplay_timers(self):
        cpu, vdp = self.new_game()
        self.assertEqual(vdp.ram[14336 + 1824:14336 + 1952],
                         ghost_score_sprite_patterns(self.chr_data))
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 28, 1
        cpu.memory[0xc260], cpu.memory[0xc261] = 0, 0
        cpu.memory[0xc27f], cpu.memory[0xc2d4] = 100, 0
        cpu.memory[0xc290], cpu.memory[0xc291], cpu.memory[0xc292] = 20, 28, 1
        cpu.memory[0xc293], cpu.memory[0xc295], cpu.memory[0xc296] = 0, 0, 0
        # Returning eyes, active ghosts and all other actors must freeze.
        cpu.memory[0xc298], cpu.memory[0xc299], cpu.memory[0xc29a] = 52, 68, 1
        cpu.memory[0xc29b], cpu.memory[0xc29e] = 0, 1
        cpu.memory[0xc2a0], cpu.memory[0xc2a1] = 132, 68
        cpu.memory[0xc2a3], cpu.memory[0xc2a6] = 0, 0
        cpu.memory[0xc2ab] = 255
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc31a], 40)
        self.assertEqual(cpu.memory[0xc296], 6)
        self.assertEqual((vdp.ram[6912], vdp.ram[6913]), (19, 12))
        self.assertEqual((vdp.ram[6914], vdp.ram[6915] & 15), (228, 7))
        self.assertEqual(vdp.ram[6916], 209)  # captured ghost hidden
        pac = bytes(cpu.memory[0xc262:0xc264])
        other = bytes(cpu.memory[0xc2a0:0xc2a2])
        eyes = bytes(cpu.memory[0xc298:0xc29a])
        frightened = cpu.memory[0xc27f]
        frame_counter = cpu.memory[0xc261]
        release_ticks = bytes(cpu.memory[0xc30c:0xc30e])
        chomp_state = bytes(cpu.memory[0xc2fc:0xc2ff])
        saved_chomp_volume = cpu.memory[0xc31f]
        self.assertEqual(vdp.psg[-4:], [159, 191, 223, 255])
        psg_len = len(vdp.psg)
        display = bytes(vdp.ram)
        ghosts = bytes(cpu.memory[0xc290:0xc2b0])
        advance(cpu, vdp, 39)
        self.assertEqual(cpu.memory[0xc31a], 1)
        self.assertEqual(cpu.memory[0xc296], 6)
        self.assertEqual(bytes(cpu.memory[0xc262:0xc264]), pac)
        self.assertEqual(bytes(cpu.memory[0xc2a0:0xc2a2]), other)
        self.assertEqual(bytes(cpu.memory[0xc298:0xc29a]), eyes)
        self.assertEqual(bytes(cpu.memory[0xc290:0xc2b0]), ghosts)
        self.assertEqual(bytes(cpu.memory[0xc2fc:0xc2ff]), chomp_state)
        self.assertEqual(cpu.memory[0xc306], 1)  # frightened, even with eyes
        self.assertEqual(cpu.memory[0xc282], 1)
        self.assertIn(185, vdp.psg[psg_len:])  # frightened sound
        self.assertIn(212, vdp.psg[psg_len:])  # ghost-eaten sound
        self.assertEqual(bytes(vdp.ram), display)  # no animation or redraw
        self.assertEqual(cpu.memory[0xc27f], frightened)
        self.assertEqual(cpu.memory[0xc261], frame_counter)
        self.assertEqual(bytes(cpu.memory[0xc30c:0xc30e]), release_ticks)
        self.assertEqual(vdp.ram[6914], 228)
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc31a], 0)
        self.assertEqual(cpu.memory[0xc296], 1)
        self.assertNotEqual(vdp.ram[6914], 228)  # Pac-Man reappears
        self.assertEqual(cpu.memory[0xc31b], 2)
        self.assertEqual(vdp.psg[-1], saved_chomp_volume)
        self.assertEqual(bytes(cpu.memory[0xc298:0xc29a]), eyes)  # no final-frame step
        self.assertEqual(bytes(cpu.memory[0xc2fc:0xc2ff]), chomp_state)
        advance(cpu, vdp, 1)
        self.assertNotEqual(bytes(cpu.memory[0xc298:0xc29a]), eyes)
        # A second ghost awards 400 and uses the NES's 38-frame repeat pause.
        cpu.memory[0xc290], cpu.memory[0xc291], cpu.memory[0xc292] = 20, 28, 1
        cpu.memory[0xc293], cpu.memory[0xc295], cpu.memory[0xc296] = 0, 0, 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc31a], 38)
        self.assertEqual(vdp.ram[6914], 232)

    def test_popup_plays_only_ghost_sounds_and_resumes_chomp(self):
        cpu, vdp = self.new_game()
        # Put an unrelated effect and a pellet sound on their channels.
        cpu.memory[0xc282], cpu.memory[0xc283] = 60, 5
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 12, 1
        cpu.memory[0xc000 + 22 + 2] = 3
        advance(cpu, vdp, 1, ghosts_disabled=True)
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 28
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        cpu.memory[0xc27f], cpu.memory[0xc2d4] = 100, 0
        cpu.memory[0xc290], cpu.memory[0xc291], cpu.memory[0xc292] = 20, 28, 1
        cpu.memory[0xc293], cpu.memory[0xc295], cpu.memory[0xc296] = 0, 0, 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc31a], 40)
        saved_volume = cpu.memory[0xc31f]
        self.assertEqual(vdp.psg[-4:], [159, 191, 223, 255])
        chomp_state = bytes(cpu.memory[0xc2fc:0xc2ff])
        start = len(vdp.psg)
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc283], 1)
        self.assertEqual(cpu.memory[0xc2fa], 1)  # ghost event replaced extra-life
        self.assertEqual(cpu.memory[0xc282], 39)
        self.assertEqual(cpu.memory[0xc306], 1)  # panic selected
        self.assertIn(185, vdp.psg[start:])
        self.assertIn(212, vdp.psg[start:])
        self.assertEqual(bytes(cpu.memory[0xc2fc:0xc2ff]), chomp_state)
        advance(cpu, vdp, 38)
        self.assertEqual(bytes(cpu.memory[0xc2fc:0xc2ff]), chomp_state)
        # All latch writes in the freeze address only channels 1 or 2.
        self.assertTrue(all(not (128 <= n < 160) and n < 224
                            for n in vdp.psg[start:] if n >= 128))
        advance(cpu, vdp, 1)
        self.assertEqual(vdp.psg[-1], saved_volume)
        self.assertEqual(bytes(cpu.memory[0xc2fc:0xc2ff]), chomp_state)
        self.assertEqual(cpu.memory[0xc282], 0)
        advance(cpu, vdp, 1)
        self.assertNotEqual(bytes(cpu.memory[0xc2fc:0xc2ff]), chomp_state)

    def test_score_popup_scroll_and_tunnel_early_clock(self):
        cpu, vdp = self.new_game()
        for n in range(1, 4):
            cpu.memory[0xc293 + n * 8] = 255
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 4, 108, 3
        cpu.memory[0xc260], cpu.memory[0xc300] = 3, 0
        cpu.memory[0xc27f], cpu.memory[0xc2d4] = 100, 0
        cpu.memory[0xc290], cpu.memory[0xc291], cpu.memory[0xc292] = 4, 108, 3
        cpu.memory[0xc293], cpu.memory[0xc295], cpu.memory[0xc296] = 0, 0, 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc31a], 40)
        self.assertEqual(vdp.ram[6912:6916], bytes([75, 28, 228, 0x87]))

    def test_mode_timer_reverses_and_pauses_for_frightened(self):
        cpu, vdp = self.new_game()
        for ghost in range(4):
            cpu.memory[0xc290 + ghost * 8 + 3] = 0
            cpu.memory[0xc290 + ghost * 8 + 2] = 1
            cpu.memory[0xc290 + ghost * 8 + 5] = 0
            cpu.memory[0xc290 + ghost * 8 + 6] = 0
        cpu.memory[0xc2d0], cpu.memory[0xc2d1], cpu.memory[0xc2d2] = 0, 0, 59
        cpu.memory[0xc27f] = 5
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc2d0], 0)
        self.assertEqual(cpu.memory[0xc2d2], 59)
        cpu.memory[0xc27f] = 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc2d0], 1)
        self.assertEqual(cpu.memory[0xc2d1], 20)
        self.assertEqual([cpu.memory[0xc292 + n * 8] for n in range(4)], [3] * 4)

    def test_scatter_phase_does_not_reverse_and_personal_latch_persists(self):
        cpu, vdp = self.new_game()
        for ghost in range(4):
            cpu.memory[0xc293 + ghost * 8] = 0
            cpu.memory[0xc292 + ghost * 8] = 1
            cpu.memory[0xc295 + ghost * 8] = 0
            cpu.memory[0xc296 + ghost * 8] = 0
        cpu.memory[0xc2d0], cpu.memory[0xc2d1], cpu.memory[0xc2d2] = 1, 0, 59
        cpu.memory[0xc27c], cpu.memory[0xc27f] = 20, 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc311], 1)  # threshold latch
        self.assertEqual(cpu.memory[0xc2d0], 2)
        self.assertEqual(cpu.memory[0xc2d1], 7)
        self.assertEqual([cpu.memory[0xc292 + n * 8] for n in range(4)], [1] * 4)
        cpu.memory[0xc27c] = 19
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc311], 1)

    def test_frightened_long_timer_rollover(self):
        cpu, vdp = self.new_game()
        cpu.memory[0xc27f], cpu.memory[0xc2d4] = 1, 1
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc27f], 255)
        self.assertEqual(cpu.memory[0xc2d4], 0)

    def test_nes_frightened_counter_and_zero_duration_stage(self):
        cpu, vdp = self.new_game()
        cpu.memory[0xc27d] = 17  # zero-second profile still lasts 30 frames
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 28, 1
        cpu.memory[0xc000 + 3 * 22 + 2] = 1
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc27f], 30)
        self.assertEqual(cpu.memory[0xc312], 30)
        advance(cpu, vdp, 30, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc27f], 0)
        self.assertEqual(cpu.memory[0xc312], 0)
        # A second energizer while active preserves the NES subsecond divider.
        cpu.memory[0xc27d], cpu.memory[0xc27f], cpu.memory[0xc312] = 1, 100, 16
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 28
        cpu.memory[0xc000 + 3 * 22 + 2] = 1
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc312], 17)
        self.assertEqual((cpu.memory[0xc27f], cpu.memory[0xc2d4]), (208, 1))

    def test_real_pellet_and_fruit_streams_drive_independent_psg_channels(self):
        cpu, vdp = self.new_game()
        for n in range(4):
            cpu.memory[0xc293 + n * 8] = 255
        # The first pellet leaves an odd remaining count and requests slot 05.
        cpu.memory[0xc27c] = 192
        cpu.memory[0xc000 + 22 + 2] = 3
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 12, 1
        start = len(vdp.psg)
        advance(cpu, vdp, 9, ghosts_disabled=True)
        writes = vdp.psg[start:]
        events = psg_events(STREAMS['sfx_pellet_odd'])
        expected = [0x80 | events[i + 1] for i in range(0, len(events) - 1, 3)]
        self.assertEqual([x for x in writes if 0x80 <= x <= 0x8f], expected)
        self.assertIn(159, writes)  # pellet stream terminates and mutes
        self.assertIn(185, writes)  # looping NES siren remains on tone 1
        # Fruit request runs its original rapidly changing note stream on tone 2.
        cpu.memory[0xc282], cpu.memory[0xc283] = 40, 4
        start = len(vdp.psg)
        advance(cpu, vdp, 12, ghosts_disabled=True)
        writes = vdp.psg[start:]
        events = psg_events(STREAMS['sfx_fruit'])
        expected = [0xc0 | events[i + 1] for i in range(0, 12 * 3, 3)]
        self.assertEqual([x for x in writes if 0xc0 <= x <= 0xcf], expected)

    def test_nes_level_speed_fractions_and_blinky_thresholds(self):
        cpu, vdp = self.new_game()
        for n in range(1, 4):
            cpu.memory[0xc293 + n * 8] = 255
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        for level, remaining, expected_fraction in ((1, 192, 144), (1, 20, 160),
                                                     (1, 10, 176), (15, 100, 0),
                                                     (15, 50, 16), (22, 192, 16)):
            with self.subTest(level=level, remaining=remaining):
                cpu.memory[0xc262], cpu.memory[0xc263] = 20, 28
                cpu.memory[0xc27d], cpu.memory[0xc27c] = level, remaining
                cpu.memory[0xc27f] = 0
                cpu.memory[0xc290], cpu.memory[0xc291], cpu.memory[0xc292] = 52, 68, 2
                cpu.memory[0xc293], cpu.memory[0xc295], cpu.memory[0xc296] = 0, 0, 0
                advance(cpu, vdp, 1)
                self.assertEqual(cpu.memory[0xc295], expected_fraction)
        # Pac-Man's leftward fractional accumulator borrows the selected speed.
        for tile, scared, expected in ((7, 0, 80), (3, 0, 96), (1, 0, 128),
                                       (7, 4, 48), (3, 4, 64)):
            with self.subTest(tile=tile, scared=scared):
                cpu.memory[0xc27d], cpu.memory[0xc27f] = 1, scared
                cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 12, 1
                cpu.memory[0xc300] = 0
                cpu.memory[0xc000 + 22 + 2] = tile
                for n in range(4):
                    cpu.memory[0xc293 + n * 8] = 255
                advance(cpu, vdp, 1, ghosts_disabled=True)
                self.assertEqual(cpu.memory[0xc300], expected)

    def test_ready_music_plays_before_gameplay(self):
        cpu, vdp = make_machine(self.rom)
        advance(cpu, vdp, 210)
        vdp.pad = 0xef
        advance(cpu, vdp, 15)
        vdp.pad = 0xff
        self.assertGreater(cpu.memory[0xc281], 0)
        start = len(vdp.psg)
        position = bytes(cpu.memory[0xc262:0xc264])
        advance(cpu, vdp, 40)
        self.assertEqual(bytes(cpu.memory[0xc262:0xc264]), position)
        writes = vdp.psg[start:]
        self.assertIn(148, writes)  # first READY voice, PSG tone 0
        self.assertIn(184, writes)  # second READY voice, PSG tone 1
        advance(cpu, vdp, 210)
        self.assertEqual(cpu.memory[0xc281], 0)
        self.assertEqual(cpu.memory[0xc2f0], 0)

    def test_nes_house_release_targets_and_idle_release(self):
        cpu, vdp = self.new_game()
        # Round 1: Pinky is exiting, Inky and Clyde wait; 30 and 90 dots
        # are the global release targets from the disassembly.
        self.assertEqual([cpu.memory[0xc296 + n * 8] for n in range(4)], [0, 4, 3, 3])
        self.assertEqual((cpu.memory[0xc30e], cpu.memory[0xc30f]), (30, 90))
        cpu.memory[0xc27c] = 163
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 12, 1
        cpu.memory[0xc000 + 22 + 2] = 3
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc27c], 162)
        self.assertEqual(cpu.memory[0xc2a6], 4)  # Inky exits on dot 30
        self.assertEqual(cpu.memory[0xc30e], 90)
        self.assertEqual(cpu.memory[0xc30c], 1)  # dot reset, then this frame's tick
        # Four NES release seconds are 384 ticks; force the counter to expire.
        cpu.memory[0xc30c], cpu.memory[0xc30d] = 127, 1  # 383
        cpu.memory[0xc000 + 22 + 2] = 7
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc2ae], 4)  # Clyde exits on timeout
        self.assertEqual((cpu.memory[0xc30c], cpu.memory[0xc30d]), (0, 0))

    def test_nes_ready_glyphs_and_temporary_maze_overlay(self):
        cpu, vdp = make_machine(self.rom)
        advance(cpu, vdp, 210)
        vdp.pad = 0xef
        advance(cpu, vdp, 15)
        vdp.pad = 0xff
        camera = cpu.memory[0xc260]
        def row(world_row, col, count):
            start = 6144 + (world_row - camera) * 32 + col
            return vdp.ram[start:start + count]
        self.assertEqual(vdp.ram[6912], 208)  # actors enter after 120 frames
        self.assertEqual(row(11, 8, 6), bytes(range(230, 236)))
        self.assertEqual(row(13, 10, 3), bytes(range(236, 239)))
        self.assertEqual(row(16, 8, 6), bytes(range(224, 230)))
        for bank in range(3):
            offset = bank * 2048 + 224 * 8
            self.assertEqual(vdp.ram[offset:offset + 120], ready_text_patterns(self.chr_data))
            self.assertEqual(vdp.ram[8192 + offset:8192 + offset + 48], bytes([0xb1] * 48))
            self.assertEqual(vdp.ram[8192 + offset + 48:8192 + offset + 120], bytes([0x71] * 72))
        self.assertEqual(vdp.ram[14336 + 1440:14336 + 1824], death_sprite_patterns(self.chr_data))
        frames = death_sprite_patterns(self.chr_data)
        self.assertEqual(len(frames), 12 * 32)
        self.assertEqual(frames[:32], pacman_sprite_patterns(self.chr_data)[:32])
        self.assertEqual(frames[-32:], bytes(32))  # NES frame 1D is blank
        advance(cpu, vdp, 120)
        self.assertNotEqual(vdp.ram[6912], 208)
        self.assertEqual(row(11, 8, 6), cpu.memory[0xc000 + 11 * 22 + 8:0xc000 + 11 * 22 + 14])
        self.assertEqual(row(13, 10, 3), cpu.memory[0xc000 + 13 * 22 + 10:0xc000 + 13 * 22 + 13])
        self.assertEqual(row(16, 8, 6), bytes(range(224, 230)))
        advance(cpu, vdp, 130)
        self.assertEqual(row(16, 8, 6), cpu.memory[0xc000 + 16 * 22 + 8:0xc000 + 16 * 22 + 14])

    def test_nes_death_freeze_animation_sound_and_life_timing(self):
        cpu, vdp = self.new_game()
        for n in range(1, 4):
            cpu.memory[0xc293 + n * 8] = 255
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 28, 1
        cpu.memory[0xc290], cpu.memory[0xc291], cpu.memory[0xc293] = 20, 28, 0
        cpu.memory[0xc296], cpu.memory[0xc27f] = 0, 0
        advance(cpu, vdp, 1)
        self.assertEqual((cpu.memory[0xc313], cpu.memory[0xc314]), (1, 128))
        self.assertEqual(vdp.ram[6914], 180)  # NES death frame 12
        self.assertEqual(cpu.memory[0xc27e], 3)
        position = bytes(cpu.memory[0xc262:0xc264])
        advance(cpu, vdp, 127)
        self.assertEqual(bytes(cpu.memory[0xc262:0xc264]), position)
        self.assertEqual(cpu.memory[0xc313], 1)
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc313], 2)
        self.assertEqual(cpu.memory[0xc283], 2)
        self.assertEqual(vdp.ram[6916], 208)  # hide ghosts during animation
        for frame in range(1, 12):
            advance(cpu, vdp, 11)
            self.assertEqual(cpu.memory[0xc315], frame)
            self.assertEqual(vdp.ram[6914], (45 + frame) * 4)
            self.assertEqual(cpu.memory[0xc27e], 3)
        advance(cpu, vdp, 11)
        self.assertEqual(cpu.memory[0xc313], 0)
        self.assertEqual(cpu.memory[0xc27e], 2)
        self.assertEqual(vdp.ram[6518:6528], b'READY     ')

    def test_death_release_targets_are_relative_to_eaten_dots(self):
        cpu, vdp = self.new_game()
        cpu.memory[0xc27c] = 150  # 42 already eaten
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 28
        cpu.memory[0xc290], cpu.memory[0xc291] = 20, 28
        cpu.memory[0xc293], cpu.memory[0xc296] = 0, 0
        cpu.memory[0xc27f] = 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc313], 1)
        advance(cpu, vdp, 260)
        self.assertEqual(cpu.memory[0xc27e], 2)
        self.assertEqual([cpu.memory[0xc296 + n * 8] for n in range(4)], [0, 3, 3, 3])
        self.assertEqual(list(cpu.memory[0xc30e:0xc311]), [49, 59, 74])

    def test_eyes_follow_a_route_to_house_from_maze(self):
        cpu, vdp = self.new_game()
        for n in range(1, 4):
            cpu.memory[0xc290 + n * 8 + 3] = 255
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 28
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        cpu.memory[0xc290], cpu.memory[0xc291] = 52, 68
        cpu.memory[0xc292], cpu.memory[0xc293], cpu.memory[0xc296] = 1, 0, 1
        advance(cpu, vdp, 70)
        self.assertEqual(cpu.memory[0xc296], 4)  # exiting after entering house
        self.assertEqual(cpu.memory[0xc290], 92)
        advance(cpu, vdp, 60)
        self.assertIn(cpu.memory[0xc296], (0, 2))  # back to active maze movement

    def test_fruit_threshold_scoring_layers_and_expiry(self):
        cpu, vdp = self.new_game()
        self.assertEqual(vdp.ram[14336 + 928:14336 + 1440], fruit_sprite_patterns(self.chr_data))
        for ghost in range(4):
            cpu.memory[0xc290 + ghost * 8 + 3] = 255
        # A dot at the first threshold spawns a cherry for 660 frames.
        cpu.memory[0xc27c] = 135
        cpu.memory[0xc000 + 22 + 2] = 3
        cpu.memory[0xc262], cpu.memory[0xc263], cpu.memory[0xc264] = 20, 12, 1
        cpu.memory[0xc260], cpu.memory[0xc261] = 0, 0
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc27c], 134)
        self.assertEqual(cpu.memory[0xc2ec] + 256 * cpu.memory[0xc2ed], 659)
        self.assertEqual(vdp.ram[6950], 116)  # cherry green layer pattern
        self.assertEqual(vdp.ram[6954], 148)  # red layer
        self.assertEqual(vdp.ram[6956], 208)
        cpu.memory[0xc262], cpu.memory[0xc263] = 92, 124
        cpu.memory[0xc261] = 0
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc2ec] + 256 * cpu.memory[0xc2ed], 0)
        digits = cpu.memory[0xc270:0xc276]
        self.assertEqual(sum(d * 10 ** (i + 1) for i, d in enumerate(digits)), 110)
        self.assertEqual(cpu.memory[0xc283], 4)
        self.assertEqual(vdp.ram[6948], 208)
        # Later-round key award, and timeout without points.
        cpu.memory[0xc27d] = 13
        cpu.memory[0xc2ec], cpu.memory[0xc2ed] = 4, 0
        cpu.memory[0xc262], cpu.memory[0xc263] = 92, 124
        advance(cpu, vdp, 1, ghosts_disabled=True)
        digits = cpu.memory[0xc270:0xc276]
        self.assertEqual(sum(d * 10 ** (i + 1) for i, d in enumerate(digits)), 5110)
        cpu.memory[0xc2ec], cpu.memory[0xc2ed] = 1, 0
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 12
        advance(cpu, vdp, 1, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc2ec], 0)
        digits = cpu.memory[0xc270:0xc276]
        self.assertEqual(sum(d * 10 ** (i + 1) for i, d in enumerate(digits)), 5110)

    def test_returning_eyes_are_harmless_and_recover_at_entrance(self):
        cpu, vdp = self.new_game()
        for n in range(1, 4):
            cpu.memory[0xc290 + n * 8 + 3] = 255
        cpu.memory[0xc262], cpu.memory[0xc263] = 52, 68
        cpu.memory[0xc290], cpu.memory[0xc291] = 52, 68
        cpu.memory[0xc293], cpu.memory[0xc296] = 0, 1
        cpu.memory[0xc27f], cpu.memory[0xc261] = 30, 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc27e], 3)
        self.assertEqual(vdp.ram[6916], 209)  # no body scanline slot
        self.assertEqual(vdp.ram[6919] & 15, 0)  # transparent ghost body
        self.assertEqual(vdp.ram[6923] & 15, 15)
        cpu.memory[0xc290], cpu.memory[0xc291] = 92, 84
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc296], 5)  # enters the house as eyes
        cpu.memory[0xc27f] = 100
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 28
        cpu.memory[0xc000 + 3 * 22 + 2] = 7
        advance(cpu, vdp, 65)
        self.assertEqual(cpu.memory[0xc296], 2)  # recovered, immune for this energizer
        cpu.memory[0xc27f] = 0
        advance(cpu, vdp, 1)
        self.assertEqual(cpu.memory[0xc296], 0)

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
        self.assertEqual(cpu.memory[0xc27e], 3)  # life is lost after animation
        self.assertEqual(cpu.memory[0xc313], 1)
        advance(cpu, vdp, 260)
        self.assertEqual(cpu.memory[0xc27e], 2)
        self.assertEqual(vdp.ram[6518:6528], b'READY     ')
        self.assertGreater(cpu.memory[0xc281], 0)
        self.assertEqual(cpu.memory[0xc000 + 5 * 22 + 2], 7)
        self.assertEqual(vdp.ram[6742:6750], bytes([60, 61, 32, 32, 32, 32, 32, 32]))
        advance(cpu, vdp, 192, ghosts_disabled=True)
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
        self.assertEqual(cpu.memory[0xc27e], 1)
        advance(cpu, vdp, 260)
        self.assertEqual(cpu.memory[0xc27e], 0)
        self.assertEqual(vdp.ram[6518:6528], b'GAME OVER ')
        self.assertEqual(cpu.memory[0xc28c], 1)
        advance(cpu, vdp, 290)  # game over resets to title
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
        self.assertEqual(vdp.ram[6518:6528], b'READY     ')
        advance(cpu, vdp, 192, ghosts_disabled=True)
        self.assertEqual(vdp.ram[6518:6528], b'          ')


if __name__ == '__main__':
    unittest.main()
