; Four SG-1000 ghost approximations. Each C290 record is eight bytes:
; X, Y, direction, release/respawn wait, color, speed fraction,
; state (0 active, 1 returning eyes, 2 recovered immune, 3 house,
; 4 exiting, 5 entering, 6 score popup), house direction/eyes-release flag.
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
    ld (49932),a              ; release inactivity ticks, low/high
    ld (49933),a
    ld (49934),a              ; current and next global release targets
    ld (49935),a
    ld (49936),a
    ld (49937),a              ; personal release / scatter mask latch
    ld (49938),a              ; NES frightened 60-frame divider
    ld (49946),a              ; active score pause countdown
    ld (49947),a              ; NES post-eat pause accumulator starts at zero
    ld (49950),a              ; reduced update flag
    call ghost_release_init
    call ghost_load_phase_duration
    ret

ghost_initial_records:
    ; NES world positions minus four pixels in each axis.
    defb 92,84,1,0,8,0,0,0      ; Blinky, outside house
    defb 92,108,0,0,13,0,3,0   ; Pinky
    defb 84,108,0,0,7,0,3,0    ; Inky
    defb 100,108,0,0,10,0,3,0  ; Clyde

; NES release-target quads: initial active count and pellet counts eaten.
; After a death use the NES special case, relative to already eaten dots.
ghost_release_init:
    ld a,(49788)
    cp 192
    jr z,ghost_release_fresh
    ld b,a
    ld a,192
    sub b
    ld b,a
    add a,7
    ld (49934),a
    ld a,b
    add a,17
    ld (49935),a
    ld a,b
    add a,32
    ld (49936),a
    ret
 ghost_release_fresh:
    ld a,(49789)
    cp 2
    jr z,ghost_release_round_two
    jr nc,ghost_release_later
    ld a,30
    ld (49934),a
    ld a,90
    ld (49935),a
    ld a,4
    ld (49822),a             ; Pinky starts exiting
    ret
 ghost_release_round_two:
    ld a,50
    ld (49934),a
    ld a,4
    ld (49822),a
    ld (49830),a
    ret
 ghost_release_later:
    ld a,4
    ld (49822),a
    ld (49830),a
    ld (49838),a
    ret

; One release at a matching global dot target or 3/4 * 96 idle frames.
ghost_release_tick:
    ld a,(49934)
    or a
    jr z,ghost_release_clock
    ld b,a
    ld a,(49788)
    add a,b
    cp 192
    jr nz,ghost_release_clock
    call ghost_release_next
    ld a,(49935)
    ld (49934),a
    ld a,(49936)
    ld (49935),a
    xor a
    ld (49936),a
 ghost_release_clock:
    ld hl,(49932)
    inc hl
    ld (49932),hl
    ld de,384               ; NES 96-tick divider * 4 seconds on rounds 1-2
    ld a,(49789)
    cp 3
    jr c,ghost_release_compare_time
    ld de,288               ; 3 seconds on later rounds
 ghost_release_compare_time:
    or a
    sbc hl,de
    ret c
    ld hl,0
    ld (49932),hl
    jp ghost_release_next

ghost_release_next:
    ld ix,49816
    ld b,3
 ghost_release_scan:
    ld a,(ix+6)
    cp 3
    jr nz,ghost_release_scan_next
    ld (ix+6),4
    ld (ix+7),0
    ret
 ghost_release_scan_next:
    ld de,8
    add ix,de
    djnz ghost_release_scan
    ret

 ; Convert NES frightened seconds/divider into the prototype's 255-frame
; blocks. The NES counts through zero, and a zero-duration stage initializes
; its divider to 30, giving a brief half-second frightened window.
ghost_start_frightened:
    xor a
    ld (49792),a              ; reset ghost chain
    ld a,(49789)
    cp 24
    jr c,ghost_fright_round_ok
    ld a,23
 ghost_fright_round_ok:
    dec a
    ld e,a
    ld d,0
    ld hl,ghost_fright_seconds
    add hl,de
    ld a,(hl)
    or a
    jr nz,ghost_fright_have_duration
    ld a,30
    ld (49938),a
    xor a
 ghost_fright_have_duration:
    inc a
    ld b,a
    ld hl,0
    ld de,60
 ghost_fright_seconds_loop:
    add hl,de
    djnz ghost_fright_seconds_loop
    ld a,(49938)
    ld c,a
    ld b,0
    or a
    sbc hl,bc
    ld b,0
 ghost_fright_split_loop:
    ld de,255
    or a
    sbc hl,de
    jr c,ghost_fright_split_done
    inc b
    jr ghost_fright_split_loop
 ghost_fright_split_done:
    add hl,de
    ld a,l
    or a
    jr nz,ghost_fright_store
    dec b
    ld a,255
 ghost_fright_store:
    ld (49791),a
    ld a,b
    ld (49876),a
    jp ghost_frighten
; Seconds from the stage-index stream (counter includes zero).
ghost_fright_seconds:
    defb 7,6,4,3,2,5,2,2,1,5,2,1
    defb 1,3,1,1,0,1,0,0,0,0,0

; Reverse released ghosts immediately on a power pellet, as the NES does.
ghost_frighten:
ghost_reverse_all:
    ld ix,49808
    ld b,4
 ghost_frighten_loop:
    ld a,(ix+3)
    or a
    jr nz,ghost_frighten_next
    ld a,(ix+6)
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
    xor a
    ld (49950),a
    call ghost_mode_tick
    call ghost_release_tick
    jr ghost_frame_common

; During the score freeze, only pre-existing returning eyes get movement.
ghost_eyes_frame:
    ld a,1
    ld (49950),a
 ghost_frame_common:
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
    ld a,(49950)
    or a
    jr z,ghost_full_slot
    ld a,(ix+6)
    cp 1
    jp nz,ghost_next
 ghost_full_slot:
    ld a,(ix+3)
    or a
    jr z,ghost_released
    dec a
    ld (ix+3),a
    jp ghost_next
 ghost_released:
    ld a,(ix+6)
    cp 3
    jp z,ghost_house_bounce
    cp 4
    jp z,ghost_house_exit
    cp 5
    jp z,ghost_house_enter
    cp 6
    jp z,ghost_next
    cp 2
    jr nz,ghost_check_returning
    ld a,(49791)
    or a
    jr nz,ghost_fractional_move
    ld (ix+6),0
    jr ghost_fractional_move
 ghost_check_returning:
    cp 1
    jr nz,ghost_fractional_move
    ld a,(ix+0)
    cp 92
    jp nz,ghost_move
    ld a,(ix+1)
    cp 84
    jp nz,ghost_move
    ; Eyes enter through the door, then re-emerge via the house handler.
    ld (ix+6),5
    ld (ix+7),1
    jp ghost_next
 ghost_fractional_move:
    ; Fixed-point speed has an integer byte and a fractional byte.
    call ghost_speed_fraction
    add a,(ix+5)
    ld (ix+5),a
    ld b,0
    jr nc,ghost_no_fractional_carry
    inc b
 ghost_no_fractional_carry:
    ld a,(49928)
    add a,b
    jp z,ghost_check_collision
    ld (49927),a
    jp ghost_move_substep
 ghost_move:
    ld a,2                    ; original returning-eyes speed: two pixels
    ld (49927),a
 ghost_move_substep:
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
    jr ghost_step_complete
 ghost_step_up:
    dec (ix+1)
    jr ghost_step_complete
 ghost_step_down:
    inc (ix+1)
 ghost_step_complete:
    ld a,(49927)
    dec a
    ld (49927),a
    jr z,ghost_restore_position
    ld a,(ix+6)
    cp 1
    jr nz,ghost_more_substeps
    ld a,(ix+0)
    cp 92
    jr nz,ghost_more_substeps
    ld a,(ix+1)
    cp 84
    jr z,ghost_restore_position
 ghost_more_substeps:
    jp ghost_move_substep
 ghost_restore_position:
    ld a,(49805)
    ld (49762),a
    ld a,(49806)
    ld (49763),a
 ghost_check_collision:
    call ghost_collide
 ghost_next:
    pop bc
    ld a,(49950)
    or a
    jr nz,ghost_next_slot      ; reduced update continues through all eyes
    ld a,(49793)
    or a
    jr nz,ghost_frame_done     ; death/respawn pause was started
    ld a,(49946)
    or a
    jr nz,ghost_frame_done     ; stop immediately after one ghost is eaten
 ghost_next_slot:
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

; House movement is half a pixel per frame, independent of maze wall probes.
; In-house ghosts bounce between the NES bounds 69h..70h (minus four).
ghost_house_bounce:
    ld a,(49761)
    and 1
    jp nz,ghost_next
    ld a,(ix+7)
    or a
    jr nz,ghost_house_bounce_down
    dec (ix+1)
    ld a,(ix+1)
    cp 101
    jp nc,ghost_next
    ld (ix+7),1
    ld (ix+2),2
    jp ghost_next
 ghost_house_bounce_down:
    inc (ix+1)
    ld a,(ix+1)
    cp 108
    jp c,ghost_next
    ld (ix+7),0
    ld (ix+2),0
    jp ghost_next

ghost_house_exit:
    ld a,(49761)
    and 1
    jp nz,ghost_next
    ld a,(ix+0)
    cp 92
    jr z,ghost_exit_up
    jr c,ghost_exit_right
    dec (ix+0)
    ld (ix+2),1
    jp ghost_next
 ghost_exit_right:
    inc (ix+0)
    ld (ix+2),3
    jp ghost_next
 ghost_exit_up:
    ld (ix+2),0
    dec (ix+1)
    ld a,(ix+1)
    cp 84
    jp nz,ghost_next
    ld (ix+2),1
    ld a,(ix+7)
    or a
    jr z,ghost_exit_initial
    ld (ix+6),2             ; recovered ghosts are not frightened again
    ld (ix+7),0
    jp ghost_next
 ghost_exit_initial:
    ld (ix+6),0
    jp ghost_next

ghost_house_enter:
    inc (ix+1)
    inc (ix+1)
    ld (ix+2),2
    ld a,(ix+1)
    cp 108
    jp c,ghost_next
    ld (ix+1),108
    ld (ix+6),4
    jp ghost_next

; NTSC ghost speeds and Blinky thresholds copied from stage_parameters.asm.
; Return fraction in A, integer pixels in C308h (49928).
ghost_speed_fraction:
    xor a
    ld (49928),a
    ld a,(ix+1)
    cp 108
    jr nz,ghost_check_fright_speed
    ld a,(ix+0)
    cp 44
    jr c,ghost_slow_fraction
    cp 140
    jr nc,ghost_slow_fraction
 ghost_check_fright_speed:
    ld a,(ix+6)
    or a
    jr nz,ghost_normal_fraction
    ld a,(49791)
    or a
    jr nz,ghost_slow_fraction
 ghost_normal_fraction:
    ; Choose one of five NTSC profiles and the level's threshold pair.
    ld a,(49789)
    cp 24
    jr c,ghost_speed_round_ok
    ld a,23
 ghost_speed_round_ok:
    dec a
    ld e,a
    ld d,0
    ld hl,ghost_speed_stage_offsets
    add hl,de
    ld a,(hl)
    ld (49929),a             ; offset into six-byte speed profile
    ld a,(49807)
    or a
    jr nz,ghost_speed_normal_slot
    ld hl,ghost_blinky_thresholds
    add hl,de
    add hl,de
    ld a,(49788)
    cp (hl)
    jr nc,ghost_speed_normal_slot
    inc hl
    cp (hl)
    ld a,2                   ; first boost offset
    jr nc,ghost_speed_boost_ready
    ld a,4                   ; second boost offset
    jr ghost_speed_boost_ready
 ghost_speed_normal_slot:
    xor a
 ghost_speed_boost_ready:
    ld b,a
    ld a,(49929)
    add a,b
    ld e,a
    ld d,0
    ld hl,ghost_speed_profiles
    add hl,de
    ld a,(hl)
    inc hl
    ld b,a
    ld a,(hl)
    ld (49928),a
    ld a,b
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
; Per round, offsets for profile 0,1,2,3,4.
ghost_speed_stage_offsets:
    defb 0,6,6,12,12,18,18,18,18,18,18,18
    defb 18,18,18,18,18,18,18,18,18,24,24
; Comparison is remaining dots < threshold+1, first then second.
ghost_blinky_thresholds:
    defb 21,11,31,16,41,21,41,21,41,21
    defb 51,26,51,26,51,26,61,31,61,31
    defb 61,31,81,41,81,41,81,41,101,51,101,51
    defb 101,51,101,51,101,51,101,51,101,51,101,51,101,51
; normal, first boost, second boost as fraction/whole-byte pairs.
ghost_speed_profiles:
    defb 144,0,160,0,176,0
    defb 160,0,176,0,192,0
    defb 208,0,224,0,240,0
    defb 240,0,0,1,16,1
    defb 16,1,32,1,48,1

; Round-driven scatter/chase schedule based on the NES timer tables. The
; divider pauses during frightened mode. Reversals use the shared helper.
ghost_mode_tick:
    ; The NES latches slot zero into chase after a personal dot threshold.
    ld a,(49937)
    or a
    jr nz,ghost_mode_latch_ready
    ld a,(49789)
    cp 24
    jr c,ghost_latch_round_ok
    ld a,23
 ghost_latch_round_ok:
    dec a
    add a,a
    ld e,a
    ld d,0
    ld hl,ghost_blinky_thresholds
    add hl,de
    ld a,(49788)
    inc a
    cp (hl)
    jr z,ghost_set_personal_latch
    inc hl
    cp (hl)
    jr nz,ghost_mode_latch_ready
 ghost_set_personal_latch:
    ld a,1
    ld (49937),a
 ghost_mode_latch_ready:
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
    cp 255                    ; NES decrements through zero before advancing
    ret nz
    ld a,(49872)
    cp 7
    ret nc
    inc a
    ld (49872),a
    call ghost_load_phase_duration
    ld a,(49872)
    and 1
    ret z                    ; NES only reverses on odd phase transitions
    jp ghost_reverse_all
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
    ld a,(ix+6)
    cp 1
    jr nz,ghost_choose_not_eyes
    ; Eyes may reverse and follow a maze-specific shortest route to the
    ; entrance; greedy targeting can loop forever around the central walls.
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
    ld de,49152
    or a
    sbc hl,de
    ld de,ghost_eye_routes
    add hl,de
    ld a,(hl)
    cp 4
    jr nc,ghost_eyes_no_route
    ld (ix+2),a
    xor a
    ret
 ghost_eyes_no_route:
    ld a,92
    ld (49842),a
    ld a,84
    ld (49843),a
    jp ghost_rank_target
 ghost_choose_not_eyes:
    or a
    jr nz,ghost_choose_normal_mode
    ld a,(49791)
    or a
    jp nz,ghost_seeded_choice
 ghost_choose_normal_mode:
    ld a,(49872)
    and 1
    jr nz,ghost_chase_target
    ld a,(49937)
    or a
    jr z,ghost_scatter_target
    ld a,(49807)
    or a
    jr z,ghost_chase_target   ; latched mode mask is bit 0
 ghost_scatter_target:
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
    ld a,(hl)                 ; active NES ghosts accept tiles 00..07
    and 248
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

; Approximate collision radius. Eaten ghosts become returning eyes.
ghost_collide:
    ld a,(ix+6)
    cp 1
    ret z
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
    ld a,(ix+6)
    or a
    jr nz,ghost_player_hit
    ld a,(49791)
    or a
    jr z,ghost_player_hit
    ; NES chain values in tens: 20, 40, 80, 160.
    ld a,(49792)
    cp 3
    jr c,ghost_combo_index_ready
    ld a,3
 ghost_combo_index_ready:
    ld (49949),a              ; popup index before chain increments
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
    ld (ix+6),6               ; NES eaten-score state until pause completes
    ld (ix+5),0
    ld a,(49807)
    ld (49948),a              ; retain eaten slot
    ld a,(49947)
    ld b,a
    ld a,40
    sub b                     ; first pause 40 frames, subsequent pauses 38
    ld (49946),a
    call ghost_popup_draw
    ld a,40
    ld (49794),a
    ld a,1
    ld (49795),a
    ret
 ghost_score_hundreds:
    defb 2,4,8,6

ghost_player_hit:
    jp game_death_start

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
    call fruit_draw
    ld a,208
    out (190),a
    ret

ghost_draw_one:
    ld a,(ix+6)
    cp 6
    jp z,ghost_draw_hidden
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
    ld (49860),a              ; screen Y for the eye layer
    ld a,(ix+6)
    cp 1
    jr z,ghost_draw_hide_body_y
    cp 5
    ld a,(49860)
    jr nz,ghost_draw_body_y_ready
    jr ghost_draw_hide_body_y
 ghost_draw_hide_body_y:
    ld a,209                  ; returning eyes use only one scanline slot
 ghost_draw_body_y_ready:
    out (190),a
    ld a,(ix+4)
    ld b,a                    ; body color, later possibly early clock
    ld a,(ix+6)
    cp 1
    jr z,ghost_draw_eyes_body
    cp 5
    jr z,ghost_draw_eyes_body
    cp 2
    jr z,ghost_draw_color_ready
    cp 4
    jr nz,ghost_draw_check_frightened
    ld a,(ix+7)
    or a
    jr z,ghost_draw_check_frightened
    jr ghost_draw_color_ready
 ghost_draw_eyes_body:
    ld b,0                    ; transparent body, keep eye sprite
    jr ghost_draw_color_ready
 ghost_draw_check_frightened:
    ld a,(49791)
    or a
    jr z,ghost_draw_color_ready
    ld b,4                    ; frightened blue
    ld a,(49876)
    or a
    jr nz,ghost_draw_color_ready
    ld a,(49791)
    cp 120                    ; NES flashes during the final two seconds
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
    ld a,(ix+6)
    cp 1
    jr z,ghost_draw_normal_pattern
    cp 2
    jr z,ghost_draw_normal_pattern
    cp 5
    jr z,ghost_draw_normal_pattern
    cp 4
    jr nz,ghost_draw_pattern_check_frightened
    ld a,(ix+7)
    or a
    jr nz,ghost_draw_normal_pattern
 ghost_draw_pattern_check_frightened:
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
