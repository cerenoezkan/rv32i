# test_program_2.asm
# Döngü + dallanma (bne / beq)
# LED'de 0..15 arası sayaç — gözle görülür blink

.text
.globl MAIN

MAIN:
    lui  x5, 2           # LED base 0x2000
    addi x1, x0, 0       # sayaç = 0

LOOP:
    addi x1, x1, 1
    andi x1, x1, 15      # 0..15
    sw   x1, 0(x5)

    lui  x3, 500         # dış gecikme (27 MHz'de yavas blink)
    addi x3, x3, 0

OUTER:
    lui  x4, 200
    addi x4, x4, 0

INNER:
    addi x4, x4, -1
    bne  x4, x0, INNER

    addi x3, x3, -1
    bne  x3, x0, OUTER

    beq  x0, x0, LOOP    # koşulsuz dal (x0 == x0)
