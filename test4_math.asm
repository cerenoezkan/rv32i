# ================================================================
# Test 4: SUM_FUNC (yaprak fonksiyon, stack yok)
# Girdi : x10 = dizi adresi, x11 = eleman sayisi
# Cikti : x12 = toplam
# ================================================================

.globl SUM_FUNC

.text

SUM_FUNC:
    addi x14, x0, 0
    add  x15, x11, x0

SUM_LOOP:
    beq  x15, x0, SUM_DONE
    lw   x16, 0(x10)
    add  x14, x14, x16
    addi x10, x10, 4
    addi x15, x15, -1
    jal  x0, SUM_LOOP

SUM_DONE:
    add  x12, x14, x0
    jalr x0, x1, 0