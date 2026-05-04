# rvi.py
# Kullanıcı Arayüzü
# Mod 1 — Sadece derle  : python rvi.py program.asm -x -es
# Mod 2 — Derle + Linkle: python rvi.py main1.asm main2.asm --link -o output.hex -x

from lib.parser import parse_input, reset_lineno, parser as ply_parser
from lib.object_writer import write_object_file
import argparse
import os

VERSION = 0.2


def get_arguments():
    descr = f"\n    RVI v{VERSION}\n    - RV32I Assembler + Linker\n    "
    ap = argparse.ArgumentParser(description=descr)

    ap.add_argument("INFILES", nargs='+',
                    help="Bir veya daha fazla .asm dosyası.")
    ap.add_argument('-o', "--outfile", default='output.hex',
                    help="Çıktı dosyası adı (default: output.hex).")
    ap.add_argument('--link', action="store_true",
                    help="Derleme sonrası tüm .o dosyalarını linkle.")
    ap.add_argument('-e',  "--echo",         action="store_true",
                    help="Üretilen kodu terminale yaz.")
    ap.add_argument('-nc', "--no-color",     action="store_true",
                    help="Renksiz çıktı.")
    ap.add_argument('-n32',"--no-32",        action="store_true",
                    help="32-bit uyarılarını kapat.")
    ap.add_argument('-x',  "--hex",          action="store_true",
                    help="HEX formatında çıktı.")
    ap.add_argument('-t',  "--tokenize",     action="store_true",
                    help="Token debug çıktısı.")
    ap.add_argument("-es", "--echo-symbols", action="store_true",
                    help="Sembol tablosunu göster.")

    return ap.parse_args()


# =========================================================
# MOD 1: Tek dosya derle
# =========================================================

def assemble_file(infile, args):
    """
    Bir .asm dosyasını derler, .o dosyasını yazar.
    Dönüş: oluşturulan .o dosyasının adı
    """
    print(f"\n{'='*50}")
    print(f"Derleniyor: {infile}")
    print(f"{'='*50}")

    result = parse_input(infile, **{
        'outfile':      args.outfile if not args.link else None,
        'hex':          args.hex,
        'echo_symbols': args.echo_symbols,
    })

    text    = result['text']
    data    = result['data']
    symbols = result['symbols']
    relocs  = result['relocations']

    # .o dosyasını yaz
    obj_filename = write_object_file(infile, text, data, symbols, relocs)

    # Echo
    if args.echo:
        print("\n=== Üretilen Kod ===")
        for i, instr in enumerate(text):
            print(f"  [0x{i*4:04X}]  {instr}")

    # Tokenizer debug
    if args.tokenize:
        print("\n=== Tokenized Instructions ===")
        with open(infile, 'r') as f:
            reset_lineno()
            for line in f:
                if not line.strip():
                    continue
                res = ply_parser.parse(line)
                if res:
                    print(f"  {res}")

    # Sembol tablosu
    if args.echo_symbols and symbols:
        print(f"\n=== Sembol Tablosu — {infile} ===")
        print(f"  {'Label':<12} {'Adres':<8} Hex")
        for label, addr in symbols.items():
            print(f"  {label:<12} {addr:<8} 0x{addr:04X}")

    # Relocation uyarısı
    if relocs:
        print(f"\n  [!] {len(relocs)} external sembol → linker gerekli")
        for r in relocs:
            print(f"      0x{r['address']:04X}  {r['type']:<6} → {r['symbol']}")

    return obj_filename


# =========================================================
# MOD 2: Derle + Linkle
# =========================================================

def assemble_and_link(infiles, args):
    """
    Tüm .asm dosyalarını sırayla derler, ardından linker ile birleştirir.
    """
    from linker import link

    # 1. Her dosyayı derle
    obj_files = []
    for infile in infiles:
        if not os.path.isfile(infile):
            print(f"[HATA] Dosya bulunamadı: '{infile}'")
            continue
        obj_file = assemble_file(infile, args)
        obj_files.append(obj_file)

    if not obj_files:
        print("[HATA] Hiç .o dosyası üretilemedi.")
        return

    # 2. Linkle
    print(f"\n{'='*50}")
    print(f"Linkleniyor: {' + '.join(obj_files)}")
    print(f"{'='*50}")

    merged_symbols = link(
        object_files=obj_files,
        output_path=args.outfile,
        hex_mode=args.hex,
    )

    # 3. Özet
    print(f"\n{'='*50}")
    print(f"Tamamlandı!")
    print(f"  Girdi    : {', '.join(infiles)}")
    print(f"  Çıktı    : {args.outfile}")
    print(f"  Semboller: {merged_symbols}")
    print(f"{'='*50}")


# =========================================================
# ANA FONKSİYON
# =========================================================

def main():
    args = get_arguments()

    if args.link:
        # Mod 2: Derle + Linkle
        if len(args.INFILES) < 2:
            print("[UYARI] --link modu için en az 2 .asm dosyası önerilir.")
            print("         Tek dosyayla devam ediliyor...")
        assemble_and_link(args.INFILES, args)

    else:
        # Mod 1: Sadece derle (her dosya için ayrı ayrı)
        for infile in args.INFILES:
            if not os.path.isfile(infile):
                print(f"[HATA] Dosya bulunamadı: '{infile}'")
                continue
            assemble_file(infile, args)


if __name__ == '__main__':
    main()