.data
num1:
.word 3

num2:
.word 7

.text
.extern TOPLA
.globl MAIN

MAIN:
addi x1, x0, 3
addi x2, x0, 7

jal x10, TOPLA

addi x5, x0, 1