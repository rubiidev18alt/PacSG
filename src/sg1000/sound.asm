; Independent SN76489 voices. Channel 0: pellet chomp (player.asm);
; channel 1: NES-derived looping ghost/eyes/frightened sequences; channels 0/1: READY melody before play;
; channel 2: ghost eaten, fruit, extra-life, and death tones. Channel 3/noise remains muted. Events share channel 2
; and replace one another, but cannot silence the chomp or the siren.
; This is an SG-1000 approximation, not a translation of the NES APU engine.
;
; C282 event remaining frames, C283 event kind (1=ghost, 2=death, 3=level,
; 4=fruit, 5=extra life).
sound_frame:
    ld a,(49904)
    or a
    jp nz,sound_ready_frame
    ld a,(49939)
    cp 2
    jr z,sound_event_tick     ; silence siren during death animation
    ; Use the NES's priority: returning eyes, frightened, then three
    ; pellet-count bands. Each one-frame note sequence loops on PSG tone 1.
    call sound_siren_tick
sound_event_tick:
    ; Start/restart an event when its kind changes or its frame counter is
    ; reloaded. The source streams run to their own F0 terminators.
    ld a,(49794)
    or a
    jr z,sound_event_no_request
    ld b,a
    ld a,(49915)
    cp b
    jr c,sound_event_start
    ld a,(49795)
    ld b,a
    ld a,(49914)
    cp b
    jr z,sound_event_countdown
 sound_event_start:
    ld a,(49795)
    ld (49914),a
    ld hl,sfx_ghost
    cp 1
    jr z,sound_event_stream_ready
    ld hl,sfx_death
    cp 2
    jr z,sound_event_stream_ready
    ld hl,sfx_fruit
    cp 4
    jr z,sound_event_stream_ready
    ld hl,sfx_extra
    cp 5
    jr z,sound_event_stream_ready
    ; No corresponding NES sound stream for the level-clear cue.
    ld a,223
    call sound_write_volume
    ld hl,0
 sound_event_stream_ready:
    ld (49911),hl
    xor a
    ld (49913),a
 sound_event_countdown:
    ld a,(49794)
    dec a
    ld (49794),a
    ld (49915),a
    jr sound_event_play
 sound_event_no_request:
    xor a
    ld (49915),a
 sound_event_play:
    ld hl,(49911)
    ld a,h
    or l
    jr z,sound_chomp_tick
    ld ix,49911
    ld c,192
    ld e,212
    call sound_ready_voice
 sound_chomp_tick:
    ld hl,(49916)
    ld a,h
    or l
    ret z
    ld ix,49916
    ld c,128
    ld e,148
    jp sound_ready_voice

sound_siren_tick:
    ld hl,49814               ; ghost record state byte
    ld de,8
    ld b,4
 sound_siren_scan_eyes:
    ld a,(hl)
    cp 1
    jr z,sound_siren_eyes
    cp 5
    jr z,sound_siren_eyes
    add hl,de
    djnz sound_siren_scan_eyes
    ld a,(49791)
    or a
    jr nz,sound_siren_frightened
    ld a,(49788)
    cp 136
    jr nc,sound_siren_high
    cp 66
    jr nc,sound_siren_mid
    ld a,4
    ld hl,sfx_siren_low
    jr sound_siren_select
 sound_siren_eyes:
    xor a
    ld hl,sfx_eyes
    jr sound_siren_select
 sound_siren_frightened:
    ld a,1
    ld hl,sfx_frightened
    jr sound_siren_select
 sound_siren_high:
    ld a,2
    ld hl,sfx_siren_high
    jr sound_siren_select
 sound_siren_mid:
    ld a,3
    ld hl,sfx_siren_mid
 sound_siren_select:
    ld b,a
    ld a,(49926)
    cp b
    jr nz,sound_siren_restart
    ld de,(49923)
    ld a,d
    or e
    jr nz,sound_siren_play
 sound_siren_restart:
    ld a,b
    ld (49926),a
    ld (49923),hl
    xor a
    ld (49925),a
 sound_siren_play:
    ld ix,49923
    ld c,160
    ld e,185
    jp sound_ready_voice

; A is remaining dot count; original streams alternate on parity.
sound_start_chomp:
    and 1
    ld hl,sfx_pellet_even
    jr z,sound_chomp_stream_ready
    ld hl,sfx_pellet_odd
 sound_chomp_stream_ready:
    ld (49916),hl
    xor a
    ld (49918),a
    ret

sound_stop_chomp:
    xor a
    ld (49916),a
    ld (49917),a
    ld (49918),a
    ld a,159
    jp sound_write_volume

; The two READY voices are compiled from the verified NES note streams.
; The NTSC APU and SN76489 clocks have equivalent tone divisors; volume and
; timbre are approximated. Records C2F1..C2F6 hold pointer and note timer.
sound_ready_init:
    ld a,250
    ld (49904),a
    ld hl,sfx_ready_a
    ld (49905),hl
    ld hl,sfx_ready_b
    ld (49908),hl
    xor a
    ld (49907),a
    ld (49910),a
    ld hl,49911
    ld b,16
 sound_clear_event_state:
    ld (hl),a
    inc hl
    djnz sound_clear_event_state
    ld a,255
    ld (49926),a
    ld a,159
    ld (49951),a
    ld a,191
    ld (49952),a
    ld a,223
    ld (49953),a
    ret

sound_ready_frame:
    dec a
    ld (49904),a
    jr nz,sound_ready_play
    ld a,159
    call sound_write_volume
    ld a,191
    jp sound_write_volume
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
; Low=255 holds the previous output (NES C0-EF); zero duration stops.
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
    jr z,sound_ready_hold_advance
    or c
    out (127),a
    ld a,(hl)
    out (127),a
    ld a,e
    call sound_write_volume
    jr sound_ready_store_pointer
 sound_ready_hold_advance:
 sound_ready_store_pointer:
    inc hl
    ld (ix+0),l
    ld (ix+1),h
    ret
 sound_ready_rest:
    xor a
    ld (ix+0),a
    ld (ix+1),a
    ld a,c
    add a,31
    jp sound_write_volume

; Track the last volume latch for each tone. The PSG keeps its frequency
; registers during the score freeze, so restoring these latches resumes the
; exact held notes without advancing any stream. A is preserved.
sound_write_volume:
    out (127),a
    cp 176
    jr c,sound_volume_0
    cp 208
    jr c,sound_volume_1
    ld (49953),a
    ret
 sound_volume_0:
    ld (49951),a
    ret
 sound_volume_1:
    ld (49952),a
    ret

sound_freeze:
    ; Do not modify the saved volume latches while muting the hardware.
    ld a,159
    out (127),a
    ld a,191
    out (127),a
    ld a,223
    out (127),a
    ld a,255
    out (127),a
    ret

sound_unfreeze:
    ld a,(49951)
    out (127),a
    ld a,(49952)
    out (127),a
    ld a,(49953)
    out (127),a
    ret
