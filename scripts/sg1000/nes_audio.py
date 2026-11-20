"""NES Namco audio streams and translation to SN76489 tone events.

These streams correspond to src/audio/streams.asm and their manifest hashes;
only the observed note, duration and control commands are accepted. The PSG
cannot reproduce the NES pulse duty, triangle waveform, or APU envelopes.
"""
# Raw stream prologues and commands, byte-for-byte from the NES disassembly.
STREAMS = {
    'sfx_extra': bytes.fromhex('01037f08a20ca20ca20ca20ca20ca20ca20ca20cf0'),
    'sfx_fruit': bytes.fromhex('03047f08330123010301a201920172015201320122010201a1019101c0089101a1010201220132015201f0'),
    'sfx_ghost': bytes.fromhex('02007f10200350038002a002210251028101a1010201220132015201f5187301c008f0'),
    'sfx_death': bytes.fromhex('01427f38230233024302530243023302230213022302330243023302230213020302130223023302230213020302b20203021302230213020302b202a202b202030223020302b202a2029202a202b2020302b202a202920282029202a2020302a20292028202f200f300f51831017101b10132017201b20133017301c00231017101b10132017201b20133017301f0'),
    'sfx_ready_a': bytes.fromhex('01817f4031083208a10871083207a107710cc00641084208b10881084207b107810cc00631083208a10871083207a107710cc00661057105810581059105a105a105b1050205320cf0'),
    'sfx_ready_b': bytes.fromhex('02827f403018a008300ea00cc0064018b008400eb00cc0063018a008300ea00cc006a00f010f210f310cf0'),
    'sfx_pellet_even': bytes.fromhex('019f7f28010141017101a1010201f518f0'),
    'sfx_pellet_odd': bytes.fromhex('019f7f280201a10171014101f5180101f0'),
    'sfx_siren_high': bytes.fromhex('01967f2882019201a201b2010301130123013301430153013301230113010301b201a201920182017201f0'),
    'sfx_siren_mid': bytes.fromhex('01967f28a201b2010301130123013301430153013301230113010301b201a2019201f0'),
    'sfx_siren_low': bytes.fromhex('01967f28b2010301130123013301430153013301230113010301b201a201f0'),
    'sfx_frightened': bytes.fromhex('029c7f2831017101a101120132017201a2011301f0'),
    'sfx_eyes': bytes.fromhex('02987f283301230113010301a20182017201520132011201a10171013101f0'),
}

# The NES uses the same 12 big-endian period bases, right-shifted by octave.
NOTE_PERIODS = (0x3f9, 0x3c0, 0x38a, 0x357, 0x327, 0x2fa,
                0x2cf, 0x2a7, 0x281, 0x25d, 0x23b, 0x21b)


def psg_events(stream):
    """Compile to [frames, low divisor, high divisor] events, zero terminated.

    C0-EF holds the previous channel output for the duration, not a rest.
    F2/F3/F5 change APU duty/envelope/length registers; a fixed PSG loudness
    approximates those hardware-specific effects. The period is incremented
    because the APU divides by timer+1 while the PSG divides by its divisor.
    """
    if len(stream) < 5 or stream[0] not in (1, 2, 3, 4):
        raise ValueError('invalid sound prologue')
    result = bytearray()
    i = 4
    while i < len(stream):
        command = stream[i]
        i += 1
        if command == 0xf0:
            if i != len(stream):
                raise ValueError('bytes after stream stop')
            return bytes(result + b'\x00')
        if command in (0xf2, 0xf3, 0xf5):
            if i >= len(stream):
                raise ValueError('missing control operand')
            i += 1
            continue
        if command >= 0xf0:
            raise ValueError('unsupported NES sound opcode')
        if i >= len(stream) or not stream[i]:
            raise ValueError('missing or zero duration')
        duration = stream[i]
        i += 1
        if command >= 0xc0:
            result.extend((duration, 255, 0))
        else:
            period = (NOTE_PERIODS[command >> 4] >> (command & 15)) + 1
            if period > 1023:
                raise ValueError('note outside PSG tone range')
            result.extend((duration, period & 15, period >> 4))
    raise ValueError('unterminated NES stream')
