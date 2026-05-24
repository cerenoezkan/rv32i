.data

VALUE1:
.word 5

VALUE2:
.word 7

.text

MAIN:
    lui  x5, 2

    # x6 = 0x40
    addi x6, x0, 64
    lw   x10, 0(x6)

    # x7 = 0x44
    addi x7, x0, 68
    lw   x11, 0(x7)

    jal  x1, ADD_FUNC

    sw   x12, 0(x5)

LOOP:
    jal x0, LOOP