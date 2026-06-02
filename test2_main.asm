# Test 2: Loop + Branch
# Beklenen gözlem:
# LED[5:0] = 1→2→3→...→63→0→1 ...

.globl MAIN
.extern INC_FUNC

.text

MAIN:
    lui  x5, 2
    addi x1, x0, 0

LOOP:
    # x1 = x1 + 1
    add  x10, x1, x0
    jal  x31, INC_FUNC
    add  x1, x12, x0

    andi x1, x1, 63
    sw   x1, 0(x5)

    lui  x3, 1

OUTER:
    addi x4, x0, 200

INNER:
    addi x4, x4, -1
    bne  x4, x0, INNER

    addi x3, x3, -1
    bne  x3, x0, OUTER

    jal  x0, LOOP