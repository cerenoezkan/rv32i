.org 0
addi x1, x0, 5
addi x2, x0, 15
add x10, x1, x2
loop:
beq x10, x1, loop
and x12, x1, x2
or x13, x1, x2
jal x0, loop
