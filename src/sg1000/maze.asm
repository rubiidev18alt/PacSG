; Z80 translation of the NES maze RLE decoding loop in
; src/rendering/maze_rendering.asm. Unlike the NES PPU writer, this routine
; decodes to RAM so tiles can be queried and changed by game logic.
;
; HL = pointer to trusted, row-aligned RLE stream (each row expands to 22).
; DE = pointer to 594 writable bytes (27 rows of 22 tiles).
; On return HL and DE point past input and output, respectively.
; Clobbers AF, BC, HL, DE. The caller must ensure enough RAM and valid input;
; there is no length check, matching the original. Use decode_maze.py to
; validate assets during the build. The separate three-row NES banner isn't
; part of this maze stream and is not decoded here.
;
; Each byte contains (run length - 1) in bits 7..6 and tile in bits 5..0.
decode_maze:
    ld b,27
maze_next_row:
    ld c,22
maze_next_token:
    ld a,(hl)
    inc hl
    push bc
    ld b,a
    and 63
    ld c,a                    ; tile id
    ld a,b
    rlca
    rlca
    and 3
    inc a                     ; run length 1..4
    ld b,a
maze_write_run:
    ld a,c
    ld (de),a
    inc de
    djnz maze_write_run
    ; Recover run length from the consumed token, while preserving DE.
    pop bc
    dec hl
    ld a,(hl)
    inc hl
    rlca
    rlca
    and 3
    inc a
    push de
    ld e,a
    ld a,c
    sub e
    ld c,a
    pop de
    jr nz,maze_next_token
    djnz maze_next_row
    ret
