# test_program_2.asm
# Test 2: Döngü + Dallanma (bne, beq, andi)
# Beklenen gözlem: LED[2:0] 0→7 arası döngüsel sayar (görünür yanıp sönme)
# Gecikme ~27MHz'de ~1 saniye/adım olacak şekilde ayarlandı

.text
.globl MAIN

MAIN:
    lui  x5, 2            # x5 = 0x2000 (LED MMIO adresi)
    addi x1, x0, 0        # sayaç x1 = 0

LOOP:
    addi x1, x1, 1        # sayacı artır
    andi x1, x1, 7        # 0..7 arasında tut (3 bit, 3 LED)
    sw   x1, 0(x5)        # LED'e yaz

    # Gecikme iç döngüsü
    # Hedef: ~1 saniye @ 27 MHz
    # Her INNER döngüsü: 2 instruction = ~2 cycle (bne dahil ~3 cycle, basit kestirme)
    # Gerçek: iç×dış × ~3 cycle = 27_000_000 → iç×dış ≈ 9_000_000
    # lui x3, 3 = 3*4096 = 12288 (dış)  lui x4, 3 = 3*4096 = 12288 (iç)
    # 12288 * 12288 * ~3 ≈ 453M cycle → ~16s @ 27 MHz, hâlâ uzun.
    # Görünür LED geçişi için: dış=200, iç=200*30 = 1.2M cycle (~44ms/adım, 8 adım → ~350ms tam tur)
    # Pratik seçim: lui x3, 1 (=4096), addi x4, x0, 200 → 4096*200*3 ≈ 2.5M (~90ms/LED adım)
    addi x3, x0, 0
    lui  x3, 1             # x3 = 4096 (dış döngü sayısı)

OUTER:
    addi x4, x0, 200       # x4 = 200 (iç döngü sayısı)

INNER:
    addi x4, x4, -1
    bne  x4, x0, INNER    # iç döngü

    addi x3, x3, -1
    bne  x3, x0, OUTER    # dış döngü

    beq  x0, x0, LOOP     # koşulsuz (x0 == x0 her zaman doğru)