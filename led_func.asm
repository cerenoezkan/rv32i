.text
.globl LED_FUNC

LED_FUNC:
    addi x1, x1, 1
    andi x1, x1, 63
    lui x3, 1953
    addi x3, x3, 288

DELAY_LOOP:
    addi x3, x3, -1
    bne x3, x0, DELAY_LOOP

    jalr x0, x10, 0