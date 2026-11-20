; Decimal score accumulator translated from the live-play digit addition in
; src/game/scoring.asm. The six digits are stored least significant first;
; each unit is ten points, exactly as in the NES scoring routine.
;
; HL = six score digits, DE = six pending score digits (non-overlapping).
; Adds and clears pending digits; wraps after the sixth digit as on the NES.
; Both arrays must contain unpacked decimal digits 0..9 on entry.
; Clobbers AF, B, DE and HL. Caller handles demo suppression, HUD, high score,
; extra lives and sound; these are NOT implemented by this routine.
add_score_digits:
    ld b,6
    or a                       ; start with carry clear
score_digit_loop:
    ld a,(de)
    adc a,(hl)
    cp 10
    jr c,score_no_carry
    sub 10
    scf
    jr score_store
score_no_carry:
    or a                       ; Z80 CP sets carry for less-than; clear it
score_store:
    ld (hl),a
    ld a,0                     ; LD does not disturb the decimal carry
    ld (de),a
    inc hl
    inc de
    djnz score_digit_loop
    ret
