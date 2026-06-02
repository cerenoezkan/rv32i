# ================================================================
# Test 4: Bellek Siniri Zorlamasi
# BRAM: 128 byte toplam (0x00-0x7C)
# TEXT: 0x00-0x33 (13 komut = 52 byte)
# DATA: 0x60-0x7C (8 kelime = 32 byte) <- BRAM'in son 32 byte'i
# Beklenen LED: 1+2+3+4+5+6+7+8 = 36 -> 36 AND 63 = 36 = 0b100100
# ================================================================

.data

ARRAY:
    .word 1
    .word 2
    .word 3
    .word 4
    .word 5
    .word 6
    .word 7
    .word 8

.text
.globl MAIN
.extern SUM_FUNC

MAIN:
    # LED MMIO adresi: 0x2000
    lui  x6, 2

    # ARRAY adresi: DATA_BASE = 0x60 = 96
    addi x10, x0, 96

    # Uzunluk: 8 eleman
    addi x11, x0, 8

    # SUM_FUNC(x10=adres, x11=uzunluk) -> x12=toplam
    jal  x1, SUM_FUNC

    # 6-bit kirp: 36 AND 63 = 36
    andi x12, x12, 63

    # LED'e yaz
    sw   x12, 0(x6)

DONE:
    jal  x0, DONE