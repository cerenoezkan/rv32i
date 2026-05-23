# test_program_2.asm
# Test 2: Döngü + Dallanma
# Beklenen gözlem: LED[5:0] 1→2→3→...→63→1 döngüsel sayar

.text
.globl MAIN

MAIN:
    lui  x5, 2
    addi x1, x0, 0

LOOP:
    addi x1, x1, 1
    andi x1, x1, 63       # 6 bite kırp (0..63 arası)
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