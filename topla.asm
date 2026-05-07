.data

RESULT:
.word 0          # Sonuç burada tutulacak

.text
.globl TOPLA     # TOPLA dışarı açılıyor

TOPLA:
    add x3, x1, x2   # x3 = x1 + x2 → 3 + 7 = 10

    sw x3, 8(x4)     # Sonucu memory'e yaz
                      # adres 8 = RESULT

    jalr x0, x10, 0  # Fonksiyondan geri dön