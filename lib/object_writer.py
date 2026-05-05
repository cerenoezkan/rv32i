# object_writer.py
# =========================================================
# RVI Object File  —  Yaz / Oku
#
# Format  (.o  →  JSON içerik):
#   {
#     "header":      { type, version, entry_point },
#     "text":        [ "01001011...", ... ],   # 32-bit binary string listesi
#     "data":        [ { "address": int, "value": "..." }, ... ],
#     "symbols":     { "LOOP": 8, "START": 0, ... },
#     "relocations": [
#         { "symbol": "FUNC_B", "address": 12, "type": "jal", "rd": "x1" },
#         ...
#     ]
#   }
# =========================================================

import json
import os

OBJECT_FORMAT_VERSION = 1
OBJECT_FORMAT_TYPE    = "RVI_OBJECT"


# =========================================================
# YAZMA
# =========================================================

def write_object_file(filename, text_section, data_section,
                      symbol_table, relocation_table):
    """
    Assembler çıktısını .o (JSON) formatında diske yazar.

    Parametreler:
        filename         : kaynak .asm dosyasının adı  ("main.asm")
                           → çıktı: "main.o"
        text_section     : ['01001011...', ...]
        data_section     : [{'address': int, 'value': '...'}, ...]
        symbol_table     : {'LOOP': 8, 'START': 0}
        relocation_table : [{'symbol': 'X', 'address': 4, 'type': 'jal', ...}]

    Dönüş:
        output_filename  : yazılan dosyanın tam yolu (str)
    """
    output_filename = _asm_to_obj(filename)

    obj = {
        "header": {
            "type":        OBJECT_FORMAT_TYPE,
            "version":     OBJECT_FORMAT_VERSION,
            "entry_point": 0,
            "source_file": os.path.basename(filename),
            "instr_count": len(text_section),
        },
        "text":        text_section,
        "data":        data_section,
        "symbols":     symbol_table,
        "relocations": relocation_table,
    }

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4)

    print(f"--- Nesne Dosyası Oluşturuldu: {output_filename} "
          f"({len(text_section)} komut, "
          f"{len(symbol_table)} sembol, "
          f"{len(relocation_table)} relocation) ---")

    return output_filename


# =========================================================
# OKUMA
# =========================================================

def read_object_file(filename):
    """
    .o dosyasını okur ve içeriği sözlük olarak döndürür.

    Dönüş:
        {
          'header':      {...},
          'text':        [...],
          'data':        [...],
          'symbols':     {...},
          'relocations': [...],
        }

    Hata durumları:
        - Dosya bulunamazsa  → FileNotFoundError
        - Format geçersizse  → ValueError
    """
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"Object dosyası bulunamadı: '{filename}'")

    with open(filename, "r", encoding="utf-8") as f:
        try:
            obj = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"'{filename}' geçerli bir JSON değil: {e}")

    _validate_object(obj, filename)
    return obj


# =========================================================
# DOĞRULAMA  (okuma sonrası kontrol)
# =========================================================

def _validate_object(obj, filename):
    """
    Okunan nesne dosyasının beklenen alanlara sahip olduğunu kontrol eder.
    Eksik ya da yanlış format varsa ValueError fırlatır.
    """
    required_keys = ("header", "text", "data", "symbols", "relocations")
    for key in required_keys:
        if key not in obj:
            raise ValueError(
                f"'{filename}' bozuk: '{key}' alanı eksik. "
                f"Bu dosya write_object_file() ile oluşturulmuş mu?"
            )

    header = obj["header"]
    if header.get("type") != OBJECT_FORMAT_TYPE:
        raise ValueError(
            f"'{filename}' tanınan bir RVI nesne dosyası değil "
            f"(type='{header.get('type')}' beklenen='{OBJECT_FORMAT_TYPE}')"
        )
    if header.get("version") != OBJECT_FORMAT_VERSION:
        raise ValueError(
            f"'{filename}' sürüm uyumsuzluğu: "
            f"dosya v{header.get('version')}, beklenen v{OBJECT_FORMAT_VERSION}"
        )


# =========================================================
# YARDIMCI
# =========================================================

def _asm_to_obj(filename):
    """'main.asm'  →  'main.o'"""
    base = filename.rsplit('.', 1)[0]
    return base + ".o"


def print_object_info(filename):
    """
    .o dosyasının özetini terminale basar.
    Debug ve rapor için kullanışlıdır.
    """
    obj = read_object_file(filename)
    h   = obj["header"]
    print(f"\n=== Object File: {filename} ===")
    print(f"  Kaynak      : {h.get('source_file', '?')}")
    print(f"  Komut sayısı: {h.get('instr_count', len(obj['text']))}")
    print(f"  Entry point : 0x{h.get('entry_point', 0):04X}")
    print(f"  Semboller   : {list(obj['symbols'].keys())}")
    print(f"  Relocationlar:")
    if obj["relocations"]:
        for r in obj["relocations"]:
            print(f"    0x{r['address']:04X}  {r['type']:<6}  → {r['symbol']}")
    else:
        print("    (yok)")