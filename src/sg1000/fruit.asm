; Fruit timer C2EC-C2ED (16-bit frames). Two NES-derived sprite layers
; follow the ghost SAT entries, avoiding destructive maze tile overlays.
fruit_spawn:
    ld hl,660                 ; NES timer 0A:3C = 11 seconds at 60 Hz
    ld (49900),hl
    ret

fruit_tick:
    ld hl,(49900)
    ld a,h
    or l
    ret z
    dec hl
    ld (49900),hl
    ld a,h
    or l
    ret z
    ; World position NES $60,$80 translated into local maze coordinates.
    ld a,(49762)
    sub 92
    jr nc,fruit_x_positive
    neg
 fruit_x_positive:
    cp 7
    ret nc
    ld a,(49763)
    sub 124
    jr nc,fruit_y_positive
    neg
 fruit_y_positive:
    cp 7
    ret nc
    xor a
    ld (49900),a
    ld (49901),a
    call fruit_stage_index
    add a,a
    ld e,a
    ld d,0
    ld hl,fruit_awards
    add hl,de
    ld a,(hl)
    ld (49783),a              ; hundreds digit
    inc hl
    ld a,(hl)
    ld (49784),a              ; thousands digit
    call game_commit_score
    ld a,40
    ld (49794),a
    ld a,4
    ld (49795),a
    ret

; Round -> NES fruit group: cherry, strawberry, orange, apple, melon,
; Galaxian, bell, key; round 13 and later use the key.
fruit_stage_index:
    ld a,(49789)
    cp 13
    jr c,fruit_stage_in_range
    ld a,13
 fruit_stage_in_range:
    dec a
    ld e,a
    ld d,0
    ld hl,fruit_stage_table
    add hl,de
    ld a,(hl)
    ret
fruit_stage_table:
    defb 0,1,2,2,3,3,4,4,5,5,6,6,7
fruit_awards:
    defb 1,0,3,0,5,0,7,0,0,1,0,2,0,3,0,5
fruit_body_colors:
    defb 8,8,9,8,3,11,11,15

; Called at end of ghost_draw with the VDP SAT write address still selected.
fruit_draw:
    ld hl,(49900)
    ld a,h
    or l
    ret z
    ld a,(49760)
    add a,a
    add a,a
    add a,a
    ld b,a
    ld a,115                  ; top Y=124-8, VDP coordinate is one less
    sub b
    ld (49902),a
    out (190),a
    ld a,84                   ; top X=92-8
    out (190),a
    call fruit_stage_index
    ld (49903),a
    add a,29                  ; fruit masks start after 29 16x16 patterns
    add a,a
    add a,a
    out (190),a
    ld a,3                    ; green leaves/stems (NES palette approximated)
    out (190),a
    ld a,(49902)
    out (190),a
    ld a,84
    out (190),a
    ld a,(49903)
    add a,37                  ; second eight-pattern layer
    add a,a
    add a,a
    out (190),a
    ld a,(49903)
    ld e,a
    ld d,0
    ld hl,fruit_body_colors
    add hl,de
    ld a,(hl)
    out (190),a
    ret

; NES shows up to seven stage fruit icons, four on the first row and three
; on the next. The SG-1000 HUD puts these at rows 12-15 to leave room for
; spare lives and the round counter. Tiles are background graphics, so the
; icons do not compete with actors for the four-sprites-per-scanline limit.
fruit_draw_history:
    ld a,(49789)              ; round, 1-based
    or a
    ret z
    cp 8
    jr c,fruit_history_short
    sub 7                     ; zero-based oldest stage for seven icons
    cp 13
    jr c,fruit_history_start_ready
    ld a,12                   ; stage 13 onward is always the key
 fruit_history_start_ready:
    ld c,a
    ld b,7
    jr fruit_history_loop_init
 fruit_history_short:
    ld b,a
    ld c,0
 fruit_history_loop_init:
    ld ix,fruit_history_addresses
 fruit_history_loop:
    push bc
    ld a,c
    cp 13
    jr c,fruit_history_stage_ready
    ld a,12
 fruit_history_stage_ready:
    ld e,a
    ld d,0
    ld hl,fruit_stage_table
    add hl,de
    ld a,(hl)
    add a,a
    add a,a
    add a,192                ; each fruit occupies four HUD tile IDs
    push af
    ld e,(ix+0)
    ld d,(ix+1)
    call set_vram_write
    pop af
    push af
    out (190),a              ; top left
    inc a
    out (190),a              ; top right
    ld e,(ix+0)
    ld d,(ix+1)
    ld hl,32
    add hl,de
    ex de,hl
    call set_vram_write
    pop af
    add a,2
    out (190),a              ; bottom left
    inc a
    out (190),a              ; bottom right
    inc ix
    inc ix
    pop bc
    inc c
    djnz fruit_history_loop
    ret
fruit_history_addresses:
    defw 6550,6552,6554,6556,6614,6616,6618
