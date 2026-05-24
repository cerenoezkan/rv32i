# test_program_1.asm
# Test 1: Arithmetic + UART Input
# UART '1' -> all 6 LEDs on
# UART '0' -> arithmetic result

.text
.globl MAIN

MAIN:
    addi x1, x0, 8
    addi x2, x0, 3
    add  x3, x1, x2
    sub  x4, x3, x2
    sub  x5, x4, x2      # x5 = 5
    lui  x6, 2            # x6 = 0x2000 LED
    addi x7, x6, 8       # x7 = 0x2008 UART data
    addi x8, x6, 12      # x8 = 0x200C UART ready

    sw   x5, 0(x6)        # baslangicta aritmetik sonucu goster

FLUSH:
    lw   x9, 0(x8)        # FIFO bos mu?
    beq  x9, x0, LOOP    # bos ise ana dongúye gec
    lw   x10, 0(x7)       # eski byte'i oku ve at
    jal  x0, FLUSH
LOOP:
    lw   x10, 0(x7)       # direkt data oku (ready beklemeden)
    beq  x10, x0, LOOP   # 0 gelirse bekle

    addi x11, x0, 49
    beq  x10, x11, ALL_ON

    addi x11, x0, 48
    beq  x10, x11, ARITH

    jal  x0, LOOP

ALL_ON:
    addi x12, x0, 63
    sw   x12, 0(x6)
    jal  x0, LOOP

ARITH:
    sw   x5, 0(x6)
    jal  x0, LOOP