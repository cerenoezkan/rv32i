#!/usr/bin/env python3
# host_uploader.py
# ---------------------------------------------------------------------------
# RVI linker çıktısını (.hex veya .o) UART üzerinden Tang Nano 9K'ya gönderir.
#
# Paket formatı (loader_fsm.v ile birebir uyumlu):
#   [0xAA][0x55]  →  paket başı
#   [ADDR: 4 bayt LE]  →  BRAM hedef adresi
#   [SIZE: 2 bayt LE]  →  data uzunluğu (max 256)
#   [DATA: SIZE bayt]  →  ham makine kodu
#   [CRC32: 4 bayt LE] →  IEEE 802.3, hesap: CRC32(ADDR||SIZE||DATA)
#   [0xAA][0x56]       →  oturum sonu
#
# Yanıtlar: 0x06 = ACK (tamam), 0x15 = NAK (CRC hatası → yeniden gönder)
#
# Kullanım:
#   python host_uploader.py test1.hex -p /dev/ttyUSB0
#   python host_uploader.py test1.o   -p COM3
#   python host_uploader.py test1.hex --dry-run   (port açmadan test)
# ---------------------------------------------------------------------------

import argparse
import json
import struct
import sys
import time
import zlib


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
SYNC_PKT     = bytes([0xAA, 0x55])
SYNC_END     = bytes([0xAA, 0x56])
RESP_ACK     = 0x06
RESP_NAK     = 0x15
MAX_PKT_DATA = 256          # paket başına maksimum veri baytı
DEFAULT_BAUD = 115200
ACK_TIMEOUT  = 3.0          # saniye
MAX_RETRIES  = 5


# ---------------------------------------------------------------------------
# CRC32 — Python zlib ile (IEEE 802.3, loader_fsm/crc32_byte.v ile uyumlu)
# ---------------------------------------------------------------------------
def crc32_ieee(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Dosya okuyucular
# ---------------------------------------------------------------------------

def parse_verilog_hex(path: str) -> dict:
    """
    @adres satırlı Verilog hex formatı → {byte_addr: byte_value}
    Linker'ın ürettiği .hex dosyasını okur.
    """
    mem = {}
    base = 0
    with open(path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.split('//')[0].strip()
            if not line:
                continue
            if line.startswith('@'):
                base = int(line[1:], 16)
                continue
            word = int(line, 16)
            for i in range(4):
                mem[base + i] = (word >> (8 * i)) & 0xFF  # little-endian
            base += 4
    return mem


def parse_object_file(path: str) -> dict:
    """
    RVI .o (JSON) nesne dosyası → {byte_addr: byte_value}
    object_writer.py'nin ürettiği formatı okur.
    """
    with open(path, 'r', encoding='utf-8') as f:
        obj = json.load(f)

    mem = {}

    # Text section: entry_point adresinden başlar (genellikle 0x0)
    text_base = obj['header'].get('entry_point', 0)
    for i, s in enumerate(obj.get('text', [])):
        # Binary string ("01001011...") veya hex string ("0000_0013") olabilir
        s = s.replace('_', '')
        if len(s) == 32 and set(s) <= {'0', '1'}:
            word = int(s, 2)
        else:
            word = int(s, 16)
        addr = text_base + i * 4
        for b in range(4):
            mem[addr + b] = (word >> (8 * b)) & 0xFF

    # Data section: link_fpga.ld'ye göre 0x400'dan başlar
    data_base = 0x00000400
    for i, s in enumerate(obj.get('data', [])):
        s = s.replace('_', '')
        if len(s) == 32 and set(s) <= {'0', '1'}:
            word = int(s, 2)
        else:
            word = int(s, 16)
        addr = data_base + i * 4
        for b in range(4):
            mem[addr + b] = (word >> (8 * b)) & 0xFF

    return mem


def load_file(path: str) -> dict:
    """Dosya uzantısına göre otomatik format seç."""
    if path.endswith('.o'):
        print(f"[+] Nesne dosyası (.o) okunuyor: {path}")
        return parse_object_file(path)
    else:
        print(f"[+] Verilog hex (.hex) okunuyor: {path}")
        return parse_verilog_hex(path)


# ---------------------------------------------------------------------------
# Adres bölgelerini birleştir
# ---------------------------------------------------------------------------

def coalesce_regions(mem: dict):
    """
    Ardışık adresleri tek bölgeye birleştir.
    Dönüş: [(start_addr, bytes_data), ...]
    """
    if not mem:
        return []
    addrs = sorted(mem.keys())
    regions = []
    start = addrs[0]
    prev  = start
    buf   = [mem[start]]

    for a in addrs[1:]:
        if a == prev + 1:
            buf.append(mem[a])
        else:
            regions.append((start, bytes(buf)))
            start = a
            buf   = [mem[a]]
        prev = a
    regions.append((start, bytes(buf)))
    return regions


# ---------------------------------------------------------------------------
# Paket oluştur
# ---------------------------------------------------------------------------

def build_packet(addr: int, payload: bytes) -> bytes:
    """
    [0xAA][0x55][ADDR:4 LE][SIZE:2 LE][DATA][CRC32:4 LE]
    CRC hesabı: CRC32(ADDR_bytes || SIZE_bytes || DATA_bytes)
    """
    addr_bytes = struct.pack('<I', addr & 0xFFFFFFFF)
    size_bytes = struct.pack('<H', len(payload) & 0xFFFF)
    body       = addr_bytes + size_bytes + payload
    crc_bytes  = struct.pack('<I', crc32_ieee(body))
    return SYNC_PKT + body + crc_bytes


# ---------------------------------------------------------------------------
# UART yardımcıları
# ---------------------------------------------------------------------------

def wait_response(ser, timeout: float) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ser.in_waiting:
            return ser.read(1)[0]
        time.sleep(0.005)
    raise TimeoutError("FPGA yanıt zaman aşımı (ACK/NAK bekleniyor)")


def send_packet(ser, pkt: bytes, pkt_num: int) -> None:
    for attempt in range(1, MAX_RETRIES + 1):
        ser.write(pkt)
        ser.flush()
        try:
            resp = wait_response(ser, ACK_TIMEOUT)
        except TimeoutError:
            print(f"    [!] Paket #{pkt_num}: zaman aşımı (deneme {attempt}/{MAX_RETRIES})")
            continue

        if resp == RESP_ACK:
            return
        if resp == RESP_NAK:
            print(f"    [!] Paket #{pkt_num}: CRC NAK — yeniden gönderiliyor "
                  f"(deneme {attempt}/{MAX_RETRIES})")
            continue
        print(f"    [!] Paket #{pkt_num}: beklenmeyen yanıt 0x{resp:02X}")

    raise RuntimeError(f"Paket #{pkt_num} gönderilemedi (maksimum deneme aşıldı)")


# ---------------------------------------------------------------------------
# Ana yükleme fonksiyonu
# ---------------------------------------------------------------------------

def upload(ser, file_path: str, dry_run: bool = False) -> None:
    mem     = load_file(file_path)
    regions = coalesce_regions(mem)

    total_bytes = sum(len(d) for _, d in regions)
    print(f"[+] {len(regions)} bellek bölgesi, toplam {total_bytes} bayt")

    pkt_count = 0
    for region_addr, region_data in regions:
        offset = 0
        while offset < len(region_data):
            chunk     = region_data[offset : offset + MAX_PKT_DATA]
            pkt_addr  = region_addr + offset
            pkt       = build_packet(pkt_addr, chunk)
            pkt_count += 1

            print(f"    Paket #{pkt_count:3d}: "
                  f"addr=0x{pkt_addr:08X}  size={len(chunk):3d}  "
                  f"CRC=0x{crc32_ieee(pkt[2:-4]):08X}")

            if not dry_run:
                send_packet(ser, pkt, pkt_count)

            offset += len(chunk)

    # Oturum sonu
    if not dry_run:
        ser.write(SYNC_END)
        ser.flush()
        print(f"[+] Oturum sonu gönderildi → FPGA CPU'yu başlatıyor...")
    else:
        print(f"[DRY-RUN] Oturum sonu: {SYNC_END.hex()}")

    print(f"[+] Tamamlandı — {pkt_count} paket gönderildi.")


# ---------------------------------------------------------------------------
# Komut satırı
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="RVI UART FPGA Yükleyici — Tang Nano 9K",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python host_uploader.py test1.hex -p /dev/ttyUSB0
  python host_uploader.py test1.o   -p COM3 -b 115200
  python host_uploader.py test1.hex --dry-run
"""
    )
    ap.add_argument("file",
                    help="Yüklenecek dosya (.hex Verilog formatı veya .o JSON)")
    ap.add_argument("-p", "--port",
                    default=None,
                    help="Seri port (ör: /dev/ttyUSB0, COM3)")
    ap.add_argument("-b", "--baud",
                    type=int, default=DEFAULT_BAUD,
                    help=f"Baud hızı (varsayılan: {DEFAULT_BAUD})")
    ap.add_argument("--dry-run",
                    action="store_true",
                    help="Port açmadan paket listesini göster")
    args = ap.parse_args()

    if args.dry_run:
        print("[DRY-RUN] Port açılmıyor.")
        upload(None, args.file, dry_run=True)
        return

    if not args.port:
        ap.error("UART yükleme için -p/--port gerekli (--dry-run hariç)")

    try:
        import serial
    except ImportError:
        print("[!] pyserial gerekli: pip install pyserial")
        sys.exit(1)

    print(f"[+] Port açılıyor: {args.port} @ {args.baud} baud")
    try:
        with serial.Serial(args.port, args.baud, timeout=0.1) as ser:
            time.sleep(0.2)          # port stabilizasyon süresi
            ser.reset_input_buffer()
            upload(ser, args.file)
    except serial.SerialException as e:
        print(f"[!] Port hatası: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()