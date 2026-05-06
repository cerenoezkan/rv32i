.globl LED_WRITE

.data
DELAY_LIMIT: .word 5      # Döngü sınırı burada saklanıyor

.text
LED_WRITE:
    lui  x3, 2            # LED adresi: 0x00002000
    addi x2, x2, 1        # Sayacı artır
    sw   x2, 0(x3)        # LED'e yaz
    
    # Gecikme sınırını bellekten oku
    la   x4, DELAY_LIMIT  # DELAY_LIMIT adresini x4'e al
    lw   x5, 0(x4)        # x5 artık 5 değerini tutuyor
    
    addi x6, x0, 0        # dış döngü sayacı = 0
DELAY_OUTER:
    addi x7, x0, 0        # iç döngü sayacı = 0

DELAY_INNER:
    addi x7, x7, 1
    # addi x5, x0, 5      <-- Eskiden buydu, şimdi bellekten (x5) geliyor
    bne  x7, x5, DELAY_INNER

    addi x6, x6, 1
    bne  x6, x5, DELAY_OUTER

    jalr x0, x10, 0       # Geri dön