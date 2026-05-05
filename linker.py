# linker.py
# =========================================================
# RVI Linker  —  Birden fazla .o dosyasını birleştirir
#
# Görevler:
#   1. .o dosyalarını oku
#   2. Sembol tablolarını birleştir (merge)
#   3. text section'ları sırayla birleştir
#   4. Relocation'ları çöz (imm=0 placeholder'ları patch et)
#   5. Final HEX / binary dosyasını yaz
#
# Kullanım:
#   python linker.py main1.o main2.o -o output.hex -x
# =========================================================

import argparse
import sys

from lib.object_writer import read_object_file
from lib.machinecodegen import mcg
from lib.machinecodeconst import MachineCodeConst
from lib.parser import encode_offset, get_imm_I, get_imm_SB, get_imm_UJ

mcc = MachineCodeConst()

MEMORY_MAP = {
    "text": 0x00000000,
    "data": 0x10000000
}

TEXT_BASE = MEMORY_MAP["text"]
DATA_BASE = MEMORY_MAP["data"]


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

def load_and_merge(object_files):
    merged_text = []
    merged_data = []
    merged_symbols = {}
    merged_relocs = []
    file_offsets = {}

    current_text_addr = TEXT_BASE
    current_data_addr = DATA_BASE # Data başlangıcını takip et

    for obj_file in object_files:
        obj = read_object_file(obj_file)
        
        # --- TEXT Sembolleri ---
        # (Mevcut sembol döngünü koru ama 'data' mı 'text' mi kontrolü ekle)
        for sym, addr in obj['symbols'].items():
            # Basit bir mantık: Eğer obje dosyasında sembolün adresi 
            # text boyutundan büyükse veya özel bir işaret varsa data'dır.
            # Şimdilik en güvenli yol: Obj içindeki sembolün tipine bakmak.
            # Eğer tip ayrımı yoksa, text içine eklemeye devam et ama 
            # verilerin adreslerini DATA_BASE'e göre kaydırdığından emin ol.
            
            # Öneri: Obj dosyasını oluşturan parser'da sembollerin 
            # hangi section'da olduğunu ('text' veya 'data') belirtmesini sağla.
            section = obj.get('symbol_sections', {}).get(sym, 'text')
            
            if section == 'data':
                global_addr = addr + current_data_addr
            else:
                global_addr = addr + current_text_addr
                
            merged_symbols[sym] = global_addr

        # --- DATA Bölümünü Birleştir ---
        for d in obj.get('data', []):
            merged_data.append(d)
        
        # Dosya offsetlerini kaydet (Debug için önemli)
        file_offsets[obj_file] = current_text_addr
        
        # Her dosyadan sonra text adresini ilerlet
        current_text_addr += len(obj['text']) * 4
        # Eğer data eklendiyse data adresini de ilerlet (4 byte hizalı)
        current_data_addr += len(obj.get('data', [])) * 4 

    return merged_text, merged_data, merged_symbols, merged_relocs, file_offsets

# =========================================================
# ADIM 2: Relocation'ları çöz (patch)
# =========================================================

def resolve_relocations(merged_text, merged_symbols, merged_relocs):
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

        # Hedef adresi bul
        if symbol not in merged_symbols:
            raise Exception(
                f"HATA: '{symbol}' sembolü hiçbir .o dosyasında tanımlı değil!\n"
                f"  Referans: {opcode} @ 0x{address:04X}\n"
                f"  Mevcut semboller: {list(merged_symbols.keys())}"
            )

        target_addr = merged_symbols[symbol]
        instr_index = (address - TEXT_BASE) // 4

        # Mevcut binary'den register bilgilerini çıkar
        current_binary = _to_binary(merged_text[instr_index])

        # Relocation kaydındaki register bilgilerini kullan
        # (parser.py bunları relocation'a kaydetmişti)
        rd  = reloc.get('rd',  _get_rd(current_binary))
        rs1 = reloc.get('rs1', _get_rs1(current_binary))
        rs2 = reloc.get('rs2', _get_rs2(current_binary))

        # encode_offset ile doğru token'ı oluştur
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

        offset = target_addr - (address + 4)
        
        if offset % 2 != 0:
            raise Exception(f"Unaligned branch target: {symbol} (offset={offset})")

        if offset < -2048 or offset > 2047:
            raise Exception(f"Branch out of range: {symbol}, offset={offset}")
        print(f"    ✓ [{instr_index:3d}] 0x{address:04X}  {opcode:<6} "
              f"'{symbol}' → 0x{target_addr:04X}  (offset: {offset:+d})")

    return merged_text


# =========================================================
# ADIM 3: Çıktı dosyasına yaz
# =========================================================

def write_output(merged_text, merged_data, output_path, hex_mode):
    with open(output_path, 'w') as f:
        # TEXT başlangıcı
        f.write(f"@{TEXT_BASE:08X}\n")
        for instr in merged_text:
            line = _to_output(_to_binary(instr), hex_mode)
            f.write(line + '\n')

        # DATA başlangıcı (Yönergedeki 'ayrıştırılmalıdır' maddesi için şart)
        if merged_data:
            f.write(f"@{DATA_BASE:08X}\n")
            for data_val in merged_data:
                line = _to_output(_to_binary(data_val), hex_mode)
                f.write(line + '\n')

    print(f"\n[✓] Çıktı yazıldı: {output_path}  "
          f"({len(merged_text)} komut, HEX format)")


# =========================================================
# ANA FONKSİYON
# =========================================================

def link(object_files, output_path, hex_mode=True, verbose=False):
    """
    Tüm linkleme adımlarını sırayla çalıştırır.

    Parametreler:
        object_files : ['main1.o', 'main2.o', ...]
        output_path  : 'output.hex'
        hex_mode     : True → HEX çıktı, False → binary
        verbose      : True → detaylı çıktı
    """
    print("=" * 50)
    print(f"RVI Linker  —  {len(object_files)} dosya linkleniyor")
    print("=" * 50)

    # 1. Yükle ve birleştir
    merged_text, merged_data ,merged_symbols, merged_relocs, file_offsets = \
        load_and_merge(object_files)

    # 2. Relocation'ları çöz
    merged_text = resolve_relocations(merged_text, merged_symbols, merged_relocs)

    # 3. Çıktı yaz
    write_output(merged_text, merged_data, output_path, hex_mode)
    # 4. Özet
    print("\n=== Linkleme Özeti ===")
    print(f"  Dosyalar     : {', '.join(object_files)}")
    print(f"  Toplam komut : {len(merged_text)}")
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
    ap.add_argument("OBJECTS", nargs='+',
                    help="Birleştirilecek .o dosyaları (en az 2)")
    ap.add_argument('-o', "--output", default='output.hex',
                    help="Çıktı dosyası adı (default: output.hex)")
    ap.add_argument('-x', "--hex", action="store_true", default=True,
                    help="HEX formatında çıktı (default: açık)")
    ap.add_argument('-b', "--binary", action="store_true",
                    help="Binary formatında çıktı")
    ap.add_argument('-v', "--verbose", action="store_true",
                    help="Detaylı çıktı")
    return ap.parse_args()


def main():
    args       = get_arguments()
    hex_mode   = not args.binary

    if len(args.OBJECTS) < 1:
        sys.exit("En az bir .o dosyası gerekli.")

    try:
        link(args.OBJECTS, args.output, hex_mode, args.verbose)
    except Exception as e:
        print(f"\n[HATA] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()