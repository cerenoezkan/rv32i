# parser.py - lib/ klasorune koy
# Two-pass, .text/.data section ayristirmali, linker uyumlu
# exports (.globl) ve imports (.extern) destegi eklendi

import ply.yacc as yacc
import sys

from lib.tokenizer import tokens, reset_lineno
from lib.machinecodegen import mcg
from lib.cprint import cprint as cp
from lib.machinecodeconst import MachineCodeConst

mcc = MachineCodeConst()

def p_program_statement(p):
    'program : statement'
    p[0] = {'type': 'instruction', 'tokens': p[1]}

def p_program_label(p):
    'program : LABEL COLUMN NEWLINE'
    p[0] = {'type': 'label', 'tokens': {'label': p[1], 'lineno': p.lineno(1)}}

def p_program_empty(p):
    '''program : NEWLINE
               | '''
    p[0] = None

def p_statement_directive(p):
    'statement : DIRECTIVE IMMEDIATE NEWLINE'
    p[0] = {'type': 'directive', 'directive': p[1], 'value': p[2], 'lineno': p.lineno(1)}

def p_statement_directive_single(p):
    'statement : DIRECTIVE NEWLINE'
    p[0] = {'type': 'directive', 'directive': p[1], 'value': None, 'lineno': p.lineno(1)}

# .globl/.global/.extern direktifleri LABEL argümanı alır
def p_statement_directive_label(p):
    'statement : DIRECTIVE LABEL NEWLINE'
    p[0] = {'type': 'directive', 'directive': p[1], 'value': p[2], 'lineno': p.lineno(1)}

def p_statement_R(p):
    'statement : OPCODE register COMMA register COMMA register NEWLINE'
    if p[1] not in mcc.INSTR_TYPE_R:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Invalid R-type opcode '{p[1]}'")
        raise SyntaxError
    p[0] = {'opcode': p[1], 'rd': p[2], 'rs1': p[4], 'rs2': p[6], 'lineno': p.lineno(1)}

def p_statement_I_S_SB(p):
    'statement : OPCODE register COMMA register COMMA IMMEDIATE NEWLINE'
    opcode = p[1]
    if opcode in mcc.INSTR_TYPE_I:
        _, imm, _ = get_imm_I(p[6], p.lineno(6))
        p[0] = {'opcode': opcode, 'rd': p[2], 'rs1': p[4], 'imm': imm, 'lineno': p.lineno(1)}
    elif opcode in mcc.INSTR_TYPE_S:
        _, imm, _ = get_imm_S(p[6], p.lineno(6))
        p[0] = {'opcode': opcode, 'rs1': p[2], 'rs2': p[4], 'imm': imm, 'lineno': p.lineno(1)}
    elif opcode in mcc.INSTR_TYPE_SB:
        _, imm, _ = get_imm_SB(p[6], p.lineno(6))
        p[0] = {'opcode': opcode, 'rs1': p[2], 'rs2': p[4], 'imm': imm, 'lineno': p.lineno(1)}
    else:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Invalid opcode '{opcode}' for this format")
        raise SyntaxError

def p_statement_load_store_offset(p):
    'statement : OPCODE register COMMA IMMEDIATE LPAREN register RPAREN NEWLINE'
    opcode = p[1]
    if opcode in mcc.INSTR_TYPE_I:
        _, imm, _ = get_imm_I(p[4], p.lineno(4))
        p[0] = {'opcode': opcode, 'rd': p[2], 'rs1': p[6], 'imm': imm, 'lineno': p.lineno(1)}
    elif opcode in mcc.INSTR_TYPE_S:
        _, imm, _ = get_imm_S(p[4], p.lineno(4))
        p[0] = {'opcode': opcode, 'rs1': p[6], 'rs2': p[2], 'imm': imm, 'lineno': p.lineno(1)}
    else:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Unsupported load/store opcode '{opcode}'")
        raise SyntaxError

def p_statement_U_UJ(p):
    'statement : OPCODE register COMMA IMMEDIATE NEWLINE'
    opcode = p[1]
    if opcode in mcc.INSTR_TYPE_U:
        _, imm, _ = get_imm_U(p[4], p.lineno(4))
        p[0] = {'opcode': opcode, 'rd': p[2], 'imm': imm, 'lineno': p.lineno(1)}
    elif opcode in mcc.INSTR_TYPE_UJ:
        _, imm, _ = get_imm_UJ(p[4], p.lineno(4))
        p[0] = {'opcode': opcode, 'rd': p[2], 'imm': imm, 'lineno': p.lineno(1)}
    else:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Invalid opcode '{opcode}' for U/UJ format")
        raise SyntaxError

def p_statement_UJ_LABEL(p):
    'statement : OPCODE register COMMA LABEL NEWLINE'
    if p[1] not in mcc.INSTR_TYPE_UJ and p[1] != mcc.INSTR_JALR:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Opcode '{p[1]}' cannot use a label target")
        raise SyntaxError
    p[0] = {'opcode': p[1], 'rd': p[2], 'label': p[4], 'lineno': p.lineno(1)}

def p_statement_SB_LABEL(p):
    'statement : OPCODE register COMMA register COMMA LABEL NEWLINE'
    if p[1] not in mcc.INSTR_TYPE_SB and p[1] != mcc.INSTR_JALR:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Opcode '{p[1]}' cannot use a label target")
        raise SyntaxError
    if p[1] in mcc.INSTR_TYPE_SB:
        p[0] = {'opcode': p[1], 'rs1': p[2], 'rs2': p[4], 'label': p[6], 'lineno': p.lineno(1)}
    else:
        p[0] = {'opcode': p[1], 'rd': p[2], 'rs1': p[4], 'label': p[6], 'lineno': p.lineno(1)}

def p_register(p):
    'register : REGISTER'
    num = int(p[1][1:])
    if num < 0 or num > 31:
        cp.cprint_fail(f"Error:{p.lineno(1)}: Invalid register '{p[1]}' (x0-x31 expected)")
        raise SyntaxError
    p[0] = p[1]

def p_statement_none(p):
    'statement : NEWLINE'
    p[0] = None

def p_error(p):
    if p:
        cp.cprint_fail(f"Syntax Error: unexpected token '{p.value}' at line {p.lineno}")
    else:
        cp.cprint_fail("Syntax Error at EOF")

# --- IMM FONKSIYONLARI ---

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
    IMM_MAX, IMM_MIN = 0b011111111111, -0b100000000000
    if v > IMM_MAX or v < IMM_MIN:
        cp.cprint_warn(f"Warning:{ln}: Store immediate {v} overflow (12-bit signed)")
    b = format(v if v >= 0 else (1 << 12) + v, '012b')[-12:]
    return True, (b[0:7], b[7:12]), None

def get_imm_SB(val, ln):
    try:
        v = int(val)
    except (ValueError, TypeError):
        return False, val, "Invalid immediate"
    IMM_MAX, IMM_MIN = 0b0111111111110, -0b1000000000000
    if v > IMM_MAX or v < IMM_MIN:
        cp.cprint_warn(f"Warning:{ln}: Branch offset {v} overflow (13-bit signed)")
    b = format(v if v >= 0 else (1 << 13) + v, '013b')
    imm_12_10_5 = b[0] + b[2:8]
    imm_4_1_11  = b[8:12] + b[1]
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
    shf = b[0] + b[10:20] + b[9] + b[1:9]
    assert len(shf) == 20
    return True, shf, None

def encode_offset(ltokens, address, target):
    offset = target - address
    lineno = ltokens.get('lineno', 0)
    opcode = ltokens['opcode']
    if opcode == mcc.INSTR_JAL:
        _, imm, _ = get_imm_UJ(offset, lineno)
        return {'opcode': opcode, 'rd': ltokens['rd'], 'imm': imm, 'lineno': lineno}
    elif opcode in mcc.INSTR_TYPE_SB:
        _, imm, _ = get_imm_SB(offset, lineno)
        return {'opcode': opcode, 'rs1': ltokens['rs1'], 'rs2': ltokens['rs2'],
                'imm': imm, 'lineno': lineno}
    elif opcode == mcc.INSTR_JALR:
        _, imm, _ = get_imm_I(offset, lineno)
        return {'opcode': opcode, 'rd': ltokens['rd'],
                'rs1': ltokens.get('rs1', 'x0'), 'imm': imm, 'lineno': lineno}
    return ltokens

def _placeholder_tokens(tokens):
    opcode = tokens['opcode']
    if opcode == mcc.INSTR_JAL:
        return {'opcode': opcode, 'rd': tokens['rd'], 'imm': '0' * 20, 'lineno': tokens['lineno']}
    elif opcode in mcc.INSTR_TYPE_SB:
        return {'opcode': opcode, 'rs1': tokens['rs1'], 'rs2': tokens['rs2'],
                'imm': ('0' * 7, '0' * 5), 'lineno': tokens['lineno']}
    elif opcode == mcc.INSTR_JALR:
        return {'opcode': opcode, 'rd': tokens['rd'], 'rs1': tokens.get('rs1', 'x0'),
                'imm': '0' * 12, 'lineno': tokens['lineno']}
    return tokens

# --- PARSER ---
parser = yacc.yacc()

# =========================================================
# DIREKTİF İŞLEYİCİ - exports/imports toplar
# =========================================================

def _handle_directive(tok, current_section, text_address, data_address,
                      export_set, import_set):
    """
    Direktifi işler, section/adres/export/import listelerini günceller.
    Dönüş: (current_section, text_address, data_address)
    """
    d = tok['directive']
    v = tok.get('value')

    if d == '.text':
        current_section = 'text'

    elif d == '.data':
        current_section = 'data'

    elif d in ('.globl', '.global'):
        # Bu sembol başka dosyalara görünür olacak
        if v:
            export_set.add(v)
            print(f"    [EXPORT] {v}")

    elif d in ('.extern', '.external'):
        # Bu sembol başka bir dosyadan gelecek
        if v:
            import_set.add(v)
            print(f"    [IMPORT] {v}")

    elif d == '.bss':
        pass  # BSS section şimdilik desteklenmiyor

    elif d == '.word':
        if current_section == 'data':
            data_address += 4
        else:
            text_address += 4

    elif d == '.org' and v is not None:
        if current_section == 'text':
            text_address = int(v)
        else:
            data_address = int(v)

    return current_section, text_address, data_address


# =========================================================
# TWO-PASS
# =========================================================

def parse_pass_one(fin, args=None):
    """
    İlk geçiş: sembol adreslerini toplar.
    export_set ve import_set de doldurulur (pass two'ya aktarılır).
    """
    text_address    = 0
    data_address    = 0
    current_section = 'text'
    symbol_table    = {}
    export_set      = set()
    import_set      = set()

    fin.seek(0)
    reset_lineno()

    # Son satırda \n yoksa parser son komutu kaçırır — garantile
    lines = fin.readlines()
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'

    for line in lines:
        result = parser.parse(line)
        if not result or result.get('tokens') is None:
            continue
        tokens_data = result['tokens']

        if isinstance(tokens_data, dict) and tokens_data.get('type') == 'directive':
            current_section, text_address, data_address = _handle_directive(
                tokens_data, current_section, text_address, data_address,
                export_set, import_set
            )
            # .word için adres sayacı zaten _handle_directive içinde artırıldı
            continue

        if result['type'] == 'label':
            if current_section == 'text':
                symbol_table[tokens_data['label']] = text_address
            else:
                # Data section sembolu: text_size + data_offset olarak sakla
                # (linker'da ayrıştırılır)
                symbol_table[tokens_data['label']] = data_address
        elif result['type'] == 'instruction':
            if tokens_data is not None and current_section == 'text':
                text_address += 4

    return symbol_table, export_set, import_set


def parse_pass_two(fin, symbol_table, export_set=None, import_set=None, args=None):
    """
    İkinci geçiş: makine kodu üretir, relocation tablosu oluşturur.
    """
    if args is None:
        args = {}
    if export_set is None:
        export_set = set()
    if import_set is None:
        import_set = set()

    fin.seek(0)
    reset_lineno()

    current_section  = 'text'
    text_address     = 0
    data_address     = 0
    text_section     = []
    data_section     = []
    relocation_table = []

    # Son satırda \n yoksa parser son komutu kaçırır — garantile
    lines = fin.readlines()
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'

    for line in lines:
        if not line.strip():
            continue
        result = parser.parse(line)
        if not result or result.get('tokens') is None:
            continue
        tok = result['tokens']

        if isinstance(tok, dict) and tok.get('type') == 'directive':
            d = tok['directive']
            v = tok.get('value')

            if d == '.text':
                current_section = 'text'
            elif d == '.data':
                current_section = 'data'
            elif d in ('.globl', '.global', '.extern', '.external', '.bss'):
                pass  # pass one'da işlendi
            elif d == '.word' and v is not None:
                val_int = int(v) & 0xFFFFFFFF
                val_bin = format(val_int, '032b')
                if current_section == 'data':
                    data_section.append(val_bin)
                    data_address += 4
                else:
                    text_section.append(val_bin)
                    text_address += 4
            elif d == '.org' and v is not None:
                if current_section == 'text':
                    text_address = int(v)
                else:
                    data_address = int(v)
            continue

        if result['type'] == 'label':
            continue
        if result['type'] != 'instruction' or tok is None:
            continue
        if current_section != 'text':
            cp.cprint_warn("Uyari: .data section icinde komut bulundu, atlaniyor.")
            continue

        current_address = text_address

        if 'label' in tok:
            label_name = tok['label']
            if label_name in symbol_table:
                resolved   = encode_offset(tok, current_address, symbol_table[label_name])
            else:
                # Bilinmeyen sembol → relocation kaydı oluştur
                # .extern ile import edilmiş mi kontrol et (bilgi amaçlı)
                is_extern = label_name in import_set
                reloc_entry = {
                    'symbol':   label_name,
                    'address':  current_address,
                    'type':     tok['opcode'],
                    'extern':   is_extern,   # ← yeni alan: linker için ipucu
                }
                for field in ('rd', 'rs1', 'rs2'):
                    if field in tok:
                        reloc_entry[field] = tok[field]
                relocation_table.append(reloc_entry)
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
            text_address += 4

    return text_section, data_section, relocation_table


def parse_input(infile, **kwargs):
    with open(infile, 'r') as fin:
        symbol_table, export_set, import_set = parse_pass_one(fin, kwargs)
        text_section, data_section, reloc_tbl = parse_pass_two(
            fin, symbol_table, export_set, import_set, kwargs
        )

    outfile = kwargs.get('outfile')
    if outfile:
        with open(outfile, 'w') as fout:
            for line in text_section:
                fout.write(line + '\n')
        print(f"Derleme tamamlandi -> {outfile}  ({len(text_section)} komut)")

    # --- OTOMATİK .o DOSYASI ÜRETİMİ ---
    # Her derleme sonunda .o dosyası otomatik oluşturulur.
    # rvi.py üzerinden çağrılsa da, doğrudan parser çağrılsa da çalışır.
    from lib.object_writer import write_object_file
    write_object_file(
        infile,
        text_section,
        data_section,
        symbol_table,
        reloc_tbl,
        exports=list(export_set),
        imports=list(import_set),
    )

    if kwargs.get('echo_symbols') and symbol_table:
        print("\n=== Symbol Table ===")
        print(f"{'Label':<16} {'Adres':<8} {'Hex'}")
        print("-" * 35)
        for lbl, addr in symbol_table.items():
            print(f"{lbl:<16} {addr:<8} 0x{addr:04X}")

    if export_set:
        print(f"\n=== Exports (.globl) ===")
        for sym in sorted(export_set):
            print(f"  {sym}")

    if import_set:
        print(f"\n=== Imports (.extern) ===")
        for sym in sorted(import_set):
            print(f"  {sym}")

    if kwargs.get('echo_sections'):
        print(f"\n=== Sections ===")
        print(f"  .text : {len(text_section)} komut")
        print(f"  .data : {len(data_section)} kelime")

    if reloc_tbl:
        print(f"\n[!] {len(reloc_tbl)} adet cozulmemis relocation var "
              f"(linker gerekli): {[r['symbol'] for r in reloc_tbl]}")

    return {
        'text':        text_section,
        'data':        data_section,
        'symbols':     symbol_table,
        'exports':     list(export_set),
        'imports':     list(import_set),
        'relocations': reloc_tbl,
    }


def main():
    if len(sys.argv) <= 1:
        sys.exit("Kullanim: python -m lib.parser <dosya.asm>")
    infile = sys.argv[1]
    print(f"Derleniyor: {infile}")
    result = parse_input(infile, outfile='a.out', echo_symbols=True, echo_sections=True)
    print(f"\ntext   : {len(result['text'])} komut")
    print(f"data   : {len(result['data'])} kayit")
    print(f"relocs : {len(result['relocations'])} adet")
    print(f"exports: {result['exports']}")
    print(f"imports: {result['imports']}")

if __name__ == '__main__':
    main()