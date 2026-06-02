# Test 3: Function Call (jal + jalr)
# LED pattern: 1->2->4->8->16->32->1->2->4...

.globl MAIN
.extern MUL_FUNC

.text

MAIN:
    lui  x5, 2
    addi x1, x0, 1

LOOP:
    jal  x10, MUL_FUNC

    sw   x1, 0(x5)

    jal  x0, LOOP