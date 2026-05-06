# linker.py
# =========================================================
# RVI Linker  —  Birden fazla .o dosyasını birleştirir
#
# Görevler:
#   1. .o dosyalarını oku
#   2. Sembol tablolarını birleştir (merge)
#   3. text ve data section'ları sırayla birleştir
#   4. Relocation'ları çöz (imm=0 placeholder'ları patch et)
#   5. Final HEX / binary dosyasını yaz
#
# Linker Script Desteği:
#   Varsayılan veya kullanıcı tanımlı .ld dosyası ile
#   TEXT_BASE ve DATA_BASE adresleri yapılandırılabilir.
#
# Kullanım:
#   python linker.py main1.o main2.o -o output.hex -x
#   python linker.py main1.o main2.o -o output.hex --linker-script link.ld
# =========================================================

import argparse
import sys
import os

from lib.object_writer import read_object_file
from lib.machinecodegen import mcg
from lib.machinecodeconst import MachineCodeConst
from lib.parser import encode_offset, get_imm_I, get_imm_SB, get_imm_UJ

mcc = MachineCodeConst()

# Varsayılan bellek adresleri (FPGA BRAM)
DEFAULT_TEXT_BASE = 0x00000000
DEFAULT_DATA_BASE = 0x00010000  # 64KB offset — data section başlangıcı


# =========================================================
# LINKER SCRIPT OKUYUCU
# =========================================================

def parse_linker_script(script_path):
    """
    Basit linker script (.ld) dosyasını okur.

    Desteklenen format:
        TEXT_BASE = 0x00000000;
        DATA_BASE = 0x00010000;

    Dönüş:
        {'TEXT_BASE': 0x00000000, 'DATA_BASE': 0x00010000}
    """
    config = {
        'TEXT_BASE': DEFAULT_TEXT_BASE,
        'DATA_BASE': DEFAULT_DATA_BASE,
    }

    if not script_path:
        return config

    if not os.path.exists(script_path):
        print(f"[!] Linker script bulunamadı: {script_path}, varsayılan adresler kullanılıyor.")
        return config

    print(f"\n[+] Linker script okunuyor: {script_path}")

    with open(script_path, 'r') as f:
        for line in f:
            line = line.split('#')[0].strip().rstrip(';').replace(' ', '')
            if line.startswith('#') or not line:
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if key in config:
                    try:
                        config[key] = int(val, 0)  # 0x... veya decimal
                        print(f"    {key} = 0x{config[key]:08X}")
                    except ValueError:
                        print(f"[!] Geçersiz değer: {key} = {val}, varsayılan kullanılıyor.")

    return config


def write_default_linker_script(path='link.ld'):
    """
    Varsayılan linker script dosyasını oluşturur.
    Kullanıcı referans olarak kullanabilir.
    """
    content = (
        "# RVI Linker Script\n"
        "# FPGA BRAM bellek düzeni\n"
        "#\n"
        "# TEXT_BASE : Program kodunun başlangıç adresi\n"
        "# DATA_BASE : Veri bölümünün başlangıç adresi\n\n"
        "TEXT_BASE = 0x00000000;\n"
        "DATA_BASE = 0x00010000;\n"
    )
    with open(path, 'w') as f:
        f.write(content)
    print(f"[✓] Varsayılan linker script oluşturuldu: {path}")


# =========================================================
# YARDIMCI: binary string içinden register numarasını çıkar
# =========================================================

def _get_rd(binary_str):
    """32-bit binary string → rd register adı  (bit 11-7)"""
    bits = binary_str if len(binary_str) == 32 else format(int(binary_str, 16), '032b')
    rd_num = int(bits[20:25], 2)
    return f"x{rd_num}"

def _get_rs1(binary_str):
    """32-bit binary string → rs1 register adı  (bit 19-15)"""
    bits = binary_str if len(binary_str) == 32 else format(int(binary_str, 16), '032b')
    rs1_num = int(bits[12:17], 2)
    return f"x{rs1_num}"

def _get_rs2(binary_str):
    """32-bit binary string → rs2 register adı  (bit 24-20)"""
    bits = binary_str if len(binary_str) == 32 else format(int(binary_str, 16), '032b')
    rs2_num = int(bits[7:12], 2)
    return f"x{rs2_num}"

def _to_binary(instr_str):
    """HEX veya binary string → 32-bit binary string"""
    if len(instr_str) == 32 and all(c in '01' for c in instr_str):
        return instr_str
    return format(int(instr_str, 16), '032b')

def _to_output(binary_str, hex_mode):
    """32-bit binary string → çıktı formatı (HEX veya binary)"""
    if hex_mode:
        return '%08X' % int(binary_str, 2)
    return binary_str


# =========================================================
# ADIM 1: Object dosyalarını yükle, section'ları birleştir
# =========================================================

def load_and_merge(object_files, text_base, data_base):
    """
    Tüm .o dosyalarını okur ve sırayla birleştirir.
    Text ve data section'ları ayrı ayrı yönetilir.

    Dönüş:
        merged_text      : ['01001011...', ...]  (tüm text komutları sırayla)
        merged_data      : ['DEADBEEF', ...]     (tüm data kelimeleri sırayla)
        merged_symbols   : {'LOOP': 8, 'FUNC': 48, ...}  (global adresler)
        merged_relocs    : [{'symbol':..., 'address':..., 'type':...}, ...]
        file_offsets     : {'main1.o': 0, 'main2.o': 48, ...}
    """
    merged_text    = []
    merged_data    = []
    merged_symbols = {}
    merged_relocs  = []
    file_offsets   = {}

    current_text_addr = text_base
    current_data_addr = data_base

    for obj_file in object_files:
        print(f"\n[+] Yükleniyor: {obj_file}")
        obj = read_object_file(obj_file)

        base_text_addr = current_text_addr
        base_data_addr = current_data_addr
        file_offsets[obj_file] = base_text_addr

        # --- Text section sembollerini global tabloya ekle ---
        for sym, addr in obj['symbols'].items():
            # Sembol data section'a mı text section'a mı ait?
            # Basit kural: adres text section boyutundan küçükse text, değilse data
            text_size = len(obj['text']) * 4
            if addr < text_size:
                global_addr = addr + base_text_addr
            else:
                # Data section sembolü — text_size'ı çıkar, data base ekle
                global_addr = (addr - text_size) + base_data_addr

            if sym in merged_symbols:
                raise Exception(
                    f"HATA: '{sym}' sembolü birden fazla dosyada tanımlı!\n"
                    f"  İlk tanım : 0x{merged_symbols[sym]:08X}\n"
                    f"  Çakışan   : {obj_file} → 0x{global_addr:08X}"
                )
            merged_symbols[sym] = global_addr
            print(f"    Sembol: {sym} → 0x{global_addr:08X}")

        # --- Relocation'ları global listeye ekle ---
        for reloc in obj['relocations']:
            global_reloc = {**reloc, 'address': reloc['address'] + base_text_addr}
            merged_relocs.append(global_reloc)
            print(f"    Relocation: {reloc['type']} → '{reloc['symbol']}' "
                  f"@ 0x{global_reloc['address']:08X}")

        # --- Text section'ı birleştir ---
        merged_text.extend(obj['text'])
        current_text_addr += len(obj['text']) * 4
        print(f"    [TEXT] {len(obj['text'])} komut eklendi "
              f"(0x{base_text_addr:08X} – 0x{current_text_addr - 4:08X})")

        # --- Data section'ı birleştir ---
        data_section = obj.get('data', [])
        if data_section:
            merged_data.extend(data_section)
            old_data_addr = current_data_addr
            current_data_addr += len(data_section) * 4
            print(f"    [DATA] {len(data_section)} kelime eklendi "
                  f"(0x{old_data_addr:08X} – 0x{current_data_addr - 4:08X})")
        else:
            print(f"    [DATA] Bu dosyada data section yok.")

    return merged_text, merged_data, merged_symbols, merged_relocs, file_offsets


# =========================================================
# ADIM 2: Relocation'ları çöz (patch)
# =========================================================

def resolve_relocations(merged_text, merged_symbols, merged_relocs, text_base):
    """
    Her relocation kaydı için:
      1. Hedef sembolün adresini merged_symbols'dan bul
      2. PC-relative offset'i hesapla
      3. merged_text içindeki placeholder komutunu patch et
    """
    if not merged_relocs:
        print("\n[✓] Çözülecek relocation yok.")
        return merged_text

    print(f"\n[+] {len(merged_relocs)} relocation çözülüyor...")

    for reloc in merged_relocs:
        symbol  = reloc['symbol']
        address = reloc['address']
        opcode  = reloc['type']

        if symbol not in merged_symbols:
            raise Exception(
                f"HATA: '{symbol}' sembolü hiçbir .o dosyasında tanımlı değil!\n"
                f"  Referans: {opcode} @ 0x{address:08X}\n"
                f"  Mevcut semboller: {list(merged_symbols.keys())}"
            )

        target_addr = merged_symbols[symbol]
        instr_index = (address - text_base) // 4

        current_binary = _to_binary(merged_text[instr_index])

        rd  = reloc.get('rd',  _get_rd(current_binary))
        rs1 = reloc.get('rs1', _get_rs1(current_binary))
        rs2 = reloc.get('rs2', _get_rs2(current_binary))

        fake_tokens = {
            'opcode': opcode,
            'lineno': 0,
            'rd':     rd,
            'rs1':    rs1,
            'rs2':    rs2,
        }

        resolved     = encode_offset(fake_tokens, address, target_addr)
        binary_res   = mcg.convert_to_binary(resolved)

        if binary_res is None:
            raise Exception(
                f"HATA: '{opcode}' komutu için binary üretilemedi "
                f"(sembol: '{symbol}')"
            )

        patched_instr, _ = binary_res
        merged_text[instr_index] = patched_instr

        offset = target_addr - address
        print(f"    ✓ [{instr_index:3d}] 0x{address:08X}  {opcode:<6} "
              f"'{symbol}' → 0x{target_addr:08X}  (offset: {offset:+d})")

    return merged_text


# =========================================================
# ADIM 3: Çıktı dosyasına yaz
# =========================================================

def write_output(merged_text, merged_data, output_path, hex_mode=True,
                 text_base=DEFAULT_TEXT_BASE, data_base=DEFAULT_DATA_BASE):
    """
    Final komut listesini ve data section'ı dosyaya yazar.

    Çıktı formatı:
        @<adres>   → bellek adresi direktifi  (Verilog $readmemh uyumlu)
        <veri>     → HEX veya binary veri

    hex_mode=True  → HEX  (FPGA için önerilen)
    hex_mode=False → binary
    """
    with open(output_path, 'w') as f:
        # --- Text section ---
        f.write(f"// TEXT SECTION  (base: 0x{text_base:08X})\n")
        f.write(f"@{text_base:08X}\n")
        for instr in merged_text:
            line = _to_output(_to_binary(instr), hex_mode)
            f.write(line + '\n')

        # --- Data section (varsa) ---
        if merged_data:
            f.write(f"\n// DATA SECTION  (base: 0x{data_base:08X})\n")
            f.write(f"@{data_base:08X}\n")
            for word in merged_data:
                line = _to_output(_to_binary(word), hex_mode)
                f.write(line + '\n')

    total = len(merged_text) + len(merged_data)
    print(f"\n[✓] Çıktı yazıldı: {output_path}  "
          f"({len(merged_text)} komut + {len(merged_data)} data kelimesi = "
          f"{total} toplam, {'HEX' if hex_mode else 'binary'} format)")


# =========================================================
# ANA FONKSİYON
# =========================================================

def link(object_files, output_path, hex_mode=True, verbose=False,
         linker_script=None, gen_default_ld=False):
    """
    Tüm linkleme adımlarını sırayla çalıştırır.

    Parametreler:
        object_files    : ['main1.o', 'main2.o', ...]
        output_path     : 'output.hex'
        hex_mode        : True → HEX çıktı, False → binary
        verbose         : True → detaylı çıktı
        linker_script   : '.ld' dosyası yolu (None → varsayılan adresler)
        gen_default_ld  : True → varsayılan link.ld oluştur ve çık
    """
    if gen_default_ld:
        write_default_linker_script()
        return {}

    print("=" * 55)
    print(f"RVI Linker  —  {len(object_files)} dosya linkleniyor")
    print("=" * 55)

    # 0. Linker script oku
    config    = parse_linker_script(linker_script)
    text_base = config['TEXT_BASE']
    data_base = config['DATA_BASE']
    print(f"\n    TEXT_BASE = 0x{text_base:08X}")
    print(f"    DATA_BASE = 0x{data_base:08X}")

    # 1. Yükle ve birleştir
    merged_text, merged_data, merged_symbols, merged_relocs, file_offsets = \
        load_and_merge(object_files, text_base, data_base)

    # 2. Relocation'ları çöz
    merged_text = resolve_relocations(
        merged_text, merged_symbols, merged_relocs, text_base)

    # 3. Çıktı yaz
    write_output(merged_text, merged_data, output_path, hex_mode,
                 text_base, data_base)

    # 4. Özet
    print("\n=== Linkleme Özeti ===")
    print(f"  Dosyalar     : {', '.join(object_files)}")
    print(f"  TEXT komutu  : {len(merged_text)}")
    print(f"  DATA kelimesi: {len(merged_data)}")
    print(f"  Semboller    : {merged_symbols}")
    print(f"  Çıktı        : {output_path}")

    return merged_symbols


# =========================================================
# KOMUT SATIRI KULLANIMI
# =========================================================

def get_arguments():
    ap = argparse.ArgumentParser(
        description="RVI Linker — RV32I object dosyalarını birleştirir"
    )
    ap.add_argument("OBJECTS", nargs='*',
                    help="Birleştirilecek .o dosyaları (en az 2)")
    ap.add_argument('-o', "--output", default='output.hex',
                    help="Çıktı dosyası adı (default: output.hex)")
    ap.add_argument('-x', "--hex", action="store_true", default=True,
                    help="HEX formatında çıktı (default: açık)")
    ap.add_argument('-b', "--binary", action="store_true",
                    help="Binary formatında çıktı")
    ap.add_argument('-v', "--verbose", action="store_true",
                    help="Detaylı çıktı")
    ap.add_argument('--linker-script', metavar='FILE',
                    help="Linker script dosyası (.ld)  örn: link.ld")
    ap.add_argument('--gen-ld', action="store_true",
                    help="Varsayılan link.ld dosyasını oluştur ve çık")
    return ap.parse_args()


def main():
    args     = get_arguments()
    hex_mode = not args.binary

    if args.gen_ld:
        write_default_linker_script()
        sys.exit(0)

    if len(args.OBJECTS) < 2:
        sys.exit("En az iki .o dosyası gerekli.")

    try:
        link(
            args.OBJECTS,
            args.output,
            hex_mode,
            args.verbose,
            linker_script=args.linker_script,
            gen_default_ld=args.gen_ld,
        )
    except Exception as e:
        print(f"\n[HATA] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()