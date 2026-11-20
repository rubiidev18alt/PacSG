; Z80 translation of src/game/turn_candidates.asm.
; HL = four cached tile IDs, IX = four-byte output, A = current direction,
; D = accepted exact tile, E = accepted masked tile class.
; Writes candidates in direction order followed by FF bytes, excluding reverse.
; Clobbers AF, BC and HL; preserves DE and IX. Input and output must not overlap.
; Direction encoding is NES order: up=0, left=1, down=2, right=3.
collect_valid_turn_candidates:
    push ix
    ld (ix+0),255
    ld (ix+1),255
    ld (ix+2),255
    ld (ix+3),255
    xor 2
    and 3
    ld b,a                       ; reverse direction
    ld c,0
turn_scan:
    ld a,c
    cp b
    jr z,turn_next
    ld a,(hl)
    cp d
    jr z,turn_store
    and 248
    jr z,turn_store
    cp e
    jr nz,turn_next
turn_store:
    ld (ix+0),c
    inc ix
turn_next:
    inc hl
    inc c
    ld a,c
    cp 4
    jr nz,turn_scan
    pop ix
    ret
