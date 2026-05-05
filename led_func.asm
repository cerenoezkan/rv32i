.text
LED_WRITE:
lui x3, 2
addi x2, x2, 1
sw x2, 0(x3)
addi x4, x0, 1
DELAY:
addi x4, x4, 1
addi x5, x0, 255
beq x4, x5, LED_WRITE
jal x0, DELAY

