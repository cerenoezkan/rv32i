.extern LED_WRITE

.data
START_VAL:  .word 1       # x1 için başlangıç değeri (1)
INIT_COUNT: .word 0       # x2 için başlangıç değeri (0)

.text
    # Verileri bellekten register'lara yüklüyoruz
    la   x5, START_VAL    # START_VAL etiketinin adresini x5'e al
    lw   x1, 0(x5)        # Bellekteki 1 değerini x1'e yükle
    
    la   x5, INIT_COUNT   # INIT_COUNT etiketinin adresini x5'e al
    lw   x2, 0(x5)        # Bellekteki 0 değerini x2'e yükle

MAIN_LOOP:
    jal  x10, LED_WRITE   # Fonksiyonu çağır
    jal  x0, MAIN_LOOP    # Başa dön