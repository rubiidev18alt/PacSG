; SG-1000 maze/CHR diagnostics, not a game. Assembled with maze.asm and
; generated data tables by build_maze_viewer.py. Display a 24-row window onto
; the original 27-row NES tile map; joystick up/down scroll the window.
;
; TMS9918A Graphics II: pattern 0000, names 1800, sprites 1B00, colors 2000.
; 1 KiB SG-1000 RAM at C000-C3FF: map C000-C251, state C260, stack at C400.
    org 0
    di
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
    call display_on

frame_loop:
    ; Polling status acknowledges vblank; interrupts stay disabled.
wait_vblank:
    in a,(191)
    and 128
    jr z,wait_vblank
    ld a,(49761)
    or a
    jr z,read_pad
    dec a
    ld (49761),a
    jr frame_loop
read_pad:
    in a,(220)                 ; joystick 1, active low
    bit 0,a
    jr z,scroll_up
    bit 1,a
    jr z,scroll_down
    jr frame_loop
scroll_up:
    ld a,(49760)
    or a
    jr z,frame_loop
    dec a
    jr change_scroll
scroll_down:
    ld a,(49760)
    cp 3
    jr z,frame_loop
    inc a
change_scroll:
    ld (49760),a
    ld a,8
    ld (49761),a
    ; Avoid displaying a partially rewritten name table.
    ld a,128
    out (191),a
    ld a,129
    out (191),a
    call draw_maze
    call display_on
    jr frame_loop

display_on:
    ld a,192
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

; Draw 24 of the 27 decoded 22-tile rows, centered in a 32-column display.
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
    ld de,6149                 ; name table + five columns
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

vdp_registers:
    defb 2,128,6,255,3,54,7,1
