# test_program_3.asm
# Test 3: Fonksiyon Çağrısı (jal + jalr)
# x1 her fonksiyon çağrısında 2 ile çarpılır, alt 3 biti LED'e yazar
# Beklenen gözlem: LED 1→2→4→1→2→4... şeklinde döner
# (1=0b001, 2=0b010, 4=0b100, 8 & 7 = 0 → andi ile 1'e döner)
#
# Not: Bu projede x10 dönüş adresi olarak kullanılıyor (standart dışı ama tutarlı)

.text
.globl MAIN

MAIN:
    lui  x5, 2            # x5 = 0x2000 (LED MMIO adresi)
    addi x1, x0, 1        # x1 = 1 (başlangıç değeri)

LOOP:
    jal  x10, MUL_FUNC    # MUL_FUNC'ı çağır; dönüş adresi x10'a kaydedildi
    sw   x1, 0(x5)        # LED'e yaz (x1'in alt 3 biti görünür)
    jal  x0, LOOP         # sonsuz döngü

# ------------------------------------------------------------------
# MUL_FUNC: x1'i 2 ile çarpar, alt 3 bite kırpar, gecikme yapar
# Çağrı: jal x10, MUL_FUNC
# Dönüş: jalr x0, x10, 0
# ------------------------------------------------------------------
MUL_FUNC:
    add  x1, x1, x1       # x1 = x1 * 2 (toplama yoluyla çarpma)
    andi x1, x1, 7        # alt 3 bit: 0..7 arası tut

    # Gecikme (~0.5 saniye @ 27 MHz)
    # lui x3, 16 = 65536 → 65536*3 cycle ≈ 7ms — çok kısa, gözle görülmez!
    # DÜZELTME: addi x3,x0,0 + lui x3,3 = 12288 × 3 ≈ 1.4ms — hâlâ kısa.
    # Görünür fark için: dış+iç kombinasyonu kullan.
    # lui x3, 2 (=8192) ve iç döngü addi x4,x0,100 → 8192*100*3 ≈ 2.5M (~90ms/adım)
    lui  x3, 2             # x3 = 8192 (dış)
    addi x3, x3, 0

DELAY_OUTER:
    addi x4, x0, 100       # x4 = 100 (iç)

DELAY:
    addi x4, x4, -1
    bne  x4, x0, DELAY    # iç sıfırlanana kadar bekle

    addi x3, x3, -1
    bne  x3, x0, DELAY_OUTER  # dış sıfırlanana kadar bekle

    jalr x0, x10, 0       # LOOP'a geri dön (x10 = dönüş adresi)