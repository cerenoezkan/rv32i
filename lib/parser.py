# parser.py
# =========================================================
# tokenizer'dan gelen token'ların gramer kurallarına uygunluğunu kontrol eder.
# Linker projesi için genişletilmiş versiyon:
#   - parse_pass_one  : sembol tablosu oluşturur (değişmedi)
#   - parse_pass_two  : binary üretir, label'ları HEMEN ÇÖZMEZ →
#                       relocation_table'a kaydeder (kritik değişiklik)
#   - parse_input     : (text_section, data_section, symbol_table,
#                        relocation_table) döndürür
# =========================================================

import ply.yacc as yacc
import sys

from lib.tokenizer import tokens, reset_lineno
from lib.machinecodegen import mcg
from lib.cprint import cprint as cp
from lib.machinecodeconst import MachineCodeConst

mcc = MachineCodeConst()


# =========================================================
# PROGRAM RULES
# =========================================================

def p_program_statement(p):
    'program : statement'
    p[0] = {
        'type': 'instruction',
        'tokens': p[1]
    }

def p_program_label(p):
    'program : LABEL COLUMN NEWLINE'
    p[0] = {
        'type': 'label',
        'tokens': {
            'label': p[1],
            'lineno': p.lineno(1)
        }
    }

def p_program_empty(p):
    '''program : NEWLINE
               | '''
    p[0] = None


# =========================================================
# DIRECTIVE
# =========================================================

# =========================================================
# DIRECTIVE (Genişletilmiş: Global ve External Destekli)
# =========================================================

# 1. Kelime içeren direktifler (.global TOPLA, .extern TOPLA)
def p_statement_directive_symbol(p):
    'statement : DIRECTIVE LABEL NEWLINE'
    p[0] = {
        'type': 'directive',
        'directive': p[1],
        'symbol': p[2],  # 'TOPLA' kelimesini burası yakalar
        'lineno': p.lineno(1)
    }

# 2. Sayı içeren direktifler (.word 100, .org 0x10)
def p_statement_directive_imm(p):
    'statement : DIRECTIVE IMMEDIATE NEWLINE'
    p[0] = {
        'type': 'directive',
        'directive': p[1],
        'value': p[2],
        'lineno': p.lineno(1)
    }

# 3. Tek başına duran direktifler (.text, .data)
def p_statement_directive_single(p):
    'statement : DIRECTIVE NEWLINE'
    p[0] = {
        'type': 'directive',
        'directive': p[1],
        'value': None,
        'lineno': p.lineno(1)
    }

# =========================================================
# R TYPE
# =========================================================

def p_statement_R(p):
    'statement : OPCODE register COMMA register COMMA register NEWLINE'
    if p[1] not in mcc.INSTR_TYPE_R:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Invalid R-type opcode '{p[1]}'")
        raise SyntaxError
    p[0] = {
        'opcode': p[1],
        'rd':  p[2],
        'rs1': p[4],
        'rs2': p[6],
        'lineno': p.lineno(1)
    }


# =========================================================
# I / S / SB TYPE  (immediate sayı)
# =========================================================

def p_statement_I_S_SB(p):
    'statement : OPCODE register COMMA register COMMA IMMEDIATE NEWLINE'
    opcode = p[1]

    if opcode in mcc.INSTR_TYPE_I:
        _, imm, _ = get_imm_I(p[6], p.lineno(6))
        p[0] = {
            'opcode': opcode, 'rd': p[2], 'rs1': p[4],
            'imm': imm, 'lineno': p.lineno(1)
        }
    elif opcode in mcc.INSTR_TYPE_S:
        _, imm, _ = get_imm_S(p[6], p.lineno(6))
        p[0] = {
            'opcode': opcode, 'rs1': p[2], 'rs2': p[4],
            'imm': imm, 'lineno': p.lineno(1)
        }
    elif opcode in mcc.INSTR_TYPE_SB:
        _, imm, _ = get_imm_SB(p[6], p.lineno(6))
        p[0] = {
            'opcode': opcode, 'rs1': p[2], 'rs2': p[4],
            'imm': imm, 'lineno': p.lineno(1)
        }
    else:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Invalid opcode '{opcode}' for this format")
        raise SyntaxError


# =========================================================
# LOAD / STORE  →  lw x4, 4(x1)  /  sw x3, 4(x1)
# =========================================================

def p_statement_load_store_offset(p):
    'statement : OPCODE register COMMA IMMEDIATE LPAREN register RPAREN NEWLINE'
    opcode = p[1]

    if opcode in mcc.INSTR_TYPE_I:        # lw, lb, lh …
        _, imm, _ = get_imm_I(p[4], p.lineno(4))
        p[0] = {
            'opcode': opcode, 'rd': p[2], 'rs1': p[6],
            'imm': imm, 'lineno': p.lineno(1)
        }
    elif opcode in mcc.INSTR_TYPE_S:      # sw, sb, sh …
        _, imm, _ = get_imm_S(p[4], p.lineno(4))
        p[0] = {
            'opcode': opcode, 'rs1': p[6], 'rs2': p[2],
            'imm': imm, 'lineno': p.lineno(1)
        }
    else:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Unsupported load/store opcode '{opcode}'")
        raise SyntaxError


# =========================================================
# U / UJ TYPE  →  lui x1, 100000  /  jal x1, 100000
# =========================================================

def p_statement_U_UJ(p):
    'statement : OPCODE register COMMA IMMEDIATE NEWLINE'
    opcode = p[1]

    if opcode in mcc.INSTR_TYPE_U:
        _, imm, _ = get_imm_U(p[4], p.lineno(4))
        p[0] = {
            'opcode': opcode, 'rd': p[2],
            'imm': imm, 'lineno': p.lineno(1)
        }
    elif opcode in mcc.INSTR_TYPE_UJ:
        _, imm, _ = get_imm_UJ(p[4], p.lineno(4))
        p[0] = {
            'opcode': opcode, 'rd': p[2],
            'imm': imm, 'lineno': p.lineno(1)
        }
    else:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Invalid opcode '{opcode}' for U/UJ format")
        raise SyntaxError


# =========================================================
# LABEL TARGETS
# NOT: Bu kurallar artık imm hesaplamaz.
#      Sadece label adını kaydeder; linker/pass-two relocation tablosuna yazar.
# =========================================================

def p_statement_UJ_LABEL(p):
    'statement : OPCODE register COMMA LABEL NEWLINE'
    # jal x1, LOOP  veya  jalr x1, x2, LABEL  (UJ + jalr)
    if p[1] not in mcc.INSTR_TYPE_UJ and p[1] != mcc.INSTR_JALR:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Opcode '{p[1]}' cannot use a label target")
        raise SyntaxError
    p[0] = {
        'opcode': p[1],
        'rd':     p[2],
        'label':  p[4],
        'lineno': p.lineno(1)
    }

def p_statement_SB_LABEL(p):
    'statement : OPCODE register COMMA register COMMA LABEL NEWLINE'
    # beq x1, x2, LOOP  veya  jalr x1, x2, LABEL
    if p[1] not in mcc.INSTR_TYPE_SB and p[1] != mcc.INSTR_JALR:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Opcode '{p[1]}' cannot use a label target")
        raise SyntaxError

    if p[1] in mcc.INSTR_TYPE_SB:
        p[0] = {
            'opcode': p[1],
            'rs1':   p[2],
            'rs2':   p[4],
            'label': p[6],
            'lineno': p.lineno(1)
        }
    else:  # jalr
        p[0] = {
            'opcode': p[1],
            'rd':    p[2],
            'rs1':   p[4],
            'label': p[6],
            'lineno': p.lineno(1)
        }


# =========================================================
# REGISTER VALIDATION
# =========================================================

def p_register(p):
    'register : REGISTER'
    num = int(p[1][1:])
    if num < 0 or num > 31:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Invalid register '{p[1]}' (x0–x31 expected)")
        raise SyntaxError
    p[0] = p[1]


# =========================================================
# EMPTY LINE
# =========================================================

def p_statement_none(p):
    'statement : NEWLINE'
    p[0] = None


# =========================================================
# SYNTAX ERROR
# =========================================================

def p_error(p):
    if p:
        cp.cprint_fail(
            f"Syntax Error: unexpected token '{p.value}' at line {p.lineno}"
        )
    else:
        cp.cprint_fail("Syntax Error at EOF — son satırda newline var mı?")


# =========================================================
# IMM HESAPLAMA FONKSİYONLARI
# =========================================================

def get_imm_I(val, ln):
    try:
        v = int(val)
    except (ValueError, TypeError):
        return False, val, "Invalid immediate"
    IMM_MAX, IMM_MIN = 0b011111111111, -0b100000000000
    if v > IMM_MAX or v < IMM_MIN:
        cp.cprint_warn(f"Warning:{ln}: Immediate {v} overflow (12-bit signed)")
    return True, format(v if v >= 0 else (1 << 12) + v, '012b')[-12:], None

def get_imm_S(val, ln):
    try:
        v = int(val)
    except (ValueError, TypeError):
        return False, val, "Invalid immediate"
    b = format(v if v >= 0 else (1 << 12) + v, '012b')[-12:]
    return True, (b[:7], b[7:]), None

def get_imm_SB(val, ln):
    try:
        v = int(val)
    except (ValueError, TypeError):
        return False, val, "Invalid immediate"
    IMM_MAX, IMM_MIN = 0b0111111111110, -0b1000000000000
    if v > IMM_MAX or v < IMM_MIN:
        cp.cprint_warn(f"Warning:{ln}: Branch offset {v} overflow (13-bit signed)")
    b = format(v if v >= 0 else (1 << 13) + v, '013b')
    # RISC-V SB encoding: imm[12|10:5] | rs2 | rs1 | funct3 | imm[4:1|11] | opcode
    imm_12_10_5 = b[0] + b[2:8]   # bit12 + bit10..5
    imm_4_1_11  = b[8:12] + b[1]  # bit4..1 + bit11
    return True, (imm_12_10_5, imm_4_1_11), None

def get_imm_U(val, ln):
    try:
        v = int(val)
    except (ValueError, TypeError):
        return False, val, "Invalid immediate"
    return True, format(v if v >= 0 else (1 << 20) + v, '020b')[-20:], None

def get_imm_UJ(val, ln):
    try:
        v = int(val)
    except (ValueError, TypeError):
        return False, val, "Invalid immediate"
    IMM_MAX, IMM_MIN = 0b011111111111111111110, -0b100000000000000000000
    if v > IMM_MAX or v < IMM_MIN:
        cp.cprint_warn(f"Warning:{ln}: JAL offset {v} overflow (21-bit signed)")
    b = format(v if v >= 0 else (1 << 21) + v, '021b')
    # RISC-V UJ encoding: imm[20|10:1|11|19:12]
    shf = b[0] + b[10:20] + b[9] + b[1:9]
    assert len(shf) == 20
    return True, shf, None


# =========================================================
# ENCODE_OFFSET  (linker'dan da çağrılır)
# Verilen tokens + (address, target) → imm hesaplayıp tokens'ı günceller
# =========================================================

def encode_offset(ltokens, address, target):
    """
    Bir label referansı için PC-relative offset hesaplar ve
    token sözlüğüne doldurur.  Hem internal (aynı dosya) hem de
    linker tarafından cross-file relocation çözümlemesinde kullanılır.
    """
    offset  = target - address
    lineno  = ltokens.get('lineno', 0)
    opcode  = ltokens['opcode']

    if opcode == mcc.INSTR_JAL:
        _, imm, _ = get_imm_UJ(offset, lineno)
        return {'opcode': opcode, 'rd':  ltokens['rd'],  'imm': imm, 'lineno': lineno}

    elif opcode in mcc.INSTR_TYPE_SB:
        _, imm, _ = get_imm_SB(offset, lineno)
        return {'opcode': opcode, 'rs1': ltokens['rs1'], 'rs2': ltokens['rs2'],
                'imm': imm, 'lineno': lineno}

    elif opcode == mcc.INSTR_JALR:
        _, imm, _ = get_imm_I(offset, lineno)
        return {'opcode': opcode, 'rd':  ltokens['rd'],  'rs1': ltokens['rs1'],
                'imm': imm, 'lineno': lineno}

    return ltokens  # diğer durumlarda dokunma


# =========================================================
# PLACEHOLDER BINARY  (relocation sırasında imm=0 için)
# =========================================================

def _placeholder_tokens(tokens):
    """
    Label referansı içeren bir token sözlüğü için imm=0 placeholder
    üretir.  Binary komut yerleştirilir; linker sonradan patch eder.
    """
    opcode = tokens['opcode']
    if opcode == mcc.INSTR_JAL:
        return {'opcode': opcode, 'rd':  tokens['rd'],
                'imm': '0' * 20,       'lineno': tokens['lineno']}
    elif opcode in mcc.INSTR_TYPE_SB:
        return {'opcode': opcode, 'rs1': tokens['rs1'], 'rs2': tokens['rs2'],
                'imm': ('0' * 7, '0' * 5), 'lineno': tokens['lineno']}
    elif opcode == mcc.INSTR_JALR:
        return {'opcode': opcode, 'rd':  tokens['rd'],  'rs1': tokens['rs1'],
                'imm': '0' * 12,       'lineno': tokens['lineno']}
    return tokens


# =========================================================
# BUILD PARSER
# =========================================================

parser = yacc.yacc()


# =========================================================
# TWO-PASS ALGORİTMASI
# =========================================================

def parse_pass_one(fin, args=None):
    """
    1. Geçiş: Sembol tablosunu oluşturur.
    Hiçbir binary üretilmez; sadece etiket→adres eşlemesi yapılır.
    """
    address      = 0
    symbol_table = {}
    fin.seek(0)
    reset_lineno()

    for line in fin:
        result = parser.parse(line)
        if not result or result.get('tokens') is None:
            continue

        tokens_data = result['tokens']

        # Direktif işleme
        if isinstance(tokens_data, dict) and tokens_data.get('type') == 'directive':
            d = tokens_data['directive']
            v = tokens_data.get('value')
            if d == '.word':
                address += 4
            elif d == '.org' and v is not None:
                address = int(v)
            continue

        if result['type'] == 'label':
            symbol_table[tokens_data['label']] = address

        elif result['type'] == 'instruction':
            if tokens_data is not None:
                address += 4

    return symbol_table


def parse_pass_two(fin, symbol_table, args=None):
    """
    2. Geçiş: Binary komutları üretir.

    KRİTİK DEĞİŞİKLİK (linker projesi):
      - Aynı dosyadaki label'lar hâlâ burada çözülür (pass-one ile bulundu).
      - GLOBAL / EXTERNAL label'lar (başka .o dosyasından gelecek olanlar)
        tanımlı değilse relocation_table'a eklenir, imm=0 placeholder bırakılır.
      - Böylece linker daha sonra bu adresleri patch edebilir.

    Dönüş:
        text_section      : ['01001011...', ...]   32-bit binary string listesi
        data_section      : [{'address': int, 'value': str}, ...]
        relocation_table  : [{'symbol': str, 'address': int, 'type': str,
                               'rd': str?, 'rs1': str?, 'rs2': str?}, ...]
    """
    if args is None:
        args = {}

    fin.seek(0)
    reset_lineno()

    address          = 0
    text_section     = []
    data_section     = []
    relocation_table = []

    for line in fin:
        if not line.strip():
            continue

        result = parser.parse(line)
        if not result or result.get('tokens') is None:
            continue

        tok = result['tokens']

        # --- DİREKTİF ---
        if isinstance(tok, dict) and tok.get('type') == 'directive':
            d = tok['directive']
            v = tok.get('value')
            if d == '.word' and v is not None:
                val_int = int(v) & 0xFFFFFFFF
                val_bin = format(val_int, '032b')
                data_section.append({'address': address, 'value': val_bin})
                text_section.append(val_bin)   # .word hem data hem text'e gider
                address += 4
            elif d == '.org' and v is not None:
                address = int(v)
            continue

        # --- ETİKET TANIMI ---
        if result['type'] == 'label':
            continue   # adres zaten pass-one'da sembol tablosuna yazıldı

        # --- KOMUT ---
        if result['type'] != 'instruction' or tok is None:
            continue

        if 'label' in tok:
            label_name = tok['label']

            if label_name in symbol_table:
                # Aynı dosyada tanımlı → hemen çöz (tek-dosya assembler davranışı)
                resolved = encode_offset(tok, address, symbol_table[label_name])
            else:
                # Başka dosyada tanımlı (external) → RELOCATION KAYDI
                reloc_entry = {
                    'symbol':  label_name,
                    'address': address,
                    'type':    tok['opcode'],
                }
                # Register bilgilerini de kaydet; linker patch ederken lazım
                for field in ('rd', 'rs1', 'rs2'):
                    if field in tok:
                        reloc_entry[field] = tok[field]
                relocation_table.append(reloc_entry)

                # Placeholder binary üret (imm = 0)
                resolved = _placeholder_tokens(tok)

            binary_res = mcg.convert_to_binary(resolved)

        elif 'opcode' in tok:
            binary_res = mcg.convert_to_binary(tok)

        else:
            continue

        if binary_res is not None:
            instr_bits, _ = binary_res
            if args.get('hex'):
                instr_bits = '%08X' % int(instr_bits, 2)
            text_section.append(instr_bits)
            address += 4

    return text_section, data_section, relocation_table


# =========================================================
# ANA GİRİŞ NOKTALARI
# =========================================================

def parse_input(infile, **kwargs):
    """
    Bir .asm dosyasını okur, iki geçiş çalıştırır ve sonuçları döndürür.

    Dönüş:
        {
          'text':        [...],   # binary/hex string listesi
          'data':        [...],   # .word gibi data direktifleri
          'symbols':     {...},   # sembol tablosu  {isim: adres}
          'relocations': [...],   # çözülemeyen label referansları
        }

    Eğer 'outfile' kwarg'ı verilmişse text_section dosyaya da yazılır.
    """
    with open(infile, 'r') as fin:
        symbol_table                          = parse_pass_one(fin, kwargs)
        text_section, data_section, reloc_tbl = parse_pass_two(fin, symbol_table, kwargs)

    # İsteğe bağlı: çıktıyı dosyaya yaz
    outfile = kwargs.get('outfile')
    if outfile:
        with open(outfile, 'w') as fout:
            for line in text_section:
                fout.write(line + '\n')
        print(f"Derleme tamamlandı → {outfile}  ({len(text_section)} komut)")

    # Sembol tablosunu ekrana yaz
    if kwargs.get('echo_symbols') and symbol_table:
        print("\n=== Symbol Table ===")
        print(f"{'Label':<12} {'Adres':<8} {'Hex'}")
        for lbl, addr in symbol_table.items():
            print(f"{lbl:<12} {addr:<8} 0x{addr:04X}")

    if reloc_tbl:
        print(f"\n[!] {len(reloc_tbl)} adet çözülmemiş relocation var "
              f"(linker gerekli): {[r['symbol'] for r in reloc_tbl]}")

    return {
        'text':        text_section,
        'data':        data_section,
        'symbols':     symbol_table,
        'relocations': reloc_tbl,
    }


# =========================================================
# STANDALONE KULLANIM
# =========================================================

def main():
    if len(sys.argv) <= 1:
        sys.exit("Kullanım: python parser.py <dosya.asm>")
    result = parse_input(sys.argv[1], outfile='a.out', echo_symbols=True)
    print(f"\ntext    : {len(result['text'])} komut")
    print(f"data    : {len(result['data'])} kayıt")
    print(f"relocs  : {len(result['relocations'])} adet")

if __name__ == '__main__':
    main()