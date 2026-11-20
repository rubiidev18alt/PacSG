; Post-eat score freeze. C31A countdown, C31B NES pause accumulator,
; C31C eaten ghost slot, C31D score-popup index.
; Sprite zero is temporarily the popup, hiding Pac-Man and giving the score
; priority over other hardware sprites on the same scanline.
ghost_popup_draw:
    ld de,6912
    call set_vram_write
    ld a,(49760)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(ix+1)
    sub b
    sub 9
    out (190),a
    ld a,(ix+0)
    cp 8
    jr nc,ghost_popup_regular_x
    add a,24
    ld b,135                 ; early clock + light cyan
    jr ghost_popup_x_ready
 ghost_popup_regular_x:
    sub 8
    ld b,7                   ; light cyan
 ghost_popup_x_ready:
    out (190),a
    ld a,(49949)
    add a,57                 ; after Pac-Man, ghost, fruit and death patterns
    add a,a
    add a,a
    out (190),a
    ld a,b
    out (190),a
    ld a,208
    out (190),a
    ret

ghost_popup_tick:
    call sound_popup_frame    ; only the ghost-eaten audio advances
    ld a,(49946)
    dec a
    ld (49946),a
    ret nz                    ; no simulation or sprite updates
    ; Release the just-eaten ghost as eyes; the NES retains a value of 2
    ; in its pause accumulator for subsequent captures in the same round.
    ld a,2
    ld (49947),a
    ld a,(49948)
    add a,a
    add a,a
    add a,a
    ld e,a
    ld d,0
    ld hl,49808
    add hl,de
    push hl
    pop ix
    ld (ix+6),1
    call player_draw_sprite
    call ghost_draw
    jp sound_unfreeze
