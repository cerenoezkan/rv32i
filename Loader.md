# PicoRV32 UART Loader — Tang Nano 9K

## Sistem Özeti

RV32I Assembly kaynak kodundan başlayıp Tang Nano 9K FPGA üzerinde fiziksel
çalışmaya kadar uçtan uca bir toolchain:

```
.asm kaynak
    ↓  rvi.py (assembler)
.o nesne dosyası
    ↓  linker.py (linker)
.hex (Verilog formatı)
    ↓  host_uploader.py (UART, 115200 baud)
FPGA loader_fsm (UART alım + CRC kontrol)
    ↓  BRAM'e yaz
PicoRV32 CPU başlat → LED çıkışı
```

---

## Kart ve Toolchain

| Özellik | Değer |
|---------|-------|
| Kart | Tang Nano 9K |
| Çip | Gowin GW1NR-9C |
| IDE | GowinEDA (Gowin IDE) |
| Clock | 27 MHz (onboard osilatör) |
| BAUD | 115200, 8N1 |
| CPU | PicoRV32 (RV32I) |

---

## Pin Tablosu

| Sinyal | Pin | Açıklama |
|--------|-----|----------|
| sys_clk | 52 | 27 MHz onboard |
| sys_rst_n | 4 | S1 butonu, aktif-LOW |
| uart_rx | 18 | PC'den FPGA'ya |
| uart_tx | 17 | FPGA'dan PC'ye (ACK/NAK) |
| led[0] | 10 | Aktif-LOW |
| led[1] | 11 | Aktif-LOW |
| led[2] | 13 | Aktif-LOW |

---

## Bellek Haritası

| Adres | Boyut | İçerik |
|-------|-------|--------|
| 0x0000_0000 | 1 KB | Program kodu (BRAM) |
| 0x0000_0400 | 3 KB | Veri bölümü (BRAM) |
| 0x0000_2000 | 4 B | LED MMIO (sw ile yaz, alt 3 bit) |

---

## Dosya Yapısı

```
rv32i/
├── lib/                    ← Assembler kütüphanesi (değiştirme)
│   ├── cprint.py
│   ├── machinecodeconst.py
│   ├── machinecodegen.py
│   ├── object_writer.py
│   ├── parser.py
│   └── tokenizer.py
├── rvi.py                  ← Assembler giriş noktası
├── linker.py               ← Linker
├── link_fpga.ld            ← FPGA linker script
├── picorv32.v              ← PicoRV32 RV32I core (değiştirme)
├── top.v                   ← Top-level modül
├── bram_interface.v        ← 4 KB BRAM
├── loader_fsm.v            ← UART loader FSM
├── uart_rx.v               ← 8N1 UART alıcı + 256B FIFO
├── uart_tx.v               ← 8N1 UART verici
├── cpu_control.v           ← CPU reset kontrolü
├── crc32_byte.v            ← IEEE CRC-32
├── host_uploader.py        ← PC tarafı yükleyici
├── test_program_1.asm      ← Test 1: Aritmetik (LED sabit)
├── test_program_2.asm      ← Test 2: Döngü (LED sayaç)
├── test_program_3.asm      ← Test 3: Fonksiyon çağrısı (LED üssel)
├── constraints/
│   └── tang_nano_9k.cst   ← Gowin pin atamaları
└── sim/
    └── tb_top.v           ← Simülasyon testbench
```

---

## Loader FSM Durum Diyagramı

```
IDLE → WAIT_HEADER → RECEIVE_PACKET → VALIDATE_CRC → WRITE_BRAM → NEXT_PACKET
                ↓                                         ↓ (NAK)        ↓
           LOAD_DONE                                  NEXT_PACKET    WAIT_HEADER
                ↓
       RELEASE_CPU_RESET → CPU çalışır
```

### Durum Açıklamaları

| Durum | Davranış |
|-------|----------|
| IDLE | CPU reset'te; 0xAA sync baytı beklenir |
| WAIT_HEADER | 0x55 → yeni paket; 0x56 → yükleme bitti |
| RECEIVE_PACKET | ADDR(4)+SIZE(2)+DATA(n)+CRC(4) alınır |
| VALIDATE_CRC | Hesaplanan CRC ile alınan karşılaştırılır |
| WRITE_BRAM | Bayt bayt BRAM'e yazar, ACK gönderir |
| NEXT_PACKET | ACK/NAK sonrası yeni paket bekler |
| LOAD_DONE | Oturum kapandı, entry_pc=0x0 ayarla |
| RELEASE_CPU_RESET | loader_done=1, CPU serbest |

---

## UART Paket Formatı

```
[0xAA][0x55][ADDR:4 LE][SIZE:2 LE][DATA:SIZE][CRC32:4 LE]
```

| Alan | Boyut | Açıklama |
|------|-------|----------|
| Sync | 2 B | 0xAA 0x55 |
| ADDR | 4 B | Little-endian BRAM adresi |
| SIZE | 2 B | Data bayt sayısı (max 256) |
| DATA | SIZE B | Ham makine kodu |
| CRC32 | 4 B | IEEE 802.3, CRC32(ADDR\|\|SIZE\|\|DATA) |

Oturum sonu: `[0xAA][0x56]`

FPGA yanıtları: `0x06` = ACK, `0x15` = NAK

---

## Kullanım Adımları

### 1. GowinEDA'da Bitstream Üret

GowinEDA'yı aç:
- File → New Project → FPGA seç: GW1NR-9C (QFN88, C6/I5)
- Şu dosyaları ekle (Add Files):
  - `top.v`, `bram_interface.v`, `loader_fsm.v`
  - `uart_rx.v`, `uart_tx.v`, `cpu_control.v`, `crc32_byte.v`
  - `picorv32.v`
- Constraint: `constraints/tang_nano_9k.cst`
- Process → Synthesize → Place & Route → Generate Bitstream
- Program Device → karta yükle (USB)

### 2. Assembly Programını Derle ve Linkle

```bash
# Tek dosya:
python rvi.py test_program_1.asm --link -o test1.hex -x --linker-script link_fpga.ld

# Çok dosya (test_program_3 tek dosyada, mul_func entegre):
python rvi.py test_program_3.asm --link -o test3.hex -x --linker-script link_fpga.ld
```

### 3. UART ile Yükle

```bash
pip install pyserial

# Linux/Mac:
python host_uploader.py test1.hex -p /dev/ttyUSB0

# Windows:
python host_uploader.py test1.hex -p COM3

# Port görmeden test:
python host_uploader.py test1.hex --dry-run
```

---

## Test Senaryoları

| Program | Açıklama | Beklenen LED |
|---------|----------|--------------|
| test_program_1.asm | Aritmetik: add, sub, addi | LED[2]=açık, diğerleri kapalı (sabit) |
| test_program_2.asm | Döngü: bne, beq, andi | 0..7 arası sayaç (~1 sn/adım) |
| test_program_3.asm | Fonksiyon: jal, jalr | 1→2→4→1→... döngüsü (~0.5 sn/adım) |

---

## Sık Karşılaşılan Sorunlar

| Sorun | Olası Neden | Çözüm |
|-------|------------|-------|
| LED yanmıyor | CPU başlamıyor | loader_done sinyalini kontrol et |
| CRC NAK alıyorum | Baud rate uyumsuzluğu | BAUD_DIV = 27M/115200 = 234 olmalı |
| Port açılmıyor | Driver yok | CH340 USB-Serial driver yükle |
| GowinEDA sentez hatası | picorv32.v uyumsuz | `define` direktiflerini kontrol et |

---

## Baud Rate Hesabı

Tang Nano 9K'da 27 MHz clock:

```
BAUD_DIV = 27_000_000 / 115200 = 234 (hata < %0.2 — kabul edilebilir)
```

Bu değer uart_rx.v ve uart_tx.v içinde `CLK_FREQ / BAUD_RATE` ile otomatik hesaplanır.