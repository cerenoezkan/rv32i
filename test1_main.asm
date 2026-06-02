.data

VALUE1:
.word 8

VALUE2:
.word 3

.text
.globl MAIN
.extern ADD_FUNC

MAIN:
    # VALUE1 oku
    addi x20, x0, 64
    lw   x1, 0(x20)

    # VALUE2 oku
    addi x21, x0, 68
    lw   x2, 0(x21)

    # ADD_FUNC için parametreler
    add  x10, x1, x0
    add  x11, x2, x0

    # x12 = VALUE1 + VALUE2
    jal  x5, ADD_FUNC

    # 11 - 3 - 3 = 5
    sub  x12, x12, x2
    sub  x12, x12, x2

    # sonucu sakla
    add  x13, x12, x0

    # MMIO adresleri
    lui  x6, 2
    addi x7, x6, 8
    addi x8, x6, 12

    sw   x13, 0(x6)

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
    sw   x13, 0(x6)
    jal  x0, LOOP