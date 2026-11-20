; SG-1000 Pac-Man prototype. Assembled with maze, player, game, ghost, sound
; and score modules plus ROM-derived graphics by build_maze_viewer.py. Fire starts;
; joystick controls Pac-Man. The viewport follows him vertically.
;
; TMS9918A Graphics II: pattern 0000, names 1800, sprites 1B00, colors 2000.
; 1 KiB SG-1000 RAM at C000-C3FF: map C000-C251, state C260, stack at C400.
    org 0
    di
    ; Stop all PSG channels on power-up and on the game-over title return.
    ld a,159
    out (127),a
    ld a,191
    out (127),a
    ld a,223
    out (127),a
    ld a,255
    out (127),a
    ld sp,50176                ; C400h, stack grows down
    ld hl,maze_data
    ld de,49152                ; C000h
    call decode_maze
    xor a
    ld (49760),a               ; C260h camera row
    ld (49761),a               ; C261h scroll repeat counter

    ; Display disabled while initializing VRAM. R1=80 selects 16 KiB RAM.
    ld hl,vdp_registers
    ld b,8
    ld c,0
setup_register_loop:
    ld a,(hl)
    out (191),a
    ld a,c
    or 128
    out (191),a
    inc hl
    inc c
    djnz setup_register_loop

    ; Hide sprites and display the title using its own Graphics II banks.
    ld de,6912
    call set_vram_write
    ld a,208
    out (190),a
    ld de,0
    call set_vram_write
    ld hl,title_pattern_data
    ld bc,6144
    call write_vram_block
    ld de,8192
    call set_vram_write
    ld hl,title_color_data
    ld bc,6144
    call write_vram_block
    ld de,6144
    call set_vram_write
    ld hl,title_name_data
    ld bc,768
    call write_vram_block
    call display_on

wait_start:
    in a,(191)
    and 128
    jr z,wait_start
    in a,(220)
    and 48                      ; either fire button, active low
    cp 48
    jr z,wait_start
    ; Switch to the maze tiles while display is off.
    ld a,128
    out (191),a
    ld a,129
    out (191),a

    ; Three Graphics II 256-pattern banks all use the same NES tile set.
    ld de,0
    ld b,3
pattern_bank_loop:
    push bc
    push de
    call set_vram_write
    ld hl,pattern_data
    ld bc,2048
    call write_vram_block
    pop de
    ld hl,2048
    add hl,de
    ex de,hl
    pop bc
    djnz pattern_bank_loop
    ld de,8192
    ld b,3
color_bank_loop:
    push bc
    push de
    call set_vram_write
    ld hl,color_data
    ld bc,2048
    call write_vram_block
    pop de
    ld hl,2048
    add hl,de
    ex de,hl
    pop bc
    djnz color_bank_loop

    ; Load pre-flipped 16x16 Pac-Man sprite frames into the TMS sprite table.
    ld de,14336
    call set_vram_write
    ld hl,pacman_sprite_data
    ld bc,608
    call write_vram_block
    call player_init
    call game_init

    ; Clear the name table, including the horizontal margins.
    ld de,6144
    call set_vram_write
    ld bc,768
clear_names_loop:
    ld a,45                    ; NES blank tile
    out (190),a
    dec bc
    ld a,b
    or c
    jr nz,clear_names_loop
    ; D0 ends the sprite list.
    ld de,6912
    call set_vram_write
    ld a,208
    out (190),a
    call draw_maze
    call draw_hud
    call game_draw_high
    call game_draw_lives
    call game_draw_round
    call player_draw_score
    call player_draw_sprite
    call ghost_draw
    call display_on

frame_loop:
    ; Polling status acknowledges vblank; interrupts stay disabled.
wait_vblank:
    in a,(191)
    and 128
    jr z,wait_vblank
    call game_frame
    jp frame_loop

display_on:
    ld a,194
    out (191),a
    ld a,129
    out (191),a
    ret

; DE = VRAM address, clobbers AF.
set_vram_write:
    ld a,e
    out (191),a
    ld a,d
    or 64
    out (191),a
    ret

; HL = source, BC = count (must be nonzero).
write_vram_block:
    ld a,(hl)
    out (190),a
    inc hl
    dec bc
    ld a,b
    or c
    jr nz,write_vram_block
    ret

; Draw 24 of the 27 decoded 22-tile rows on the left; HUD occupies columns 22..31.
draw_maze:
    ld ix,49152
    ld a,(49760)
    or a
    jr z,maze_window_ready
    ld de,22
maze_window_skip:
    add ix,de
    dec a
    jr nz,maze_window_skip
maze_window_ready:
    ld de,6144                 ; name table, left edge
    ld b,24
maze_screen_row:
    push bc
    push de
    call set_vram_write
    ld c,22
maze_screen_tile:
    ld a,(ix+0)
    out (190),a
    inc ix
    dec c
    jr nz,maze_screen_tile
    pop de
    ld hl,32
    add hl,de
    ex de,hl
    pop bc
    djnz maze_screen_row
    ret

; HUD: score, high score, spare lives and round are updated separately.
; Ten columns starting at x=22, untouched by maze redraw/scrolling.
draw_hud:
    ld de,6198                  ; row 1, column 22: NES HIGH SCORE placement
    call set_vram_write
    ld hl,hud_high
    ld bc,10
    call write_vram_block
    ld de,6326                  ; row 5: 1UP
    call set_vram_write
    ld hl,hud_1up
    ld bc,10
    call write_vram_block
    ld de,6806                  ; row 20: round number
    call set_vram_write
    ld hl,hud_round
    ld bc,10
    call write_vram_block
    ret

; Each row is 10 tile IDs; 32 is NES space.
hud_1up:   defb 176,179,178,32,32,32,32,32,32,32
hud_zero:  defb 48,48,32,32,32,32,32,32,32,32
hud_high:  defb 180,181,182,183,184,185,186,187,32,32
hud_round: defb 82,79,85,78,68,32,32,32,32,32

vdp_registers:
    defb 2,128,6,255,3,54,7,1
