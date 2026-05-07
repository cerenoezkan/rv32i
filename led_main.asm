.text
.globl MAIN
.extern LED_FUNC

MAIN:
    lui x5, 2
    addi x1, x0, 0

LOOP:
    jal x10, LED_FUNC
    sw x1, 0(x5)
    jal x0, LOOP