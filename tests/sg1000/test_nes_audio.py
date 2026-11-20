"""Check the source stream bytes and their PSG note/duration compilation."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/sg1000'))
from nes_audio import STREAMS, psg_events


class NesAudioTests(unittest.TestCase):
    def test_streams_match_disassembly_manifest_and_rom(self):
        names = {
            'sfx_ready_a': 'slot00_player_ready_channel_a',
            'sfx_ready_b': 'slot01_player_ready_channel_b',
            'sfx_extra': 'slot02_extra_life', 'sfx_death': 'slot03_death',
            'sfx_pellet_even': 'slot04_pellet_even',
            'sfx_pellet_odd': 'slot05_pellet_odd',
            'sfx_fruit': 'slot06_fruit', 'sfx_ghost': 'slot07_eat_ghost',
            'sfx_eyes': 'slot08_ghost_house_state6_marker',
            'sfx_frightened': 'slot09_ghost_house_release_marker',
            'sfx_siren_high': 'slot0a_release_counter_hi',
            'sfx_siren_mid': 'slot0b_release_counter_mid',
            'sfx_siren_low': 'slot0c_release_counter_lo',
        }
        assets = json.loads((ROOT / 'assets/manifest.json').read_text())['assets']
        assets = {a['path'].split('/')[-1].removesuffix('.bin'): a
                  for a in assets if a['image'] == 'japan-v10'}
        rom = (ROOT / 'pacman.nes').read_bytes() if (ROOT / 'pacman.nes').exists() else None
        for label, asset in names.items():
            with self.subTest(label=label):
                stream = STREAMS[label]
                self.assertEqual(hashlib.sha1(stream).hexdigest(), assets[asset]['sha1'])
                if rom is not None:
                    self.assertIn(stream, rom)
                events = psg_events(stream)
                self.assertEqual(events[-1], 0)
                self.assertEqual((len(events) - 1) % 3, 0)

    def test_notes_and_hold_and_bad_commands(self):
        # 31h = NES base 0357h >> 1; the PSG needs timer+1.
        result = psg_events(bytes([1, 0x81, 0x7f, 0x40, 0x31, 8,
                                   0xc0, 6, 0xf3, 0, 0x32, 7, 0xf0]))
        self.assertEqual(result, bytes([8, 12, 26, 6, 255, 0, 7, 6, 13, 0]))
        for invalid in (bytes([1, 0, 0, 0, 0xf7]),
                        bytes([1, 0, 0, 0, 0x31]),
                        bytes([1, 0, 0, 0, 0x31, 0]),
                        bytes([1, 0, 0, 0, 0xf0, 1])):
            with self.assertRaises(ValueError):
                psg_events(invalid)


if __name__ == '__main__':
    unittest.main()
