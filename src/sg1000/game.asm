; Game state for the SG-1000 prototype. C27C=count, C27D=round,
; C27E=lives, C27F=frightened timer, C280=ghost chain, C281=pause,
; C282/C283=event sound timer/kind, C285-C28A=high score, C28B=1UP latch,
; C28C=game-over latch, C2B6=level-clear request.

game_init:
    xor a
    ld hl,49791
    ld b,5
init_game_flags:
    ld (hl),a
    inc hl
    djnz init_game_flags
    ld hl,49803               ; extra-life/game-over and temporary flags
    ld b,5
init_game_misc_flags:
    ld (hl),a
    inc hl
    djnz init_game_misc_flags
    ld (49846),a
    ld (49900),a
    ld (49901),a
    ld (49939),a
    ld (49943),a
    ld (49944),a
    ld (49945),a
    ; Preserve the high score when the game-over path returns to the title.
    ; A four-byte signature avoids treating typical power-on RAM as valid.
    ld a,(49856)
    cp 80
    jr nz,game_cold_highscore
    ld a,(49857)
    cp 65
    jr nz,game_cold_highscore
    ld a,(49858)
    cp 67
    jr nz,game_cold_highscore
    ld a,(49859)
    cp 83
    jr z,game_highscore_ready
 game_cold_highscore:
    xor a
    ld hl,49797
    ld b,6
 game_clear_highscore:
    ld (hl),a
    inc hl
    djnz game_clear_highscore
    ld a,1
    ld (49800),a              ; initial high score 10,000
    ld a,80
    ld (49856),a
    ld a,65
    ld (49857),a
    ld a,67
    ld (49858),a
    ld a,83
    ld (49859),a
 game_highscore_ready:
    ld a,1
    ld (49789),a              ; round
    ld a,3
    ld (49790),a              ; lives
    ld a,192
    ld (49788),a              ; NES v1.0 dot count
    call ghost_init
    call sound_ready_init
    ld a,250
    ld (49793),a             ; pause while the two-voice READY tune plays
    ret

game_frame:
    call sound_frame
    ld a,(49939)
    or a
    jp nz,game_death_tick
    ld a,(49946)
    or a
    jp nz,ghost_popup_tick
    ld a,(49793)
    or a
    jr z,game_active
    dec a
    ld (49793),a
    jr z,game_pause_done
    ld b,a
    ld a,(49944)
    or a
    ret z
    cp b
    ret nz
    xor a
    ld (49944),a
    call draw_maze             ; restore PLAYER/ONE underlying maze cells
    call player_draw_sprite    ; NES places actors at READY frame $78
    call ghost_draw
    jp game_ready_draw_ready    ; READY! remains until the pause ends
 game_pause_done:
    call game_clear_message
    ld a,(49945)
    or a
    jr z,game_pause_no_level_ready
    xor a
    ld (49945),a
    ld a,192
    ld (49793),a
    call game_show_ready
    ret
 game_pause_no_level_ready:
    ld a,(49804)
    or a
    jp nz,0                   ; game over: return to title, reset score/maze
    ret
 game_active:
    ld a,(49791)
    or a
    jr z,game_power_tick_done
    ld a,(49938)
    inc a
    cp 60
    jr c,game_fright_divider_store
    xor a
 game_fright_divider_store:
    ld (49938),a
    ld a,(49791)
    dec a
    ld (49791),a
    jr nz,game_power_tick_done
    ld a,(49876)              ; each extra block represents 255 frames
    or a
    jr z,game_power_tick_done
    dec a
    ld (49876),a
    ld a,255
    ld (49791),a
 game_power_tick_done:
    call player_frame
    call fruit_tick
    ld a,(49846)
    or a
    jr z,game_ghost_tick
    call game_next_level
    ret
 game_ghost_tick:
    call ghost_frame
    ret

; Commit pending digits, update high score, award the one-time 10,000 1UP.
game_commit_score:
    ld hl,49776
    ld de,49782
    call add_score_digits
    ld a,(49803)
    or a
    jr nz,game_compare_high
    ld a,(49779)              ; score digit 3 = 10,000 points
    or a
    jr z,game_compare_high
    ld a,1
    ld (49803),a
    ld a,(49790)
    cp 9
    jr nc,game_compare_high
    inc a
    ld (49790),a
    call game_draw_lives
    ld a,60
    ld (49794),a
    ld a,5
    ld (49795),a
 game_compare_high:
    ld hl,49781
    ld de,49802
    ld b,6
 game_compare_digit:
    ld a,(de)
    cp (hl)
    jr c,game_promote_high
    jr nz,game_score_done
    dec hl
    dec de
    djnz game_compare_digit
    jr game_score_done
 game_promote_high:
    ld hl,49776
    ld de,49797
    ld bc,6
    ldir
    call game_draw_high
 game_score_done:
    call player_draw_score
    ret

; Reset positions, but preserve consumed pellets, score, lives and round.
game_reset_positions:
    ld a,92
    ld (49762),a
    ld a,164
    ld (49763),a
    ld a,1
    ld (49764),a
    ld (49765),a
    ld a,3
    ld (49760),a
    xor a
    ld (49791),a
    ld (49792),a
    ld (49876),a
    ld (49938),a
    ld (49920),a
    ld (49921),a
    ld (49900),a
    ld (49901),a
    call ghost_init
    ret

; Restore the original decoded maze and begin the next round.
game_next_level:
    xor a
    ld (49846),a
    ld (49771),a
    call sound_stop_chomp    ; stop chomp while the level clears
    ld hl,maze_data
    ld de,49152
    call decode_maze
    ld a,192
    ld (49788),a
    ld a,(49789)
    cp 99
    jr nc,game_level_capped
    inc a
    ld (49789),a
 game_level_capped:
    call game_reset_positions
    ld a,1
    ld (49945),a              ; after clear, enter the READY sequence
    ld a,90
    ld (49793),a
    ld (49794),a
    ld a,3
    ld (49795),a
    ld a,128
    out (191),a
    ld a,129
    out (191),a
    call draw_maze
    call game_draw_round
    call player_draw_sprite
    call ghost_draw
    call game_show_clear
    call display_on
    ret

 ; READY uses the exact NES sprite glyphs as temporary background tiles.
; This avoids using 15 scarce TMS sprites and restores the RAM maze afterward.
game_show_ready:
    ld de,6912                 ; NES hides actors until READY frame $78
    call set_vram_write
    ld a,208
    out (190),a
    ld a,1
    ld (49943),a
    ld a,(49793)
    sub 120
    jr nc,game_ready_store_hide_time
    xor a
 game_ready_store_hide_time:
    ld (49944),a
    ld hl,game_ready_text
    call game_write_message
    call game_ready_draw_ready
    ld d,11                   ; PLAYER at NES $44,$60, adjusted for viewport
    ld e,8
    ld hl,game_player_glyphs
    ld bc,6
    call game_ready_write_row
    ld d,13                   ; ONE at NES $50,$70
    ld e,10
    ld hl,game_one_glyphs
    ld bc,3
    jp game_ready_write_row

game_ready_draw_ready:
    ld d,16                   ; READY! at NES $44,$88
    ld e,8
    ld hl,game_ready_glyphs
    ld bc,6
    jp game_ready_write_row

; D=world tile row, E=column, HL=glyphs, BC=count.
game_ready_write_row:
    push hl
    push bc
    ld a,(49760)
    ld b,a
    ld a,d
    sub b
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld d,0
    add hl,de
    ld de,6144
    add hl,de
    ex de,hl
    call set_vram_write
    pop bc
    pop hl
    jp write_vram_block

game_show_over:
    ld hl,game_over_text
    jr game_write_message
game_show_clear:
    ld hl,game_clear_text
    jr game_write_message
game_clear_message:
    ld a,(49943)
    or a
    jr z,game_clear_hud_message
    xor a
    ld (49943),a
    ld (49944),a
    call draw_maze
 game_clear_hud_message:
    ld hl,game_blank_text
 game_write_message:
    ld de,6518                ; row 11, column 22
    call set_vram_write
    ld bc,10
    jp write_vram_block
 game_ready_text: defb 82,69,65,68,89,32,32,32,32,32
 game_over_text:  defb 71,65,77,69,32,79,86,69,82,32
 game_clear_text: defb 67,76,69,65,82,32,32,32,32,32
 game_blank_text: defb 32,32,32,32,32,32,32,32,32,32
 game_ready_glyphs:  defb 224,225,226,227,228,229
 game_player_glyphs: defb 230,231,232,233,234,235
 game_one_glyphs:    defb 236,237,238

; High score, lives and round occupy fixed HUD addresses, not the scroll area.
game_draw_high:
    ld de,6262                ; row 3, column 22
    ld hl,49802
    jp game_write_digits

game_draw_lives:
    ld a,(49790)
    or a
    jr z,game_life_count_ready
    dec a                     ; NES shows spare lives, not current life
 game_life_count_ready:
    cp 5
    jr c,game_life_count_capped
    ld a,4
 game_life_count_capped:
    ld (49855),a
    ld de,6742                ; row 18, column 22
    call set_vram_write
    ld a,(49855)
    ld c,a
    ld b,4
 game_lives_top:
    ld a,c
    or a
    jr z,game_lives_top_blank
    dec c
    ld a,60                   ; NES life icon top-left
    out (190),a
    ld a,61
    out (190),a
    jr game_lives_top_next
 game_lives_top_blank:
    ld a,32
    out (190),a
    out (190),a
 game_lives_top_next:
    djnz game_lives_top
    ld de,6774                ; row 19
    call set_vram_write
    ld a,(49855)
    ld c,a
    ld b,4
 game_lives_bottom:
    ld a,c
    or a
    jr z,game_lives_bottom_blank
    dec c
    ld a,62                   ; NES life icon bottom-left
    out (190),a
    ld a,63
    out (190),a
    jr game_lives_bottom_next
 game_lives_bottom_blank:
    ld a,32
    out (190),a
    out (190),a
 game_lives_bottom_next:
    djnz game_lives_bottom
    ret

game_draw_round:
    ld de,6812                ; row 20, column 28
    call set_vram_write
    ld a,(49789)
    ld b,0
 game_round_tens:
    cp 10
    jr c,game_round_write
    sub 10
    inc b
    jr game_round_tens
 game_round_write:
    ld c,a
    ld a,b
    or a
    jr z,game_round_space
    add a,48
    jr game_round_tens_out
 game_round_space:
    ld a,32
 game_round_tens_out:
    out (190),a
    ld a,c
    add a,48
    out (190),a
    ret
