# RVI — RV32I Assembler & Linker Sistemi
## Nesne dosyası üretimi, çoklu dosya bağlayıcı (linker) ve FPGA dağıtım hattına sahip iki geçişli bir RV32I assembler

📋 İçindekiler
Genel Bakış

Mimari

Özellikler

Proje Yapısı

Kurulum

Kullanım

Assembly Dili Referansı

Nesne Dosyası Formatı (Object File Format)

Linker Script

FPGA Dağıtımı

GUI

Örnek: LED Sayacı

İş Hattı Diyagramı (Pipeline Diagram)

## Genel Bakış
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

  python rvi.py main1.asm main2.asm --link -o output.hex -x

- Sadece Linker (Mevcut .o dosyalarından)

  python linker.py main1.o main2.o -o output.hex -x

  python linker.py main1.o main2.o -o output.hex --linker-script link.ld

- Varsayılan bir linker script oluşturma

   python linker.py --gen-ld

- Grafik Arayüz (GUI)

   python rvi_gui.py
