; Pac-Man movement and pellet handling on the decoded NES tile map.
; 1 KiB RAM: C260 camera row, C261 frame counter, C262/C263 center XY in pixels,
; C264 current dir, C265 requested dir (NES order up/left/down/right), C266-C26A
; scratch, C26B chomp timer; C270-C275 score digits (least significant first, 10 points/unit),
; C276-C27B pending digits. Coordinates are relative to the 22x27 maze.
;
; This is not the complete NES movement engine: it uses 3/4 pixel per frame,
; tile-center collision/turns, simplified tunnel wrapping, and a scrolling
; viewport. Chomp is approximated on the SN76489. Ghosts and round logic live
; in separate modules; this is not a complete NES engine translation.

player_init:
    ld a,92                   ; NES start X=60h maps to maze center 92
    ld (49762),a
    ld a,164                  ; NES start Y=A8h maps to maze center 164
    ld (49763),a
    ld a,1                    ; left
    ld (49764),a
    ld (49765),a
    ld a,3
    ld (49760),a              ; start at bottom of 27-row maze
    xor a
    ld (49761),a
    ld (49771),a
    ld a,159                  ; mute PSG tone and noise channels
    out (127),a
    ld a,191
    out (127),a
    ld a,223
    out (127),a
    ld a,255
    out (127),a
    xor a
    ld hl,49776               ; score and pending digits
    ld b,12
player_init_digits:
    ld (hl),a
    inc hl
    djnz player_init_digits
    ret

player_frame:
    ld a,(49771)
    or a
    jr z,player_sound_done
    dec a
    ld (49771),a
    jr z,player_sound_mute
    ld b,a
    ld a,8
    sub b
    or 144                    ; short channel-0 volume decay
    out (127),a
    jr player_sound_done
player_sound_mute:
    ld a,159                  ; silence channel 0 after the chomp
    out (127),a
player_sound_done:
    ; NES priority is right, left, down, up. No input retains direction.
    in a,(220)
    ld b,a
    bit 3,b
    jr z,player_want_right
    bit 2,b
    jr z,player_want_left
    bit 1,b
    jr z,player_want_down
    bit 0,b
    jr z,player_want_up
    ld a,(49764)
    jr player_store_request
player_want_right:
    ld a,3
    jr player_store_request
player_want_left:
    ld a,1
    jr player_store_request
player_want_down:
    ld a,2
    jr player_store_request
player_want_up:
    xor a
player_store_request:
    ld (49765),a
    ld a,(49761)
    inc a
    ld (49761),a
    and 3
    jp z,player_frame_sprite   ; 3 pixels per 4 frames

    ; Exact 8-pixel cell centers are (4,4) modulo 8.
    ld a,(49762)
    and 7
    cp 4
    jr nz,player_mid_tile
    ld a,(49763)
    and 7
    cp 4
    jr nz,player_mid_tile
    call player_consume_tile
    ld a,(49765)
    call player_can_move
    jr nz,player_check_current
    ld a,(49765)
    ld (49764),a
player_check_current:
    ld a,(49764)
    call player_can_move
    jp nz,player_frame_sprite
    jr player_do_move
player_mid_tile:
    ; Like NES Pac-Man, allow a reversal before reaching a tile center.
    ld a,(49765)
    xor 2
    ld b,a
    ld a,(49764)
    cp b
    jr nz,player_do_move
    ld a,(49765)
    ld (49764),a
player_do_move:
    ld a,(49764)
    cp 0
    jr z,player_move_up
    cp 1
    jr z,player_move_left
    cp 2
    jr z,player_move_down
player_move_right:
    ld a,(49762)
    cp 172
    jr nz,player_inc_x
    ld a,(49763)
    cp 108                    ; tunnel row 13
    jr nz,player_move_right_normal
    ld a,4
    ld (49762),a
    jr player_after_move
player_move_right_normal:
    ld a,(49762)
player_inc_x:
    inc a
    ld (49762),a
    jr player_after_move
player_move_left:
    ld a,(49762)
    cp 4
    jr nz,player_dec_x
    ld a,(49763)
    cp 108
    jr nz,player_move_left_normal
    ld a,172
    ld (49762),a
    jr player_after_move
player_move_left_normal:
    ld a,(49762)
player_dec_x:
    dec a
    ld (49762),a
    jr player_after_move
player_move_up:
    ld a,(49763)
    dec a
    ld (49763),a
    jr player_after_move
player_move_down:
    ld a,(49763)
    inc a
    ld (49763),a
player_after_move:
    call player_update_camera
player_frame_sprite:
    call player_draw_sprite
    ret

; A = requested direction. Z if neighbor tile is passable. Uses NES passability
; rule (tile & F0h)==0 and restricts horizontal edge wrap to tunnel row 13.
player_can_move:
    ld (49766),a
    ld a,(49762)
    srl a
    srl a
    srl a
    ld e,a
    ld a,(49763)
    srl a
    srl a
    srl a
    ld d,a
    ld a,(49766)
    or a
    jr z,player_probe_up
    cp 1
    jr z,player_probe_left
    cp 2
    jr z,player_probe_down
    ld a,e
    cp 21
    jr nz,player_probe_right_regular
    ld a,d
    cp 13
    jr nz,player_probe_blocked
    ld e,0
    jr player_probe_tile
player_probe_right_regular:
    inc e
    jr player_probe_tile
player_probe_left:
    ld a,e
    or a
    jr nz,player_probe_left_regular
    ld a,d
    cp 13
    jr nz,player_probe_blocked
    ld e,21
    jr player_probe_tile
player_probe_left_regular:
    dec e
    jr player_probe_tile
player_probe_up:
    ld a,d
    or a
    jr z,player_probe_blocked
    dec d
    jr player_probe_tile
player_probe_down:
    ld a,d
    cp 26
    jr z,player_probe_blocked
    inc d
player_probe_tile:
    call player_map_address
    ld a,(hl)
    and 240
    ret
player_probe_blocked:
    ld a,1
    or a
    ret

; D=row 0..26, E=column 0..21; HL returns C000 + row*22 + column.
player_map_address:
    ld a,e
    ld (49769),a
    ld l,d
    ld h,0
    add hl,hl                 ; row*2
    push hl
    add hl,hl                 ; row*4
    push hl
    add hl,hl
    add hl,hl                 ; row*16
    pop de
    add hl,de                 ; row*20
    pop de
    add hl,de                 ; row*22
    ld a,(49769)
    ld e,a
    ld d,0
    add hl,de
    ld de,49152
    add hl,de
    ret

; Eat a pellet under the centered player, update RAM tile, VRAM and score.
player_consume_tile:
    ld a,(49762)
    srl a
    srl a
    srl a
    ld e,a
    ld a,(49763)
    srl a
    srl a
    srl a
    ld d,a
    call player_map_address
    ld a,(hl)
    cp 3
    jr z,player_regular_pellet
    cp 9
    jr z,player_alternate_pellet
    cp 1
    jr z,player_power_pellet
    cp 2
    ret nz
player_power_pellet:
    push hl
    call ghost_start_frightened
    pop hl
    ld a,5                    ; 50 points in 10-point units
    ld (49782),a
    ld a,7
    jr player_clear_pellet
player_alternate_pellet:
    ld a,1
    ld (49782),a
    ld a,8                    ; NES alternate pellet clears to tile 08
    jr player_clear_pellet
player_regular_pellet:
    ld a,1
    ld (49782),a
    ld a,7
player_clear_pellet:
    ld (hl),a
    ld (49768),a
    ld a,(49788)
    or a
    jr z,player_dot_count_done
    dec a
    ld (49788),a
    jr nz,player_dot_count_done
    ld a,1
    ld (49846),a              ; complete the round after this frame
player_dot_count_done:
    ; Short alternating approximate chomp on SN76489 tone channel 0.
    ld a,(49788)
    and 1
    jr z,player_chomp_low
    ld a,140                  ; tone divisor 172
    out (127),a
    ld a,10
    jr player_chomp_high_byte
player_chomp_low:
    ld a,130                  ; tone divisor 210
    out (127),a
    ld a,13
player_chomp_high_byte:
    out (127),a
    ld a,148                  ; channel 0 volume
    out (127),a
    ld a,6
    ld (49771),a
    call game_commit_score
    ; Address the changed tile on the current screen.
    ld a,(49763)
    srl a
    srl a
    srl a
    ld b,a
    ld a,(49760)
    ld c,a
    ld a,b
    sub c
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl                 ; visible row * 32
    ld a,(49762)
    srl a
    srl a
    srl a
    ld e,a
    ld d,0
    add hl,de
    ld de,6144
    add hl,de
    ex de,hl
    call set_vram_write
    ld a,(49768)
    out (190),a
    ret

; Print the six unpacked score digits in NES order, suppressing leading zeroes.
player_draw_score:
    ld de,6390
    ld hl,49781
    ; fall through: DE=VRAM destination, HL=most significant digit
 game_write_digits:
    call set_vram_write
    ld b,6
    ld c,0
player_score_loop:
    ld a,(hl)
    or a
    jr nz,player_score_digit
    ld a,c
    or a
    jr nz,player_score_digit
    ld a,b
    cp 1
    jr z,player_score_digit
    ld a,32
    jr player_score_write
player_score_digit:
    ld c,1
    ld a,(hl)
    add a,48
player_score_write:
    out (190),a
    dec hl
    djnz player_score_loop
    ld a,48                   ; implicit ones digit (scores are in tens)
    out (190),a
    ret

; Scroll near the top/bottom edges, keeping the 16x16 player visible while
; leaving the HUD fixed. The NES maze is 27 rows and the screen is 24, so
; the only valid top-row offsets are 0..3. Move one row per threshold crossing.
player_update_camera:
    ld a,(49763)
    srl a
    srl a
    srl a
    ld b,a                    ; Pac-Man's maze row
    ld a,(49760)
    add a,4                   ; keep four rows above the player if possible
    cp b
    jr c,player_camera_bottom
    jr z,player_camera_bottom
    ld a,(49760)
    or a
    ret z                     ; already at top
    dec a
    jr player_camera_change
player_camera_bottom:
    ld a,(49760)
    add a,19                  ; keep four rows below the player if possible
    cp b
    ret nc
    ld a,(49760)
    cp 3
    ret z                     ; already at bottom
    inc a
player_camera_change:
    ld (49760),a
    ld a,128
    out (191),a
    ld a,129
    out (191),a
    call draw_maze
    call display_on
    ret

; Emit one 16x16 TMS sprite, yellow. Select the same nine NES source frames
; used by the NES animation routine. The SG-1000 has no sprite flip bits;
; flipped quadrants are precomputed in pacman_sprite_patterns at build time.
player_draw_sprite:
    ld de,6912
    call set_vram_write
    ld a,(49760)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(49763)
    sub b
    sub 9                     ; TMS sprite Y stores top minus one
    out (190),a
    ld a,(49762)
    cp 8
    jr nc,player_sprite_normal_x
    add a,24                  ; early-clock shifts sprite left by 32 pixels
    ld b,139                  ; early clock + light yellow
    jr player_sprite_x_ready
player_sprite_normal_x:
    sub 8
    ld b,11
player_sprite_x_ready:
    out (190),a
    ld a,(49761)
    and 7
    cp 6
    jr nc,player_sprite_closed
    cp 3
    ld c,0
    jr c,player_sprite_phase_ready
    inc c
player_sprite_phase_ready:
    ld a,(49764)
    add a,a
    add a,c
    inc a                     ; frame 1..8
    add a,a
    add a,a                   ; 16x16 pattern index is a multiple of 4
    jr player_sprite_pattern_ready
player_sprite_closed:
    xor a
player_sprite_pattern_ready:
    out (190),a
    ld a,b
    out (190),a
    ld a,208                  ; end sprite list
    out (190),a
    ret
