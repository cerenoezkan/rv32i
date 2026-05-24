#!/usr/bin/env python3
# host_uploader.py

import argparse
import json
import struct
import sys
import time
import zlib

SYNC_PKT     = bytes([0xAA, 0x55])
SYNC_END     = bytes([0xAA, 0x56])
RESP_ACK     = 0x06
RESP_NAK     = 0x15
MAX_PKT_DATA = 256
DEFAULT_BAUD = 115200
ACK_TIMEOUT  = 3.0
MAX_RETRIES  = 5

def crc32_ieee(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF

def parse_verilog_hex(path: str) -> dict:
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
                mem[base + i] = (word >> (8 * i)) & 0xFF
            base += 4
    return mem

def parse_object_file(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        obj = json.load(f)
    mem = {}
    text_base = obj['header'].get('entry_point', 0)
    for i, s in enumerate(obj.get('text', [])):
        s = s.replace('_', '')
        if len(s) == 32 and set(s) <= {'0', '1'}:
            word = int(s, 2)
        else:
            word = int(s, 16)
        addr = text_base + i * 4
        for b in range(4):
            mem[addr + b] = (word >> (8 * b)) & 0xFF
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
    if path.endswith('.o'):
        print(f"[+] Nesne dosyası (.o) okunuyor: {path}")
        return parse_object_file(path)
    else:
        print(f"[+] Verilog hex (.hex) okunuyor: {path}")
        return parse_verilog_hex(path)

def coalesce_regions(mem: dict):
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

def build_packet(addr: int, payload: bytes) -> bytes:
    addr_bytes = struct.pack('<I', addr & 0xFFFFFFFF)
    size_bytes = struct.pack('<H', len(payload) & 0xFFFF)
    body       = addr_bytes + size_bytes + payload
    crc_bytes  = struct.pack('<I', crc32_ieee(body))
    return SYNC_PKT + body + crc_bytes

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
            print(f"    [!] Paket #{pkt_num}: CRC NAK — yeniden gönderiliyor (deneme {attempt}/{MAX_RETRIES})")
            continue
        print(f"    [!] Paket #{pkt_num}: beklenmeyen yanıt 0x{resp:02X}")
    raise RuntimeError(f"Paket #{pkt_num} gönderilemedi (maksimum deneme aşıldı)")

def upload(ser, file_path: str, dry_run: bool = False) -> None:
    mem     = load_file(file_path)
    regions = coalesce_regions(mem)
    total_bytes = sum(len(d) for _, d in regions)
    print(f"[+] {len(regions)} bellek bölgesi, toplam {total_bytes} bayt")
    pkt_count = 0
    for region_addr, region_data in regions:
        offset = 0
        while offset < len(region_data):
            chunk    = region_data[offset : offset + MAX_PKT_DATA]
            pkt_addr = region_addr + offset
            pkt      = build_packet(pkt_addr, chunk)
            pkt_count += 1
            print(f"    Paket #{pkt_count:3d}: addr=0x{pkt_addr:08X}  size={len(chunk):3d}  CRC=0x{crc32_ieee(pkt[2:-4]):08X}")
            if not dry_run:
                send_packet(ser, pkt, pkt_count)
            offset += len(chunk)
    if not dry_run:
        ser.write(SYNC_END)
        ser.flush()
        print(f"[+] Oturum sonu gönderildi -> FPGA CPU'yu baslatıyor...")
    else:
        print(f"[DRY-RUN] Oturum sonu: {SYNC_END.hex()}")
    print(f"[+] Tamamlandı — {pkt_count} paket gönderildi.")

def interactive_mode(ser):
    print("\n[+] Interaktif mod — UART girisi:")
    print("    '1' gonder -> tum LED yanar")
    print("    '0' gonder -> aritmetik sonuc")
    print("    'q' -> cik\n")
    while True:
        cmd = input("Komut (0/1/q): ").strip()
        if cmd == 'q':
            break
        if cmd in ('0', '1'):
            ser.write(cmd.encode())
            print(f"    Gonderildi: '{cmd}'")
        else:
            print("    Gecersiz komut")

def main():
    ap = argparse.ArgumentParser(description="RVI UART FPGA Yukleyici — Tang Nano 9K")
    ap.add_argument("file", help="Yuklenecek dosya (.hex veya .o)")
    ap.add_argument("-p", "--port", default=None, help="Seri port (orn: COM8)")
    ap.add_argument("-b", "--baud", type=int, default=DEFAULT_BAUD, help=f"Baud hızı (varsayılan: {DEFAULT_BAUD})")
    ap.add_argument("--dry-run", action="store_true", help="Port acmadan paket listesini goster")
    args = ap.parse_args()

    if args.dry_run:
        print("[DRY-RUN] Port acılmıyor.")
        upload(None, args.file, dry_run=True)
        return

    if not args.port:
        ap.error("UART yukleme icin -p/--port gerekli (--dry-run haric)")

    try:
        import serial
    except ImportError:
        print("[!] pyserial gerekli: pip install pyserial")
        sys.exit(1)

    print(f"[+] Port acılıyor: {args.port} @ {args.baud} baud")
    try:
        with serial.Serial(args.port, args.baud, timeout=0.1) as ser:
            ser.dtr = True
            time.sleep(0.1)
            ser.dtr = False
            time.sleep(0.5)
            ser.reset_input_buffer()
            upload(ser, args.file)
            if 'test1' in args.file:
                interactive_mode(ser)
    except serial.SerialException as e:
        print(f"[!] Port hatası: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()