# mul_func.asm — test_program_3 yardımcı fonksiyon
.text
.globl MUL_FUNC

MUL_FUNC:
    add  x1, x1, x1      # x1 * 2 (add ile)
    andi x1, x1, 63      # alt 6 bit
    lui  x3, 500
    addi x3, x3, 0
DELAY:
    addi x3, x3, -1
    bne  x3, x0, DELAY
    jalr x0, x10, 0
