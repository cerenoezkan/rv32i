.global TOPLA       # <--- DİKKAT: Burası "Global sembol" kanıtı

.text
TOPLA:
add x3, x1, x2
addi x3, x3, 1
jalr x0, x10, 0
