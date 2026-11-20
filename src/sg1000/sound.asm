; Independent SN76489 voices. Channel 0: pellet chomp (player.asm);
; channel 1: continuous ghost siren; channels 0/1: READY melody before play;
; channel 2: ghost eaten, fruit, extra-life, death, and level-clear tones. Channel 3/noise remains muted. Events share channel 2
; and replace one another, but cannot silence the chomp or the siren.
; This is an SG-1000 approximation, not a translation of the NES APU engine.
;
; C282 event remaining frames, C283 event kind (1=ghost, 2=death, 3=level,
; 4=fruit, 5=extra life).
sound_frame:
    ld a,(49904)
    or a
    jp nz,sound_ready_frame
    ; Siren, updated every four frames. Sweeping divisor varies the pitch.
    ld a,(49761)
    and 3
    jr nz,sound_event_tick
    ld a,(49761)
    and 31
    ld b,a
    ld a,(49761)
    and 32
    jr z,sound_siren_rising
    ld a,31
    sub b
    ld b,a
sound_siren_rising:
    ld a,(49791)
    or a
    jr z,sound_siren_normal
    ld a,b
    add a,208                 ; lower frightened-mode warble
    jr sound_siren_frequency
sound_siren_normal:
    ld a,b
    add a,150
sound_siren_frequency:
    ld b,a
    and 15
    or 160                    ; tone channel 1 latch
    out (127),a
    ld a,b
    rrca
    rrca
    rrca
    rrca
    and 15
    out (127),a
    ld a,185                  ; channel 1, low volume
    out (127),a
sound_event_tick:
    ld a,(49794)
    or a
    ret z
    dec a
    ld (49794),a
    jr nz,sound_event_active
    ld a,223                  ; mute channel 2 only
    out (127),a
    ret
sound_event_active:
    and 3
    ret nz
    ld a,(49794)
    and 31
    ld b,a
    ld a,(49795)
    cp 2
    jr z,sound_event_death
    cp 3
    jr z,sound_event_level
    cp 4
    jr z,sound_event_fruit
    cp 5
    jr z,sound_event_extra
    ld a,b
    add a,75                  ; eaten ghost
    jr sound_event_frequency
sound_event_fruit:
    ld a,b
    add a,a
    add a,55
    jr sound_event_frequency
sound_event_extra:
    ld a,b
    and 7
    add a,a
    add a,45
    jr sound_event_frequency
sound_event_death:
    ld a,b
    add a,a
    add a,130
    jr sound_event_frequency
sound_event_level:
    ld a,b
    rrca
    rrca
    and 7
    add a,90
sound_event_frequency:
    ld b,a
    and 15
    or 192                    ; tone channel 2 latch
    out (127),a
    ld a,b
    rrca
    rrca
    rrca
    rrca
    and 15
    out (127),a
    ld a,212                  ; channel 2 audible volume
    out (127),a
    ret

; The two READY voices are transcribed from the verified NES note streams.
; The NTSC APU and SN76489 clocks have equivalent tone divisors; volume and
; timbre are approximated. Records C2F1..C2F6 hold pointer and note timer.
sound_ready_init:
    ld a,250
    ld (49904),a
    ld hl,sound_ready_a
    ld (49905),hl
    ld hl,sound_ready_b
    ld (49908),hl
    xor a
    ld (49907),a
    ld (49910),a
    ret

sound_ready_frame:
    dec a
    ld (49904),a
    jr nz,sound_ready_play
    ld a,159
    out (127),a
    ld a,191
    out (127),a
    ret
 sound_ready_play:
    ld ix,49905
    ld c,128                  ; channel 0 latch
    ld e,148                  ; channel 0 volume
    call sound_ready_voice
    ld ix,49908
    ld c,160                  ; channel 1 latch
    ld e,184                  ; channel 1 volume
    jp sound_ready_voice

; Each entry is duration, divisor low nibble, divisor high six bits.
; Low=255 indicates a rest; zero duration terminates the stream.
sound_ready_voice:
    ld a,(ix+2)
    or a
    jr z,sound_ready_next
    dec a
    ld (ix+2),a
    ret nz
 sound_ready_next:
    ld l,(ix+0)
    ld h,(ix+1)
    ld a,(hl)
    or a
    jr z,sound_ready_rest
    ld (ix+2),a
    inc hl
    ld a,(hl)
    inc hl
    cp 255
    jr z,sound_ready_rest_advance
    or c
    out (127),a
    ld a,(hl)
    out (127),a
    ld a,e
    out (127),a
    jr sound_ready_store_pointer
 sound_ready_rest_advance:
    ld a,c
    add a,31
    out (127),a
 sound_ready_store_pointer:
    inc hl
    ld (ix+0),l
    ld (ix+1),h
    ret
 sound_ready_rest:
    ld a,c
    add a,31
    out (127),a
    ret

sound_ready_a:
    defb 8,11,26,8,5,13,8,13,17,8,3,21,7,5,13,7,13,17
    defb 12,3,21,6,255,0,8,3,25,8,9,12,8,13,16,8,0,20
    defb 7,9,12,7,13,16,12,0,20,6,255,0,8,11,26,8,5,13
    defb 8,13,17,8,3,21,7,5,13,7,13,17,12,3,21,6,255,0
    defb 5,7,22,5,3,21,5,0,20,5,0,20,5,14,18,5,13,17
    defb 5,13,17,5,13,16,5,14,15,12,5,13,0

sound_ready_b:
    defb 24,7,53,8,11,35,14,7,53,12,11,35,6,255,0,24,7,50
    defb 8,11,33,14,7,50,12,11,33,6,255,0,24,7,53,8,11,35
    defb 14,7,53,12,11,35,6,255,0,15,11,35,15,12,31,15,5,28
    defb 12,11,26,0
