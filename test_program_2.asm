# test_program_2.asm
# Test 2: Döngü + Dallanma (addi, bne, andi)
# Beklenen gözlem: LED[2:0] 1→2→3→4→5→6→7→1→... döngüsel sayar
# Her adım ~90ms @ 27 MHz → tam tur ~630ms (gözle net görülür)
#
# NOT: Son satır "beq x0,x0,LOOP" yerine "jal x0,LOOP" kullanıldı.
# Nedeni: beq SB-type (12-bit offset), jal UJ-type (20-bit offset).
# Uzun programlarda beq offset taşabilir; jal her zaman güvenlidir.

.text
.globl MAIN

MAIN:
    lui  x5, 2            # x5 = 0x2000 (LED MMIO adresi)
    addi x1, x0, 0        # sayaç başlangıcı = 0

LOOP:
    addi x1, x1, 1        # sayacı bir artır
    andi x1, x1, 7        # 3 bite kırp (0..7 arası döner)
    sw   x1, 0(x5)        # LED'e yaz (bit=0 → LED açık, aktif-low)

    # Gecikme: ~90ms @ 27 MHz
    # Hesap: lui x3,1 = 4096 (dış), addi x4,x0,200 = 200 (iç)
    # 4096 * 200 * 3 cycle ≈ 2.46M cycle / 27M = ~91ms
    lui  x3, 1             # x3 = 4096 (dış döngü sayısı)

OUTER:
    addi x4, x0, 200       # x4 = 200 (iç döngü sayısı)

INNER:
    addi x4, x4, -1
    bne  x4, x0, INNER    # iç döngü: x4 sıfırlanana kadar

    addi x3, x3, -1
    bne  x3, x0, OUTER    # dış döngü: x3 sıfırlanana kadar

    jal  x0, LOOP          # koşulsuz tekrar (UJ-type, güvenli)