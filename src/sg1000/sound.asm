; Independent SN76489 voices. Channel 0: pellet chomp (player.asm);
; channel 1: continuous ghost siren; channel 2: event tones (ghost eaten,
; death, level clear). Channel 3/noise remains muted. Events share channel 2
; and replace one another, but cannot silence the chomp or the siren.
; This is an SG-1000 approximation, not a translation of the NES APU engine.
;
; C282 event remaining frames, C283 event kind (1=eat, 2=death, 3=level).
sound_frame:
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
    ld a,b
    add a,75                  ; eaten ghost
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
