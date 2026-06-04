.globl MAIN
.text

MAIN:
    addi x10, x0, 8
    addi x11, x0, 3

    jal  x1, ADD_FUNC

    sub  x12, x12, x11
    sub  x12, x12, x11

    lui  x6, 2
    addi x7, x6, 8
    addi x8, x6, 12

    sw   x12, 0(x6)

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
    addi x9, x0, 63
    sw   x9, 0(x6)
    jal  x0, LOOP

ARITH:
    sw   x12, 0(x6)
    jal  x0, LOOP