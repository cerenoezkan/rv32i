# test_program_1.asm
# Basit aritmetik: add / sub / addi
# Sonuç LED'e yazılır (beklenen: 0x14 = 20)

.text
.globl MAIN

MAIN:
    addi x1, x0, 10      # x1 = 10
    addi x2, x0, 3       # x2 = 3
    add  x3, x1, x2      # x3 = 13
    sub  x4, x1, x2      # x4 = 7
    add  x5, x3, x4      # x5 = 20

    lui  x6, 2           # LED @ 0x2000
    sw   x5, 0(x6)       # LED = 20

HOLD:
    jal  x0, HOLD        # sonsuz bekleme
