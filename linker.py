# linker.py
# =========================================================
# RVI Linker  —  Birden fazla .o dosyasını birleştirir
#
# Görevler:
#   1. .o dosyalarını oku
#   2. Sembol tablolarını birleştir (sadece exports görünür olur)
#   3. text ve data section'ları sırayla birleştir
#   4. Relocation'ları çöz (imm=0 placeholder'ları patch et)
#   5. Final HEX / binary dosyasını yaz
#
# Global/Extern Kuralları:
#   - Bir sembol sadece kendi dosyasında tanımlıdır (lokal).
#   - .globl ile işaretlenirse diğer dosyalara görünür olur (export).
#   - .extern ile işaretlenirse "başka dosyadan bekliyorum" anlamına gelir (import).
#   - Aynı isimde iki export varsa hata fırlatılır.
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

DEFAULT_TEXT_BASE = 0x00000000
DEFAULT_DATA_BASE = 0x00010000


# =========================================================
# LINKER SCRIPT OKUYUCU
# =========================================================

def parse_linker_script(script_path):
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
            if not line:
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if key in config:
                    try:
                        config[key] = int(val, 0)
                        print(f"    {key} = 0x{config[key]:08X}")
                    except ValueError:
                        print(f"[!] Geçersiz değer: {key} = {val}, varsayılan kullanılıyor.")
    return config


def write_default_linker_script(path='link.ld'):
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
    bits = binary_str if len(binary_str) == 32 else format(int(binary_str, 16), '032b')
    return f"x{int(bits[20:25], 2)}"

def _get_rs1(binary_str):
    bits = binary_str if len(binary_str) == 32 else format(int(binary_str, 16), '032b')
    return f"x{int(bits[12:17], 2)}"

def _get_rs2(binary_str):
    bits = binary_str if len(binary_str) == 32 else format(int(binary_str, 16), '032b')
    return f"x{int(bits[7:12], 2)}"

def _to_binary(instr_str):
    if len(instr_str) == 32 and all(c in '01' for c in instr_str):
        return instr_str
    return format(int(instr_str, 16), '032b')

def _to_output(binary_str, hex_mode):
    if hex_mode:
        return '%08X' % int(binary_str, 2)
    return binary_str


# =========================================================
# ADIM 1: Object dosyalarını yükle, section'ları birleştir
# =========================================================

def load_and_merge(object_files, text_base, data_base):
    """
    Tüm .o dosyalarını okur ve sırayla birleştirir.

    Global/Lokal sembol kuralı:
      - Her dosyanın kendi sembol tablosu önce lokal_symbols'e alınır.
      - Sadece exports listesindeki semboller global_symbols'e eklenir.
      - Relocation çözümünde önce lokal, sonra global aranır.

    Dönüş:
        merged_text      : tüm text komutları
        merged_data      : tüm data kelimeleri
        global_symbols   : export edilen semboller (dosyalar arası görünür)
        local_symbols    : {obj_file: {sembol: adres}} (dosya içi semboller)
        merged_relocs    : relocation listesi (hangi dosyaya ait bilgisi de var)
        file_offsets     : her dosyanın text başlangıç adresi
        symbol_scopes    : {sembol_adı: ('GLOBAL'|'LOCAL', kaynak_dosya)}
    """
    merged_text    = []
    merged_data    = []
    global_symbols = {}   # sadece .globl ile export edilenler
    local_symbols  = {}   # {obj_file: {sembol: global_adres}}
    merged_relocs  = []
    file_offsets   = {}
    symbol_scopes  = {}   # GUI için: {sembol: ('GLOBAL'/'LOCAL', obj_file)}

    current_text_addr = text_base
    current_data_addr = data_base

    for obj_file in object_files:
        print(f"\n[+] Yükleniyor: {obj_file}")
        obj = read_object_file(obj_file)

        base_text_addr = current_text_addr
        base_data_addr = current_data_addr
        file_offsets[obj_file] = base_text_addr

        exports = set(obj.get('exports', []))
        imports = set(obj.get('imports', []))
        text_size = len(obj['text']) * 4

        if exports:
            print(f"    Exports : {sorted(exports)}")
        if imports:
            print(f"    Imports : {sorted(imports)}")

        # --- Sembolleri yerleştir ---
        file_sym_map = {}

        for sym, addr in obj['symbols'].items():
            # Sembolün text mi data mı section'ında olduğunu belirle
            if addr < text_size:
                global_addr = addr + base_text_addr
            else:
                global_addr = (addr - text_size) + base_data_addr

            file_sym_map[sym] = global_addr

            if sym in exports:
                # Global olarak dışa aç — çakışma kontrolü
                if sym in global_symbols:
                    raise Exception(
                        f"HATA: Global sembol '{sym}' birden fazla dosyada export edilmiş!\n"
                        f"  İlk tanım : 0x{global_symbols[sym]:08X}\n"
                        f"  Çakışan   : {obj_file} → 0x{global_addr:08X}"
                    )
                global_symbols[sym] = global_addr
                symbol_scopes[sym] = ('GLOBAL', os.path.basename(obj_file))
                print(f"    [GLOBAL] {sym} → 0x{global_addr:08X}")
            else:
                # Lokal sembol — sadece bu dosyada görünür
                symbol_scopes[sym] = ('LOCAL', os.path.basename(obj_file))
                print(f"    [LOCAL ] {sym} → 0x{global_addr:08X}")

        local_symbols[obj_file] = file_sym_map

        # --- Imports doğrulaması (bilgi amaçlı, linker sonunda kontrol edilir) ---
        for imp in imports:
            if imp not in obj['symbols']:
                print(f"    [EXTERN] '{imp}' bu dosyada tanımsız — linker çözecek")

        # --- Relocation'ları global listeye ekle ---
        for reloc in obj['relocations']:
            global_reloc = {
                **reloc,
                'address':   reloc['address'] + base_text_addr,
                'obj_file':  obj_file,
            }
            merged_relocs.append(global_reloc)
            extern_tag = " [extern]" if reloc.get('extern') else ""
            print(f"    Relocation: {reloc['type']} → '{reloc['symbol']}'"
                  f" @ 0x{global_reloc['address']:08X}{extern_tag}")

        # --- Text section birleştir ---
        merged_text.extend(obj['text'])
        current_text_addr += len(obj['text']) * 4
        print(f"    [TEXT] {len(obj['text'])} komut "
              f"(0x{base_text_addr:08X} – 0x{current_text_addr - 4:08X})")

        # --- Data section birleştir ---
        data_section = obj.get('data', [])
        if data_section:
            merged_data.extend(data_section)
            old = current_data_addr
            current_data_addr += len(data_section) * 4
            print(f"    [DATA] {len(data_section)} kelime "
                  f"(0x{old:08X} – 0x{current_data_addr - 4:08X})")
        else:
            print(f"    [DATA] Bu dosyada data section yok.")

    return (merged_text, merged_data, global_symbols,
            local_symbols, merged_relocs, file_offsets, symbol_scopes)


# =========================================================
# ADIM 2: Relocation'ları çöz
# =========================================================

def resolve_relocations(merged_text, global_symbols, local_symbols,
                        merged_relocs, text_base):
    """
    Her relocation için sembolü çözer:
      1. Önce reloc'un ait olduğu dosyanın lokal sembol tablosuna bak.
      2. Bulamazsan global sembol tablosuna bak (.globl export'lar).
      3. İkisinde de yoksa hata fırlat.
    """
    if not merged_relocs:
        print("\n[✓] Çözülecek relocation yok.")
        return merged_text

    print(f"\n[+] {len(merged_relocs)} relocation çözülüyor...")

    for reloc in merged_relocs:
        symbol   = reloc['symbol']
        address  = reloc['address']
        opcode   = reloc['type']
        obj_file = reloc.get('obj_file', '')

        # Sembol arama sırası: lokal → global
        file_locals  = local_symbols.get(obj_file, {})
        target_addr  = file_locals.get(symbol) or global_symbols.get(symbol)

        if target_addr is None:
            raise Exception(
                f"HATA: '{symbol}' sembolü çözülemedi!\n"
                f"  Referans dosya : {obj_file}\n"
                f"  Adres          : 0x{address:08X}\n"
                f"  İpucu          : Sembolü tanımlayan dosyada '.globl {symbol}' "
                f"satırı var mı?\n"
                f"  Mevcut globals : {list(global_symbols.keys())}"
            )

        instr_index    = (address - text_base) // 4
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

        resolved   = encode_offset(fake_tokens, address, target_addr)
        binary_res = mcg.convert_to_binary(resolved)

        if binary_res is None:
            raise Exception(
                f"HATA: '{opcode}' komutu için binary üretilemedi "
                f"(sembol: '{symbol}')"
            )

        patched_instr, _ = binary_res
        merged_text[instr_index] = patched_instr

        scope  = "LOCAL" if symbol in file_locals else "GLOBAL"
        offset = target_addr - address
        print(f"    ✓ [{instr_index:3d}] 0x{address:08X}  {opcode:<6} "
              f"'{symbol}' [{scope}] → 0x{target_addr:08X}  (offset: {offset:+d})")

    return merged_text


# =========================================================
# ADIM 3: Çıktı dosyasına yaz
# =========================================================

def write_output(merged_text, merged_data, output_path, hex_mode=True,
                 text_base=DEFAULT_TEXT_BASE, data_base=DEFAULT_DATA_BASE):
    with open(output_path, 'w') as f:
        f.write(f"// TEXT SECTION  (base: 0x{text_base:08X})\n")
        f.write(f"@{text_base:08X}\n")
        for instr in merged_text:
            f.write(_to_output(_to_binary(instr), hex_mode) + '\n')

        if merged_data:
            f.write(f"\n// DATA SECTION  (base: 0x{data_base:08X})\n")
            f.write(f"@{data_base:08X}\n")
            for word in merged_data:
                f.write(_to_output(_to_binary(word), hex_mode) + '\n')

    total = len(merged_text) + len(merged_data)
    print(f"\n[✓] Çıktı yazıldı: {output_path}  "
          f"({len(merged_text)} komut + {len(merged_data)} data = "
          f"{total} toplam, {'HEX' if hex_mode else 'binary'})")


# =========================================================
# ANA FONKSİYON
# =========================================================

def link(object_files, output_path, hex_mode=True, verbose=False,
         linker_script=None, gen_default_ld=False):

    if gen_default_ld:
        write_default_linker_script()
        return {}, {}, {}

    print("=" * 55)
    print(f"RVI Linker  —  {len(object_files)} dosya linkleniyor")
    print("=" * 55)

    config    = parse_linker_script(linker_script)
    text_base = config['TEXT_BASE']
    data_base = config['DATA_BASE']
    print(f"\n    TEXT_BASE = 0x{text_base:08X}")
    print(f"    DATA_BASE = 0x{data_base:08X}")

    (merged_text, merged_data, global_symbols,
     local_symbols, merged_relocs, file_offsets,
     symbol_scopes) = load_and_merge(object_files, text_base, data_base)

    merged_text = resolve_relocations(
        merged_text, global_symbols, local_symbols, merged_relocs, text_base
    )

    write_output(merged_text, merged_data, output_path, hex_mode,
                 text_base, data_base)

    # Tüm sembolleri tek dict'te topla (adres bilgisiyle)
    all_symbols = {}
    for obj_file, fmap in local_symbols.items():
        for sym, addr in fmap.items():
            all_symbols[sym] = addr

    print("\n=== Linkleme Özeti ===")
    print(f"  Dosyalar      : {', '.join(object_files)}")
    print(f"  TEXT komutu   : {len(merged_text)}")
    print(f"  DATA kelimesi : {len(merged_data)}")
    print(f"  Global semb.  : {global_symbols}")
    print(f"  Toplam semb.  : {len(all_symbols)}")
    print(f"  Çıktı         : {output_path}")

    # Dönüş: global_symbols, all_symbols (lokal dahil), symbol_scopes
    return global_symbols, all_symbols, symbol_scopes


# =========================================================
# KOMUT SATIRI
# =========================================================

def get_arguments():
    ap = argparse.ArgumentParser(
        description="RVI Linker — RV32I object dosyalarını birleştirir"
    )
    ap.add_argument("OBJECTS", nargs='*',
                    help="Birleştirilecek .o dosyaları (en az 2)")
    ap.add_argument('-o', "--output", default='output.hex')
    ap.add_argument('-x', "--hex", action="store_true", default=True)
    ap.add_argument('-b', "--binary", action="store_true")
    ap.add_argument('-v', "--verbose", action="store_true")
    ap.add_argument('--linker-script', metavar='FILE')
    ap.add_argument('--gen-ld', action="store_true")
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