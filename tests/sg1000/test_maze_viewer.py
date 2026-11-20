"""Boot the cartridge and exercise Pac-Man on a Z80 with a minimal VDP/PSG."""
from pathlib import Path
import sys
import tempfile
import unittest
import z80

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/sg1000'))
from build_maze_viewer import assets_from_rom, build, pacman_sprite_patterns, title_assets
from decode_maze import decode


class VDP:
    def __init__(self):
        self.ram = bytearray(16384)
        self.registers = [0] * 8
        self.latch = None
        self.address = 0
        self.pad = 255
        self.vblank = False
        self.psg = []

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
        elif port & 255 == 127:
            self.psg.append(value)

    def input(self, port):
        if port & 255 == 191:
            self.latch = None
            value = 128 if self.vblank else 0
            self.vblank = False
            return value
        return self.pad


def advance(cpu, vdp, frames, ghosts_disabled=False):
    for _ in range(frames):
        if ghosts_disabled:
            for ghost in range(4):
                cpu.memory[0xc290 + ghost * 8 + 3] = 255
        vdp.vblank = True
        cpu.ticks_to_stop = 1000000
        cpu.run()


def make_machine(rom):
    cpu, vdp = z80.Z80Machine(), VDP()
    cpu.set_memory_block(0, rom)
    cpu.set_input_callback(vdp.input)
    cpu.set_output_callback(vdp.output)
    return cpu, vdp


class ViewerTests(unittest.TestCase):
    def test_reject_unrecognized_rom(self):
        with self.assertRaisesRegex(ValueError, 'verified'):
            assets_from_rom(bytes(24592))

    def test_sprite_quads_and_flips(self):
        # Construct unique top/bottom rows in each NES tile: verifying that
        # conversion honors horizontal and vertical NES OAM flips and the TMS
        # TL, BL, TR, BR sprite-pattern layout.
        chr_data = bytearray(8192)
        for tile in range(9):
            for y in range(8):
                chr_data[4096 + tile * 16 + y] = (tile * 17 + y) & 255
        data = pacman_sprite_patterns(chr_data)
        self.assertEqual(len(data), 9 * 32)
        first = [chr_data[4096 + y] for y in range(8)]
        flip = lambda x: int(f'{x:08b}'[::-1], 2)
        self.assertEqual(data[:8], bytes(first))
        self.assertEqual(data[8:16], bytes(reversed(first)))
        self.assertEqual(data[16:24], bytes(map(flip, first)))
        self.assertEqual(data[24:32], bytes(map(flip, reversed(first))))

    def test_title_and_synthetic_maze(self):
        maze = bytes([0xc3] * 5 + [0x43]) * 27  # 22 ordinary pellets per row
        logo = bytes(range(138))
        palette = bytes([0x0f, 0x20, 0x0f, 0x06, 0x0f, 0x26, 0x20, 0x27,
                         0x0f, 0x06, 0x0f, 0x26, 0x0f, 0x06, 0x20, 0x26])
        chr_data = bytes([255]) * 8192
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.sg'
            build(maze, chr_data, path, logo=logo, title_palette=palette)
            rom = path.read_bytes()
        self.assertEqual(len(rom), 49152)
        cpu, vdp = make_machine(rom)
        advance(cpu, vdp, 60)
        self.assertEqual(vdp.registers, [2, 194, 6, 255, 3, 54, 7, 1])
        patterns, colors, names = title_assets(chr_data, logo, palette)
        self.assertEqual(vdp.ram[:6144], patterns)
        self.assertEqual(vdp.ram[8192:14336], colors)
        self.assertEqual(vdp.ram[6144:6912], names)
        vdp.pad = 0xef
        advance(cpu, vdp, 70)
        self.assertEqual(vdp.ram[14336:14336 + 288], pacman_sprite_patterns(chr_data))
        self.assertEqual(vdp.ram[6932], 208)
        self.assertEqual(vdp.ram[6144 + 5 * 32 + 22:6144 + 5 * 32 + 25], bytes([0xb0, 0xb3, 0xb2]))
        self.assertEqual(vdp.ram[6144 + 1 * 32 + 22:6144 + 1 * 32 + 32], bytes(range(0xb4, 0xbc)) + b'  ')
        for bank in range(3):
            off = bank * 2048 + 0x2d * 8
            self.assertEqual(vdp.ram[off:off + 8], bytes(8))
            self.assertEqual(vdp.ram[8192 + off:8192 + off + 8], bytes([0x11] * 8))

    def test_real_rom_movement_pellets_walls_and_tunnel(self):
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
        cpu, vdp = make_machine(rom)
        advance(cpu, vdp, 60)
        self.assertEqual(vdp.ram[6144:6912], title_assets(chr_data, logo, palette)[2])
        vdp.pad = 0xef
        advance(cpu, vdp, 15)
        vdp.pad = 0xff
        advance(cpu, vdp, 115, ghosts_disabled=True)
        # Pac-Man automatically moves left, eats the five dots and stops at
        # the wall to the left. NES score stores one unit for 10 points.
        self.assertEqual((cpu.memory[0xc262], cpu.memory[0xc263]), (52, 164))
        self.assertEqual(bytes(cpu.memory[0xc270:0xc276]), b'\x05\0\0\0\0\0')
        self.assertEqual(vdp.ram[6390:6397], b'     50')
        for x in range(6, 11):
            self.assertEqual(cpu.memory[0xc000 + 20 * 22 + x], 7)
        self.assertIn(148, vdp.psg)  # chomp volume
        self.assertIn(159, vdp.psg)  # chomp ends muted
        self.assertIn(185, vdp.psg)  # independent ghost-siren channel
        self.assertEqual(vdp.ram[6932], 208)
        self.assertEqual(vdp.ram[6915] & 15, 11)  # yellow sprite
        self.assertEqual(vdp.ram[14336:14336 + 288], pacman_sprite_patterns(chr_data))
        camera = cpu.memory[0xc260]
        for row in range(24):
            start = 0xc000 + (row + camera) * 22
            self.assertEqual(vdp.ram[6144 + row * 32:6144 + row * 32 + 22],
                             bytes(cpu.memory[start:start + 22]))
        # Reverse along consumed tiles; the same dots must not score twice.
        vdp.pad = 0xf7  # right
        advance(cpu, vdp, 35, ghosts_disabled=True)
        self.assertGreater(cpu.memory[0xc262], 52)
        self.assertEqual(cpu.memory[0xc270], 5)
        # An uneaten power pellet gives 50 points and clears once. Pac-Man
        # is placed on a real power-pellet tile facing an adjacent wall.
        cpu.memory[0xc262], cpu.memory[0xc263] = 20, 28
        cpu.memory[0xc264], cpu.memory[0xc260], cpu.memory[0xc261] = 1, 0, 0
        vdp.pad = 0xff
        advance(cpu, vdp, 10, ghosts_disabled=True)
        self.assertEqual(cpu.memory[0xc000 + 3 * 22 + 2], 7)
        self.assertEqual((cpu.memory[0xc262], cpu.memory[0xc263]), (20, 28))
        self.assertEqual(bytes(cpu.memory[0xc270:0xc276]), b'\0\x01\0\0\0\0')
        self.assertEqual(vdp.ram[6390:6397], b'    100')
        advance(cpu, vdp, 10, ghosts_disabled=True)
        self.assertEqual(bytes(cpu.memory[0xc270:0xc276]), b'\0\x01\0\0\0\0')
        # The horizontal tunnel wraps to the other edge.
        cpu.memory[0xc262], cpu.memory[0xc263] = 4, 108
        cpu.memory[0xc264], cpu.memory[0xc261] = 1, 0
        advance(cpu, vdp, 4, ghosts_disabled=True)
        self.assertGreaterEqual(cpu.memory[0xc262], 168)
        self.assertLessEqual(cpu.memory[0xc262], 172)
        # A legal upward turn moves Pac-Man along the corridor and the camera
        # follows him, without changing the HUD columns.
        cpu.memory[0xc262], cpu.memory[0xc263] = 52, 164
        cpu.memory[0xc264], cpu.memory[0xc260], cpu.memory[0xc261] = 1, 3, 0
        vdp.pad = 0xfe
        advance(cpu, vdp, 250, ghosts_disabled=True)
        self.assertEqual((cpu.memory[0xc262], cpu.memory[0xc263]), (52, 12))
        self.assertEqual(cpu.memory[0xc260], 0)
        for row in range(24):
            start = 0xc000 + row * 22
            self.assertEqual(vdp.ram[6144 + row * 32:6144 + row * 32 + 22],
                             bytes(cpu.memory[start:start + 22]))
        self.assertEqual(vdp.ram[6144 + 1 * 32 + 22:6144 + 1 * 32 + 32], bytes(range(0xb4, 0xbc)) + b'  ')
        # Follow a real corridor all the way back to the bottom. The map and
        # sprite must scroll together, and the HUD must not be overwritten.
        vdp.pad = 0xfd  # down to row 23, where the corridor ends
        advance(cpu, vdp, 300, ghosts_disabled=True)
        self.assertEqual((cpu.memory[0xc262], cpu.memory[0xc263]), (52, 188))
        self.assertEqual(cpu.memory[0xc260], 3)
        vdp.pad = 0xfb  # left to column 2
        advance(cpu, vdp, 60, ghosts_disabled=True)
        self.assertEqual((cpu.memory[0xc262], cpu.memory[0xc263]), (20, 188))
        vdp.pad = 0xfd  # down to row 25
        advance(cpu, vdp, 40, ghosts_disabled=True)
        self.assertEqual((cpu.memory[0xc262], cpu.memory[0xc263]), (20, 204))
        self.assertEqual(cpu.memory[0xc260], 3)
        for row in range(24):
            start = 0xc000 + (row + 3) * 22
            self.assertEqual(vdp.ram[6144 + row * 32:6144 + row * 32 + 22],
                             bytes(cpu.memory[start:start + 22]))
        self.assertEqual(vdp.ram[6912], 204 - 3 * 8 - 9)
        self.assertEqual(vdp.ram[6144 + 1 * 32 + 22:6144 + 1 * 32 + 32], bytes(range(0xb4, 0xbc)) + b'  ')


if __name__ == '__main__':
    unittest.main()
