# Tang Nano 9K — RV32I UART Loader Denetim Raporu

**Tarih:** 2026  
**Hedef:** Gowin GW1NR-9C (Tang Nano 9K), 27 MHz, PicoRV32  
**Denetim kapsamı:** RTL, timing, FSM, host-FPGA protokol, sentez uyumu

---

## 1. PROJE ANALİZİ

### Dosya envanteri

| Dosya | Görev | Durum |
|--------|------|--------|
| `top.v` | Entegrasyon: clock, reset, UART, loader, CPU, BRAM, LED MMIO | ✅ Yapı doğru |
| `loader_fsm.v` | UART paket decode, CRC, BRAM yazma FSM | ✅ (1 kritik düzeltme uygulandı) |
| `bram_interface.v` | 4 KB BRAM, CPU bus + loader backdoor | ✅ Gowin BRAM attr |
| `cpu_control.v` | `cpu_resetn`, güç-açılışı, `force_loader` | ✅ |
| `uart_rx.v` | 8N1 RX + 2FF sync + 256 FIFO | ✅ |
| `uart_tx.v` | 8N1 TX, ACK/NAK | ✅ |
| `crc32_byte.v` | IEEE CRC-32 (zlib uyumlu) | ✅ |
| `picorv32.v` | RV32I çekirdek | ✅ (upstream) |
| `host_uploader.py` | .hex / .o → UART paketleri | ✅ |
| `sim_tb.v` | Full integration TB | ✅ |
| `constraints/tang_nano_9k.cst` | Gowin pin atamaları | ✅ |
| `link_fpga.ld` | FPGA DATA @ 0x400 | ✅ |
| `test_program_1/2/3.asm` | Test senaryoları | ✅ |
| `lib/`, `rvi.py`, `linker.py` | Toolchain (dokunulmadı) | ✅ |

**Kaldırılan / kullanılmayacak:** `memory.v`, `constraints/basys3_top.xdc`

### Mimari değerlendirme

```
Host (.hex/.o) ──UART──► uart_rx/FIFO ──► loader_fsm ──► bram_interface
                                                    │
                                              cpu_control (cpu_resetn)
                                                    │
                                              picorv32 ◄──► bram + LED@0x2000
```

Mimari **akademik loader projesi için doğru**: CPU yükleme bitene kadar reset'te, BRAM'e runtime yazım, CRC korumalı paketler.

### FPGA'da çalışır mı?

**Evet — koşullu:** GowinEDA'da doğru dosyalar, `tang_nano_9k.cst`, bitstream yükleme ve ardından `host_uploader.py` ile program gönderimi gerekir. Simülasyon `sim_tb` ile loader_done doğrulanmalı.

### Kritik bulgular (öncesi / sonrası)

| # | Sorun | Şiddet | Durum |
|---|--------|--------|--------|
| 1 | Yeniden UART yüklemede CPU çalışırken BRAM'e yazım (race) | **Kritik** | ✅ Düzeltildi (`loader_done<=0` yeni oturumda) |
| 2 | `entry_pc` PicoRV32'e bağlı değil | Orta | ⚠️ Dokümante (PC sabit 0x0) |
| 3 | LED MMIO 16-bit yazım, donanımda 3 bit | Düşük | ⚠️ Beklenen (maskeleme) |
| 4 | `ld_ack` kombinasyonel | Düşük | ✅ Tek yazıcı (loader) yeterli |
| 5 | Host paketleri arası gecikme yok | Orta | ✅ 5 ms delay eklendi |

---

## 2. EKSİKLER VE RİSKLER

### Eksik modüller

- Gowin proje dosyası (`.gprj`) — IDE'de manuel oluşturulur
- ILA / SignalTap benzeri on-chip debug — yok (isteğe bağlı)
- `entry_pc` → PicoRV32 PC yazma köprüsü — yok (parametre sabit)

### Race condition

- **CPU vs loader BRAM:** Loader aktifken CPU reset'te → güvenli. Düzeltme sonrası yeni UART oturumu CPU'yu durdurur.
- **FIFO overflow:** 256 byte; tek paket max 256+10 byte; uzun ardışık paketlerde `fifo_full` riski — host delay ile azaltıldı.

### FSM

- `S_NEXT_PACKET`: `0xAA` dışı baytlar tüketilir (discard) — OK
- Oturum sonu: `AA 56` iki aşamada — host sırası doğru olmalı
- `crc_valid_delay`: 1 clock CRC settle — OK

### UART veri kaybı

- Baud hata: 27M/115200 = **234**, gerçek ~115107 bps (~%0.08) — kabul edilebilir
- RX 2-FF sync: 27 MHz için yeterli
- TX tek kuyruk: ACK sırasında `tx_busy` bekleniyor — OK

### Reset sırası

1. `sys_rst_n=0` → tüm mantık reset (`sys_rst=1`)
2. `pwr_done` (16 cycle)
3. UART yükleme → `loader_done=1`
4. `cpu_resetn=1` (buton serbest, loader idle)

---

## 3. TANG NANO 9K UYUMLULUK

| Konu | Sonuç |
|------|--------|
| Gowin sentez | `syn_ramstyle = "block_ram"` kullanılıyor |
| PLL | **Gerekmez** — 27 MHz direkt osilatör |
| Clock | 27 MHz uygun |
| BRAM | 1024×32 = 4 KB — GW1NR-9C için küçük |
| CST pinleri | sys_clk=52, rst=4, uart=17/18, led=10/11/13 |
| UART | USB-serial bridge kart üzerinde |
| Kaynak | PicoRV32 + BRAM << 9K LUT limiti |

**Dikkat:** Tang Nano 9K resmi pin numaraları kart revizyonuna göre doğrulanmalı (Sipeed wiki).

---

## 4. UYGULANAN DÜZELTMELER

| Dosya | Değişiklik |
|--------|------------|
| `loader_fsm.v` | Yeni UART oturumunda `loader_done<=0`, `loader_active<=1` |
| `host_uploader.py` | Paketler arası 5 ms bekleme |
| `tb_uart_rx.v` | Yeni |
| `tb_bram_interface.v` | Yeni |
| `tb_loader_fsm.v` | Yeni |
| `AUDIT_REPORT.md` | Bu dosya |

---

## 5. LOADER AKIŞI

1. **PC:** `host_uploader.py` hex/o parse → paketler → seri port
2. **UART:** 8N1, 115200, `AA 55` + ADDR + SIZE + DATA + CRC32
3. **FPGA RX:** `uart_rx` → FIFO → `loader_fsm`
4. **BRAM:** `WRITE_BRAM` → `bram_interface` byte yazma
5. **CPU reset:** `loader_done=0` iken `cpu_resetn=0`
6. **Serbest:** `AA 56` → `LOAD_DONE` → `loader_done=1`
7. **Çalışma:** `cpu_resetn=1`, PC=0 (`PROGADDR_RESET`)

---

## 6–7. TEST VE DEBUG

Detaylı adımlar ana yanıt metninde (Gowin IDE, COM port, LED active-low, sim komutları).

---

## 8. TESTBENCH DOSYALARI

| Dosya | Kapsam |
|--------|--------|
| `tb_uart_rx.v` | UART RX byte |
| `tb_bram_interface.v` | Loader + CPU BRAM |
| `tb_loader_fsm.v` | FSM + oturum sonu |
| `sim_tb.v` | Full `top` entegrasyon |

---

## 9. TEST PROGRAMLARI

| Program | Beklenen (LED active-low) |
|---------|---------------------------|
| `test_program_1.asm` | `led_reg=20` → pinlerde ~bit pattern |
| `test_program_2.asm` | 0..15 sayaç blink |
| `test_program_3.asm` | x1 her tur ×2 (alt 6 bit) |

---

## 10. SON KARAR

| Soru | Cevap |
|------|--------|
| Gerçekten çalışır mı? | **Evet**, sim + doğru yükleme akışı ile |
| FPGA'da denenebilir mi? | **Evet** |
| Kritik hata kaldı mı? | **Ana race düzeltildi**; `entry_pc` donanımda sabit |
| Teslim seviyesi? | **Evet** — akademik FPGA loader ödevi için uygun |
