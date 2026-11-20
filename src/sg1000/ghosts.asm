; Four SG-1000 ghost approximations. Each C290 record is eight bytes:
; X, Y, direction, release/respawn wait, TMS color, fractional speed, two reserved bytes.
; Ghosts use two NES-derived sprite masks: colored body plus white eyes.
; The TMS9918's four-sprites-per-scanline limit is mitigated by rotating ghost
; priority, but layered sprites can flicker/drop when many actors overlap.
;
; C28D/E save Pac-Man XY while using player_can_move for ghost tile probes;
; C28F ghost index; C2B0/C2B1 drawing/loop work; C2B7 opposite direction;
; C2B8-BB candidate list; C2BC temporary candidate.

ghost_init:
    ld hl,ghost_initial_records
    ld de,49808
    ld bc,32
    ldir
    xor a
    ld (49872),a              ; scatter/chase phase
    ld (49874),a              ; 60 Hz seconds divider
    call ghost_load_phase_duration
    ret

ghost_initial_records:
    defb 52,68,1,0,8,0,0,0      ; red
    defb 132,68,3,45,13,0,0,0   ; pink
    defb 52,148,1,90,7,0,0,0    ; cyan
    defb 132,148,3,135,10,0,0,0 ; orange

; NES per-round frightened durations in 60-Hz frames. A nonzero high
; component counts additional 255-frame blocks, so the low countdown stays
; nonzero throughout frightened mode. Later rounds with duration zero do not
; make ghosts edible in this prototype.
ghost_start_frightened:
    xor a
    ld (49792),a              ; reset ghost chain
    ld a,(49789)
    cp 24
    jr c,ghost_fright_round_ok
    ld a,23
 ghost_fright_round_ok:
    dec a
    add a,a
    ld e,a
    ld d,0
    ld hl,ghost_fright_durations
    add hl,de
    ld a,(hl)
    ld (49791),a
    inc hl
    ld a,(hl)
    ld (49876),a
    ld a,(49791)
    or a
    ret z
    jp ghost_frighten
; Low frames, number of additional 255-frame blocks; seconds per NES table:
; 7,6,4,3,2,5,2,2,1,5,2,1,1,3,1,1,0,1,0,0,0,0,0.
ghost_fright_durations:
    defb 165,1,105,1,240,0,180,0,120,0,45,1
    defb 120,0,120,0,60,0,45,1,120,0,60,0
    defb 60,0,180,0,60,0,60,0,0,0,60,0
    defb 0,0,0,0,0,0,0,0,0,0

; Reverse released ghosts immediately on a power pellet, as the NES does.
ghost_frighten:
ghost_reverse_all:
    ld ix,49808
    ld b,4
 ghost_frighten_loop:
    ld a,(ix+3)
    or a
    jr nz,ghost_frighten_next
    ld a,(ix+2)
    xor 2
    ld (ix+2),a
 ghost_frighten_next:
    ld de,8
    add ix,de
    djnz ghost_frighten_loop
    ret

ghost_frame:
    call ghost_mode_tick
    ld a,(49762)
    ld (49805),a
    ld a,(49763)
    ld (49806),a
    xor a
    ld (49807),a
    ld ix,49808
    ld b,4
 ghost_frame_loop:
    push bc
    ld a,(ix+3)
    or a
    jr z,ghost_released
    dec a
    ld (ix+3),a
    jp ghost_next
 ghost_released:
    ; NES-style fixed-point fraction: accumulate each ghost's stage/mode
    ; speed and move one pixel on carry (late-stage speeds are capped at 1).
    call ghost_speed_fraction
    add a,(ix+5)
    ld (ix+5),a
    jp nc,ghost_check_collision
 ghost_move:
    ; Reuse the NES-style neighbor probe with ghost coordinates temporarily
    ; installed, restoring the real Pac-Man coordinates before collision.
    ld a,(ix+0)
    ld (49762),a
    ld a,(ix+1)
    ld (49763),a
    and 7
    cp 4
    jr nz,ghost_step
    ld a,(49762)
    and 7
    cp 4
    jr nz,ghost_step
    call ghost_choose_direction
    jr nz,ghost_restore_position  ; no legal exit
 ghost_step:
    ld a,(ix+2)
    or a
    jr z,ghost_step_up
    cp 1
    jr z,ghost_step_left
    cp 2
    jr z,ghost_step_down
 ghost_step_right:
    ld a,(49762)
    cp 172
    jr nz,ghost_increment_x
    ld a,(49763)
    cp 108
    jr nz,ghost_right_reload
    ld a,4
    jr ghost_store_x
 ghost_right_reload:
    ld a,(49762)
 ghost_increment_x:
    inc a
    jr ghost_store_x
 ghost_step_left:
    ld a,(49762)
    cp 4
    jr nz,ghost_decrement_x
    ld a,(49763)
    cp 108
    jr nz,ghost_left_reload
    ld a,172
    jr ghost_store_x
 ghost_left_reload:
    ld a,(49762)
 ghost_decrement_x:
    dec a
 ghost_store_x:
    ld (ix+0),a
    jr ghost_restore_position
 ghost_step_up:
    dec (ix+1)
    jr ghost_restore_position
 ghost_step_down:
    inc (ix+1)
 ghost_restore_position:
    ld a,(49805)
    ld (49762),a
    ld a,(49806)
    ld (49763),a
 ghost_check_collision:
    call ghost_collide
 ghost_next:
    pop bc
    ld a,(49793)
    or a
    jr nz,ghost_frame_done     ; death/respawn pause was started
    ld de,8
    add ix,de
    ld a,(49807)
    inc a
    ld (49807),a
    dec b
    jp nz,ghost_frame_loop
 ghost_frame_done:
    call ghost_draw
    ret

; Normal, frightened and tunnel fractions from the NTSC level profiles.
; Blinky's level-one pellet thresholds use the two original boosted speeds.
ghost_speed_fraction:
    ld a,(49791)
    or a
    jr nz,ghost_slow_fraction
    ld a,(ix+1)
    cp 108                    ; tunnel row
    jr nz,ghost_normal_fraction
    ld a,(ix+0)
    cp 44
    jr c,ghost_slow_fraction
    cp 140
    jr nc,ghost_slow_fraction
 ghost_normal_fraction:
    ld a,(49789)
    cp 1
    jr nz,ghost_normal_other_rounds
    ld a,(49807)
    or a
    jr nz,ghost_normal_level_one
    ld a,(49788)
    cp 11
    jr c,ghost_fast_second
    cp 21
    jr c,ghost_fast_first
 ghost_normal_level_one:
    ld a,144                  ; 90h / 256 pixels per frame
    ret
 ghost_fast_first:
    ld a,160
    ret
 ghost_fast_second:
    ld a,176
    ret
 ghost_normal_other_rounds:
    cp 4
    jr c,ghost_normal_round_two
    cp 6
    jr c,ghost_normal_round_four
    cp 22
    jr c,ghost_normal_round_six
    ld a,255                  ; 0110h+ profiles capped at one pixel/frame
    ret
 ghost_normal_round_two:
    ld a,160
    ret
 ghost_normal_round_four:
    ld a,208
    ret
 ghost_normal_round_six:
    ld a,240
    ret
 ghost_slow_fraction:
    ld a,(49789)
    cp 4
    jr c,ghost_slow_early
    cp 6
    jr c,ghost_slow_mid
    ld a,128
    ret
 ghost_slow_mid:
    ld a,112
    ret
 ghost_slow_early:
    ld a,80
    ret

; Round-driven scatter/chase schedule based on the NES timer tables. The
; divider pauses during frightened mode. Reversals use the shared helper.
ghost_mode_tick:
    ld a,(49791)
    or a
    ret nz
    ld a,(49873)
    cp 255
    ret z
    ld a,(49874)
    inc a
    cp 60
    jr c,ghost_mode_store_divider
    xor a
    ld (49874),a
    ld a,(49873)
    dec a
    ld (49873),a
    ret nz
    ld a,(49872)
    cp 7
    ret nc
    inc a
    ld (49872),a
    call ghost_load_phase_duration
    call ghost_reverse_all
    ret
 ghost_mode_store_divider:
    ld (49874),a
    ret

ghost_load_phase_duration:
    ld hl,ghost_phase_round_one
    ld a,(49789)
    cp 2
    jr c,ghost_phase_table_ready
    ld hl,ghost_phase_round_two
    cp 4
    jr c,ghost_phase_table_ready
    ld hl,ghost_phase_later
 ghost_phase_table_ready:
    ld a,(49872)
    ld e,a
    ld d,0
    add hl,de
    ld a,(hl)
    ld (49873),a
    ret
ghost_phase_round_one:
    defb 7,20,7,20,5,20,5,255
ghost_phase_round_two:
    defb 7,20,7,20,5,255,255,255
ghost_phase_later:
    defb 5,20,5,20,5,255,255,255

; Choose targets and ranked directions using the NES slot formulas and LUT.
; This reuses the prototype's RAM tile probes and its dead-end fallback.
ghost_choose_direction:
    ld a,(ix+2)
    xor 2
    ld (49847),a
    ld a,(49791)
    or a
    jp nz,ghost_seeded_choice
    ld a,(49872)
    and 1
    jr nz,ghost_chase_target
    ; NES corner targets in maze-local pixels (NES coordinates minus 4).
    ld a,(49807)
    add a,a
    ld e,a
    ld d,0
    ld hl,ghost_corner_targets
    add hl,de
    ld a,(hl)
    ld (49842),a
    inc hl
    ld a,(hl)
    ld (49843),a
    jr ghost_rank_target
 ghost_chase_target:
    ld a,(49807)
    or a
    jr z,ghost_target_pacman
    cp 1
    jr z,ghost_target_ahead
    cp 2
    jr z,ghost_target_vector
    ; Clyde uses Pac-Man when either axis is >=32 pixels away, otherwise
    ; chooses a seeded legal non-reverse exit (the reconstructed NES behavior).
    ld a,(49762)
    ld b,a
    ld a,(49805)
    sub b
    jr nc,ghost_clyde_x_positive
    neg
 ghost_clyde_x_positive:
    cp 32
    jr nc,ghost_target_pacman
    ld a,(49763)
    ld b,a
    ld a,(49806)
    sub b
    jr nc,ghost_clyde_y_positive
    neg
 ghost_clyde_y_positive:
    cp 32
    jp c,ghost_seeded_choice
 ghost_target_pacman:
    ld a,(49805)
    ld (49842),a
    ld a,(49806)
    ld (49843),a
    jr ghost_rank_target
 ghost_target_ahead:
    ; Pinky targets 24 pixels ahead of Pac-Man's current direction.
    ld a,(49764)
    add a,a
    ld e,a
    ld d,0
    ld hl,ghost_lead_offsets
    add hl,de
    ld a,(49805)
    add a,(hl)
    ld (49842),a
    inc hl
    ld a,(49806)
    add a,(hl)
    ld (49843),a
    jr ghost_rank_target
 ghost_target_vector:
    ; Inky's NES target is 2*Pac-Man minus Blinky, with byte wrap.
    ld a,(49805)
    add a,a
    ld b,a
    ld a,(49808)
    ld c,a
    ld a,b
    sub c
    ld (49842),a
    ld a,(49806)
    add a,a
    ld b,a
    ld a,(49809)
    ld c,a
    ld a,b
    sub c
    ld (49843),a
 ghost_rank_target:
    ; NES builds an index from X sign, Y sign and dominant axis. Arithmetic
    ; here deliberately follows the original unsigned subtract/absolute value.
    ld e,0
    ld a,(49762)
    ld b,a
    ld a,(49842)
    sub b
    jr nc,ghost_rank_x_positive
    neg
    set 2,e
 ghost_rank_x_positive:
    ld (49844),a
    ld a,(49763)
    ld b,a
    ld a,(49843)
    sub b
    jr nc,ghost_rank_y_positive
    neg
    set 1,e
 ghost_rank_y_positive:
    ld b,a
    ld a,(49844)
    cp b
    jr nc,ghost_rank_index_ready
    set 0,e
 ghost_rank_index_ready:
    ld a,e
    add a,a
    ld e,a
    ld d,0
    ld hl,ghost_ranked_directions
    add hl,de
    ld a,(hl)
    ld (49848),a
    inc hl
    ld a,(hl)
    ld (49849),a
    ld a,(ix+2)
    dec a
    and 3
    ld (49850),a
    ld a,(ix+2)
    inc a
    and 3
    ld (49851),a
    jr ghost_try_candidates

; NES frightened/Clyde-near choice: scan directions seeded by frame counter,
; exclude reversal, and require a tile in the low 0..7 range.
ghost_seeded_choice:
    ld a,(49761)
    ld c,a
    ld b,4
 ghost_seeded_loop:
    inc c
    ld a,c
    and 3
    ld (49852),a
    push bc
    ld b,a
    ld a,(49847)
    cp b
    jr z,ghost_seeded_reject
    ld a,b
    call player_can_move
    jr nz,ghost_seeded_reject
    ld a,(hl)
    and 248
    jr nz,ghost_seeded_reject
    pop bc
    ld a,(49852)
    ld (ix+2),a
    xor a
    ret
 ghost_seeded_reject:
    pop bc
    djnz ghost_seeded_loop
    ; No accepted seeded choice: take the prototype's safe dead-end fallback.
    ld a,(49847)
    call player_can_move
    ret nz
    ld a,(49847)
    ld (ix+2),a
    xor a
    ret

ghost_corner_targets:
    defb 164,4,20,4,164,204,20,204
ghost_lead_offsets:
    defb 0,232,232,0,0,24,24,0
ghost_ranked_directions:
    defb 3,2,2,3,3,0,0,3,1,2,2,1,1,0,0,1

 ghost_try_candidates:
    ld hl,49848
    ld b,4
 ghost_candidate_loop:
    ld a,(hl)
    ld (49852),a
    push hl
    push bc
    ld b,a
    ld a,(49847)
    cp b
    jr z,ghost_candidate_reject
    ld a,b
    call player_can_move
    jr nz,ghost_candidate_reject
    pop bc
    pop hl
    ld a,(49852)
    ld (ix+2),a
    xor a
    ret
 ghost_candidate_reject:
    pop bc
    pop hl
    inc hl
    djnz ghost_candidate_loop
    ld a,(49847)
    call player_can_move
    ret nz
    ld a,(49847)
    ld (ix+2),a
    xor a
    ret

; Approximate collision radius. Eaten ghosts wait, then respawn in the maze.
ghost_collide:
    ld a,(ix+0)
    ld b,a
    ld a,(49805)
    sub b
    jr nc,ghost_dx_positive
    neg
 ghost_dx_positive:
    cp 7
    ret nc
    ld a,(ix+1)
    ld b,a
    ld a,(49806)
    sub b
    jr nc,ghost_dy_positive
    neg
 ghost_dy_positive:
    cp 7
    ret nc
    ld a,(49791)
    or a
    jr z,ghost_player_hit
    ; NES chain values in tens: 20, 40, 80, 160.
    ld a,(49792)
    cp 3
    jr c,ghost_combo_index_ready
    ld a,3
 ghost_combo_index_ready:
    ld e,a
    ld d,0
    ld hl,ghost_score_hundreds
    add hl,de
    ld a,(hl)
    ld (49783),a              ; pending hundreds digit
    ld a,e
    cp 3
    jr nz,ghost_score_ready
    ld a,1
    ld (49784),a              ; pending thousands digit
 ghost_score_ready:
    ld a,(49792)
    cp 3
    jr nc,ghost_combo_capped
    inc a
    ld (49792),a
 ghost_combo_capped:
    call game_commit_score
    ld (ix+0),52
    ld (ix+1),68
    ld (ix+2),1
    ld (ix+3),90
    ld a,40
    ld (49794),a
    ld a,1
    ld (49795),a
    ret
 ghost_score_hundreds:
    defb 2,4,8,6

ghost_player_hit:
    xor a
    ld (49771),a
    ld a,159
    out (127),a              ; stop chomp when play pauses
    ld a,(49790)
    or a
    ret z
    dec a
    ld (49790),a
    call game_draw_lives
    ld a,100
    ld (49794),a
    ld a,2
    ld (49795),a
    ld a,(49790)
    or a
    jr nz,ghost_respawn_player
    ld a,1
    ld (49804),a              ; game over returns to title after pause
    ld a,120
    ld (49793),a
    call game_show_over
    ret
 ghost_respawn_player:
    call game_reset_positions
    ld a,90
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

; Emit four sprites following Pac-Man at SAT 1B04. Rotate their order to share
; the TMS9918's four-sprites-per-scanline limit when all five actors overlap.
ghost_draw:
    ld a,(49761)
    rrca
    rrca
    rrca
    and 3
    ld (49840),a
    ld de,6916
    call set_vram_write
    ld b,4
 ghost_draw_loop:
    push bc
    ld a,(49840)
    add a,a
    add a,a
    add a,a
    ld e,a
    ld d,0
    ld hl,49808
    add hl,de
    push hl
    pop ix
    call ghost_draw_one
    ld a,(49840)
    inc a
    and 3
    ld (49840),a
    pop bc
    djnz ghost_draw_loop
    ld a,208
    out (190),a
    ret

ghost_draw_one:
    ld a,(ix+3)
    or a
    jp nz,ghost_draw_hidden
    ld a,(49760)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(ix+1)
    sub b
    jp c,ghost_draw_hidden
    cp 200
    jp nc,ghost_draw_hidden
    sub 9
    ld (49860),a              ; sprite Y, same for both layers
    out (190),a
    ld a,(ix+4)
    ld b,a                    ; body color, later possibly early clock
    ld a,(49791)
    or a
    jr z,ghost_draw_color_ready
    ld b,4                    ; frightened blue
    ld a,(49876)
    or a
    jr nz,ghost_draw_color_ready
    ld a,(49791)
    cp 60
    jr nc,ghost_draw_color_ready
    ld a,(49761)
    and 8
    jr z,ghost_draw_color_ready
    ld b,15                   ; flash near the end
 ghost_draw_color_ready:
    ld a,(ix+0)
    cp 8
    jr nc,ghost_draw_regular_x
    add a,24
    set 7,b                   ; early clock
    jr ghost_draw_x_ready
 ghost_draw_regular_x:
    sub 8
 ghost_draw_x_ready:
    ld (49861),a
    out (190),a
    ld a,b
    ld (49862),a              ; body color / early-clock flag
    ld a,(49761)
    and 8
    ld c,0
    jr z,ghost_draw_phase_ready
    inc c
 ghost_draw_phase_ready:
    ld a,(49791)
    or a
    jr z,ghost_draw_normal_pattern
    ld a,c
    add a,17                  ; 9 Pac frames + 8 directional ghost frames
    jr ghost_draw_pattern
 ghost_draw_normal_pattern:
    ld a,(ix+2)
    add a,a
    add a,c
    add a,9
 ghost_draw_pattern:
    add a,a
    add a,a
    ld (49863),a
    out (190),a
    ld a,(49862)
    out (190),a               ; body sprite (higher priority than its eyes)
    ld a,(49860)
    out (190),a
    ld a,(49861)
    out (190),a
    ld a,(49863)
    add a,40                  ; eye masks follow 10 body frames
    out (190),a
    ld a,(49862)
    and 128                   ; preserve early-clock bit
    ld b,a
    ld a,(49862)
    and 15
    cp 15
    ld a,15                   ; white eyes; red face when flashing white
    jr nz,ghost_eye_color_ready
    ld a,8
 ghost_eye_color_ready:
    or b
    out (190),a
    ret
 ghost_draw_hidden:
    ; Two hidden entries, not D0 (which terminates the entire sprite list).
    ld a,209
    out (190),a
    xor a
    out (190),a
    out (190),a
    out (190),a
    ld a,209
    out (190),a
    xor a
    out (190),a
    out (190),a
    out (190),a
    ret
