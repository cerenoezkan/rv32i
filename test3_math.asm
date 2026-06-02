.globl MUL_FUNC

.text

MUL_FUNC:
    add  x1, x1, x1
    andi x1, x1, 63

    bne  x1, x0, DELAY_START

    addi x1, x0, 1

DELAY_START:
    lui  x3, 1

DELAY_OUTER:
    addi x4, x0, 200

DELAY_INNER:
    addi x4, x4, -1
    bne  x4, x0, DELAY_INNER

    addi x3, x3, -1
    bne  x3, x0, DELAY_OUTER

    jalr x0, x10, 0