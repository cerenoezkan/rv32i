# test_program_1.asm
# Test 1: Temel Aritmetik (add, sub, addi)
# Beklenen gözlem: LED[2:0] = 0b100 (decimal 4, yani x5=20'nin alt 3 biti)
# Tang Nano 9K: 3 LED, aktif-low → LED[2]=açık, LED[1,0]=kapalı

.text
.globl MAIN

MAIN:
    addi x1, x0, 10      # x1 = 10
    addi x2, x0, 3       # x2 = 3
    add  x3, x1, x2      # x3 = 13
    sub  x4, x1, x2      # x4 = 7
    add  x5, x3, x4      # x5 = 20 = 0b10100

    lui  x6, 2            # x6 = 0x2000 (LED MMIO adresi)
    sw   x5, 0(x6)        # LED = 20 → alt 3 bit = 0b100 → LED[2] açık

HOLD:
    jal  x0, HOLD         # sonsuz döngü — LED sabit yanar