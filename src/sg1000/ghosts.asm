; Four SG-1000 ghost approximations. Each C290 record is eight bytes:
; X, Y, direction, release/respawn wait, TMS color, three reserved bytes.
; Ghosts use NES-derived sprite masks; eyes are transparent because each TMS
; sprite has one color. The four-sprites-per-scanline limit is mitigated by
; rotating ghost priority. This is not the original NES AI or house sequence.
;
; C28D/E save Pac-Man XY while using player_can_move for ghost tile probes;
; C28F ghost index; C2B0/C2B1 drawing/loop work; C2B7 opposite direction;
; C2B8-BB candidate list; C2BC temporary candidate.

ghost_init:
    ld hl,ghost_initial_records
    ld de,49808
    ld bc,32
    ldir
    ret

ghost_initial_records:
    defb 52,68,1,0,8,0,0,0      ; red
    defb 132,68,3,45,13,0,0,0   ; pink
    defb 52,148,1,90,7,0,0,0    ; cyan
    defb 132,148,3,135,10,0,0,0 ; orange

; Reverse released ghosts immediately on a power pellet, as the NES does.
ghost_frighten:
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
    ; Normal ghosts move every other frame, frightened ghosts every fourth.
    ld a,(49791)
    or a
    ld a,(49761)
    jr z,ghost_normal_speed
    and 3
    jr nz,ghost_check_collision
    jr ghost_move
 ghost_normal_speed:
    and 1
    jr nz,ghost_check_collision
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

; Choose a legal non-reverse direction. Prefer moving toward Pac-Man, with
; alternating axis priority by ghost; while frightened prefer moving away.
; If there is no non-reverse exit, reverse at a dead end. Z means a move exists.
ghost_choose_direction:
    ld a,(ix+2)
    xor 2
    ld (49847),a
    ld a,(49762)
    ld b,a
    ld a,(49805)
    cp b
    ld a,3                    ; toward right
    jr nc,ghost_horizontal_ready
    ld a,1                    ; toward left
 ghost_horizontal_ready:
    ld b,a
    ld a,(49791)
    or a
    ld a,b
    jr z,ghost_horizontal_store
    xor 2                     ; flee
 ghost_horizontal_store:
    ld (49842),a
    ld a,(49763)
    ld b,a
    ld a,(49806)
    cp b
    ld a,2                    ; toward down
    jr nc,ghost_vertical_ready
    xor a                     ; toward up
 ghost_vertical_ready:
    ld b,a
    ld a,(49791)
    or a
    ld a,b
    jr z,ghost_vertical_store
    xor 2
 ghost_vertical_store:
    ld (49843),a
    ; Alternate which axis is tested first so ghosts don't all choose alike.
    ld a,(49807)
    and 1
    jr nz,ghost_vertical_first
    ld a,(49842)
    ld (49848),a
    xor 2
    ld (49851),a
    ld a,(49843)
    ld (49849),a
    xor 2
    ld (49850),a
    jr ghost_try_candidates
 ghost_vertical_first:
    ld a,(49843)
    ld (49848),a
    xor 2
    ld (49851),a
    ld a,(49842)
    ld (49849),a
    xor 2
    ld (49850),a
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
    jr nz,ghost_draw_hidden
    ld a,(49760)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,(ix+1)
    sub b
    jr c,ghost_draw_hidden
    cp 200
    jr nc,ghost_draw_hidden
    sub 9
    out (190),a
    ld a,(ix+4)
    ld b,a                    ; sprite color, later possibly early clock
    ld a,(49791)
    or a
    jr z,ghost_draw_color_ready
    ld b,4                    ; frightened blue
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
    out (190),a
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
    out (190),a
    ld a,b
    out (190),a
    ret
 ghost_draw_hidden:
    ld a,209                  ; off-screen, not the D0 end-of-list marker
    out (190),a
    xor a
    out (190),a
    out (190),a
    out (190),a
    ret
