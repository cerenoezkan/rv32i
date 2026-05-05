.extern TOPLA       # <--- DİKKAT: Burası "External çözümleme" kanıtı

.text
addi x1, x0, 3
addi x2, x0, 7
jal x10, TOPLA      # Linker buradaki TOPLA'yı diğer dosyada arayacak
addi x5, x0, 1