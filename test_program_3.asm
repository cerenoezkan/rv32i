# test_program_3.asm
# Fonksiyon çağrısı: jal (çağrı) + jalr (dönüş)
# LED değeri her tur 2 ile çarpılır (gözle görülür üssel artış)

.text
.globl MAIN

MAIN:
    lui  x5, 2           # LED @ 0x2000
    addi x1, x0, 1       # sayaç = 1

LOOP:
    # Not: Bu projede x10 dönüş adresi olarak kullanılıyor (standart dışı,
    # ancak MUL_FUNC içindeki jalr x0, x10, 0 ile tutarlı)
    jal  x10, MUL_FUNC   # fonksiyon çağrısı; dönüş adresi x10
    sw   x1, 0(x5)
    jal  x0, LOOP

MUL_FUNC:
    add  x1, x1, x1      # x1 * 2
    andi x1, x1, 63
    lui  x3, 400
    addi x3, x3, 0
DELAY:
    addi x3, x3, -1
    bne  x3, x0, DELAY
    jalr x0, x10, 0      # fonksiyondan dönüş
