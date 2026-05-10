.text
.globl LED_FUNC      # LED_FUNC dışarı açılır

LED_FUNC:
    addi x1, x1, 1   # LED değerini 1 artır

    andi x1, x1, 63  # Sadece alt 6 bit tutulur
                     # 0-63 arası sayaç oluşur

    lui x3, 1953     # Delay sayacı üst bitleri

    addi x3, x3, 288 # x3 ≈ büyük delay değeri
                     # LED değişimi gözle görülebilir olur

DELAY_LOOP:
    addi x3, x3, -1  # Delay sayacını azalt

    bne x3, x0, DELAY_LOOP
                     # x3 sıfır değilse döngüye devam et

    jalr x0, x10, 0  # Fonksiyondan geri dön
