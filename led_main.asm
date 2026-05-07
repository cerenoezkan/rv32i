.text
.globl MAIN          # MAIN sembolü dışarı açılır
.extern LED_FUNC     # LED_FUNC başka dosyada tanımlı

MAIN:
    lui x5, 2        # x5 = 0x2000 → LED register adresi

    addi x1, x0, 0   # x1 = başlangıç LED değeri (0)

LOOP:
    jal x10, LED_FUNC    # LED_FUNC fonksiyonunu çağır
                         # dönüş adresi x10'a kaydedilir

    sw x1, 0(x5)         # x1 değerini LED register'a yaz

    jal x0, LOOP         # Sonsuz döngü → tekrar LOOP'a git