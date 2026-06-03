# test_program_1.asm
# UART '1' -> all 6 LEDs on
# UART '0' -> arithmetic result

.globl MAIN

.text

MAIN:
    addi x1, x0, 8
    addi x2, x0, 3

    # Fonksiyon parametreleri
    add  x10, x1, x0
    add  x11, x2, x0

    jal  x1, ADD_FUNC

    # x12 = 11
    add  x3, x12, x0

    sub  x4, x3, x2
    sub  x5, x4, x2      # x5 = 5

    lui  x6, 2           # x6 = 0x2000 LED
    addi x7, x6, 8       # x7 = 0x2008 UART data
    addi x8, x6, 12      # x8 = 0x200C UART ready

    sw   x5, 0(x6)

FLUSH:
    lw   x9, 0(x8)
    beq  x9, x0, LOOP

    lw   x10, 0(x7)
    jal  x0, FLUSH

LOOP:
    lw   x10, 0(x7)
    beq  x10, x0, LOOP

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