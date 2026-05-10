.data

NUM1:
.word 3          # İlk sayı

NUM2:
.word 7          # İkinci sayı

.text
.extern TOPLA    # TOPLA fonksiyonu başka dosyada
.globl MAIN      # MAIN dışarı açılıyor

MAIN:
    lui x4, 0    # x4 = data section base adresi

    lw x1, 0(x4) # x1 = NUM1 değerini oku (3)
    lw x2, 4(x4) # x2 = NUM2 değerini oku (7)

    jal x10, TOPLA   # TOPLA fonksiyonunu çağır

    addi x5, x0, 1   # Program sonu için örnek işlem

    