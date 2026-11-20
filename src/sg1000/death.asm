; NES death script adapted to the SG-1000. C313 = 0 playing, 1 collision
; freeze, 2 animation; C314 = phase timer, C315 = death OAM frame 0..11.
game_death_start:
    xor a
    ld (49771),a
    ld (49941),a
    call sound_stop_chomp
    ld a,1
    ld (49939),a
    ld (49793),a              ; stop the ghost loop after this collision
    ld a,128                  ; NES pre-death freeze
    ld (49940),a
    call player_draw_sprite   ; NES frame 12, closed Pac-Man
    ret

game_death_tick:
    ld a,(49940)
    dec a
    ld (49940),a
    ret nz
    ld a,(49939)
    cp 1
    jr nz,game_death_advance
    ld a,2
    ld (49939),a
    ld a,11                   ; NES countdown $0A decrements through zero
    ld (49940),a
    ld a,100
    ld (49794),a
    ld a,2
    ld (49795),a              ; play original NES death stream
    ld a,191
    out (127),a              ; stop ghost siren while ghosts disappear
    call player_draw_sprite  ; its terminator hides all ghosts and fruit
    ret
 game_death_advance:
    ld a,11
    ld (49940),a
    ld a,(49941)
    inc a
    cp 12                     ; NES frame $1E is the terminal boundary
    jr nc,game_death_finish
    ld (49941),a
    jp player_draw_sprite

game_death_finish:
    xor a
    ld (49939),a
    ld (49793),a
    ld a,(49790)
    or a
    jr z,game_death_game_over
    dec a
    ld (49790),a
    call game_draw_lives
    ld a,(49790)
    or a
    jr z,game_death_game_over
    call game_reset_positions
    ld a,192                  ; NES READY script holds at least $C0 frames
    ld (49793),a
    ld a,128
    out (191),a
    ld a,129
    out (191),a
    call draw_maze
    call player_draw_sprite
    call ghost_draw
    call game_show_ready
    call display_on
    ret
 game_death_game_over:
    ld a,1
    ld (49804),a
    ld a,255                  ; NES game-over script runs until byte wraps
    ld (49793),a
    call game_show_over
    ret
