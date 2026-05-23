# test_program_1.asm
# Test 1: Arithmetic + Button Input (6 LED)
# Normal: arithmetic result x5=5 -> LED[0]+LED[2] on
# S1 short press: all 6 LEDs on

.text
.globl MAIN

MAIN:
    addi x1, x0, 8
    addi x2, x0, 3
    add  x3, x1, x2      # x3 = 11
    sub  x4, x3, x2      # x4 = 8
    sub  x5, x4, x2      # x5 = 5 = 0b000101
    lui  x6, 2            # x6 = 0x2000
    addi x7, x6, 4        # x7 = 0x2004 button

LOOP:
    lw   x8, 0(x7)        # read button (released=1, pressed=0)
    beq  x8, x0, BTN_PRESSED

    sw   x5, 0(x6)        # LED = 5 = 0b000101
    jal  x0, LOOP

BTN_PRESSED:
    addi x9, x0, 63       # 63 = 0b111111
    sw   x9, 0(x6)        # all LEDs on
    jal  x0, LOOP