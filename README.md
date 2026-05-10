# RVI — RV32I Assembler & Linker Sistemi
## Nesne dosyası üretimi, çoklu dosya bağlayıcı (linker) ve FPGA dağıtım hattına sahip iki geçişli bir RV32I assembler

📋 İçindekiler
Genel Bakış

Mimari

Özellikler

Proje Yapısı

Kurulum

Kullanım

Assembly Dili Referansı - Direktifler

Linker Script

GUI

İş Hattı Diyagramı (Pipeline Diagram)

## Genel Bakış
<img width="1536" height="1024" alt="ChatGPT Image 10 May 2026 14_07_14" src="https://github.com/user-attachments/assets/ca33fee8-f89d-4278-b3e5-f7870f72d197" />

RVI, RISC-V RV32I komut seti mimarisi için Python ile sıfırdan oluşturulmuş tam bir araç zinciridir (toolchain). .asm kaynak dosyalarını iki geçişli bir assembler aracılığıyla ikili nesne dosyalarına (.o) derler, birden fazla nesne dosyasını nihai bir .hex çıktısında birleştirir ve PicoRV32 işlemci çekirdeğini kullanarak gerçek FPGA donanımını hedefler.

Sistem; dosyalar arası sembol çözümleme, export/import deklarasyonları (.globl / .extern), relocation yamaları (patching) ve özel bellek yerleşimleri için linker script desteği sunar. Kaynak koddan çalışan donanıma kadar tüm yaşam döngüsünü kapsar.

## Mimari

<img width="458" height="638" alt="image" src="https://github.com/user-attachments/assets/d99474ec-4c0c-468f-9bcf-4ed70b4905a1" />


## Özellikler 

<img width="592" height="837" alt="image" src="https://github.com/user-attachments/assets/d6c1b625-b2ba-4195-8bf8-f21f00b22b7f" />


## Proje Yapısı 

<img width="633" height="431" alt="image" src="https://github.com/user-attachments/assets/65f920ca-f57e-4fb0-9142-0af5ff3cfea4" />


## Kurulum

### Gereksinimler

- Python 3.8+

- PLY (Python Lex-Yacc)

  pip install ply 

### Klonlama


git clone https://github.com/<kullanici-adiniz>/rvi.git
cd rvi


### Kullanım 

- Mod 1 — Tek bir dosyayı derleme

  python rvi.py program.asm -x -es


  <img width="592" height="325" alt="image" src="https://github.com/user-attachments/assets/009ac071-6d84-402a-9e37-eb70d2887121" />

- Mod 2 — Çoklu dosyaları derleme + linkleme

  python rvi.py led_main.asm led_func.asm --link -o output.hex -x
  

- Sadece Linker (Mevcut .o dosyalarından)

  python linker.py led_main.o led_func.o -o output.hex -x

  python linker.py led_main.o led_func.o -o output.hex --linker-script link.ld
  

- Varsayılan bir linker script oluşturma

   python linker.py --gen-ld
  

- Grafik Arayüz (GUI)

   python rvi_gui.py




## Assembly Dili Referansı 

### Direktifler 

<img width="532" height="137" alt="image" src="https://github.com/user-attachments/assets/3c7c6792-952c-4579-a641-c90df85634c5" />




## Linker Script 

Temel adresleri ayarlamak için link.ld dosyasını düzenleyin:

TEXT_BASE = 0x00000000;   # Kodun başlangıcı

DATA_BASE = 0x00010000;   # Veri bölümünün başlangıcı




## GUI 

Grafiksel iş akışı için rvi_gui.py dosyasını çalıştırın:

<img width="893" height="291" alt="image" src="https://github.com/user-attachments/assets/46b59f0f-f388-4669-b3a9-beccbca1f457" />






## İş Hattı Diyagramı (Pipeline Diagram) 

<img width="657" height="192" alt="image" src="https://github.com/user-attachments/assets/428877a4-e2d9-4231-9781-c1fc000f9dfa" />

