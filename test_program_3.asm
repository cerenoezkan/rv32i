# test_program_3.asm
# Test 3: Fonksiyon Çağrısı (jal + jalr)
# x1 her çağrıda 2 ile çarpılır, alt 3 biti LED'e yazar.
# Beklenen gözlem: LED 1→2→4→1→2→4... şeklinde döner (~90ms/adım)
#
# DÜZELTME: andi x1,x1,7 → x1=8 olunca 0 yapar, sonra 0 kalır.
# Çözüm: sıfırsa x1'i 1'e sıfırla (RESET_VAL etiketi).
# Böylece döngü kesinlikle 1→2→4→1→... olur, sonsuza kadar.
#
# Not: x10 dönüş adresi olarak kullanılıyor (bu projede standart, mul_func ile tutarlı)

.text
.globl MAIN

MAIN:
    lui  x5, 2            # x5 = 0x2000 (LED MMIO adresi)
    addi x1, x0, 1        # x1 = 1 (başlangıç değeri)

LOOP:
    jal  x10, MUL_FUNC    # MUL_FUNC çağır; x10 = dönüş adresi
    sw   x1, 0(x5)        # güncel x1'i LED'e yaz
    jal  x0, LOOP         # sonsuz döngü

# ------------------------------------------------------------------
# MUL_FUNC: x1 = (x1 * 2) & 7, sıfırsa 1'e sıfırla, gecikme yap
# Çağrı  : jal x10, MUL_FUNC
# Dönüş  : jalr x0, x10, 0
# ------------------------------------------------------------------
MUL_FUNC:
    add  x1, x1, x1       # x1 = x1 * 2

    andi x1, x1, 7        # alt 3 bite kırp (0..7)

    # Sıfır kontrolü: x1=0 ise 1'e sıfırla (1→2→4→1 döngüsü bozulmasın)
    bne  x1, x0, DELAY_START   # x1 != 0 ise gecikmeye geç
    addi x1, x0, 1             # x1 = 0 idi → 1'e sıfırla

DELAY_START:
    # Gecikme: ~90ms @ 27 MHz
    # lui x3,1 = 4096 (dış), addi x4,x0,200 = 200 (iç)
    # 4096 * 200 * 3 ≈ 2.46M cycle / 27M ≈ 91ms
    lui  x3, 1             # x3 = 4096 (dış döngü)

DELAY_OUTER:
    addi x4, x0, 200       # x4 = 200 (iç döngü)

DELAY_INNER:
    addi x4, x4, -1
    bne  x4, x0, DELAY_INNER   # iç döngü

    addi x3, x3, -1
    bne  x3, x0, DELAY_OUTER   # dış döngü

    jalr x0, x10, 0       # LOOP'a geri dön