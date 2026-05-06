.text
LED_WRITE:
    lui  x3, 2
    addi x2, x2, 1
    sw   x2, 0(x3)
    addi x6, x0, 0
DELAY_OUTER:
    addi x7, x0, 0
DELAY_INNER:
    addi x7, x7, 1
    addi x5, x0, 5
    bne  x7, x5, DELAY_INNER
    addi x6, x6, 1
    addi x5, x0, 5
    bne  x6, x5, DELAY_OUTER
    jal  x0, LED_WRITE
    