#!/usr/bin/env python3
# host_uploader.py
# ---------------------------------------------------------------------------
# RVI linker çıktısını (.hex) UART üzerinden FPGA loader'a gönderir.
#
# Paket formatı:
#   [0xAA][0x55] [ADDR:4 LE] [SIZE:2 LE] [DATA...] [CRC32:4 LE]
# Oturum sonu: [0xAA][0x56]
#
# Yanıtlar: 0x06 ACK, 0x15 NAK (CRC hatası → yeniden gönder)
#
# Kullanım:
#   python host_uploader.py output.hex -p COM3
#   python host_uploader.py output.hex -p /dev/ttyUSB0 -b 115200
# ---------------------------------------------------------------------------

import argparse
import binascii
import struct
import sys
import time
import zlib

def _import_serial():
    try:
        import serial
        return serial
    except ImportError:
        print("[!] pyserial gerekli: pip install pyserial")
        sys.exit(1)

SYNC_PKT  = bytes([0xAA, 0x55])
SYNC_END  = bytes([0xAA, 0x56])
RESP_ACK  = 0x06
RESP_NAK  = 0x15
MAX_PKT   = 256
DEFAULT_BAUD = 115200
ACK_TIMEOUT  = 2.0


def crc32_ieee(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def parse_object_file(path: str) -> dict:
    """RVI .o (JSON) formatını okur → {byte_addr: value} döndürür"""
    import json
    with open(path, 'r', encoding='utf-8') as f:
        obj = json.load(f)

    mem = {}
    text_base = obj['header'].get('entry_point', 0)
    for i, instr_str in enumerate(obj['text']):
        if len(instr_str) == 32 and all(c in '01' for c in instr_str):
            word = int(instr_str, 2)
        else:
            word = int(instr_str, 16)
        addr = text_base + i * 4
        for b in range(4):
            mem[addr + b] = (word >> (8 * b)) & 0xFF

    data_base = 0x00000400
    for i, word_str in enumerate(obj.get('data', [])):
        if len(word_str) == 32 and all(c in '01' for c in word_str):
            word = int(word_str, 2)
        else:
            word = int(word_str, 16)
        addr = data_base + i * 4
        for b in range(4):
            mem[addr + b] = (word >> (8 * b)) & 0xFF

    return mem


def parse_verilog_hex(path: str) -> dict:
    """@adres satırlı Intel/Verilog hex → {byte_addr: value}"""
    mem = {}
    base = 0
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("//")[0].strip()
            if not line:
                continue
            if line.startswith("@"):
                base = int(line[1:], 16)
                continue
            word = int(line, 16)
            for i in range(4):
                mem[base + i] = (word >> (8 * i)) & 0xFF
            base += 4
    return mem


def coalesce_regions(mem: dict):
    if not mem:
        return []
    addrs = sorted(mem.keys())
    regions = []
    start = addrs[0]
    prev = start
    buf = [mem[start]]

    for a in addrs[1:]:
        if a == prev + 1:
            buf.append(mem[a])
        else:
            regions.append((start, bytes(buf)))
            start = a
            buf = [mem[a]]
        prev = a
    regions.append((start, bytes(buf)))
    return regions


def split_chunks(data: bytes, max_size: int):
    for i in range(0, len(data), max_size):
        yield data[i : i + max_size]


def build_packet(addr: int, payload: bytes) -> bytes:
    hdr = struct.pack("<IH", addr & 0xFFFFFFFF, len(payload) & 0xFFFF)
    body = hdr + payload
    crc = struct.pack("<I", crc32_ieee(body))
    return SYNC_PKT + body + crc


def wait_response(ser, timeout: float) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ser.in_waiting:
            return ser.read(1)[0]
        time.sleep(0.01)
    raise TimeoutError("FPGA yanıt zaman aşımı (ACK/NAK bekleniyor)")


def send_packet(ser, pkt: bytes, retries: int = 5) -> None:
    for attempt in range(retries):
        ser.write(pkt)
        ser.flush()
        try:
            resp = wait_response(ser, ACK_TIMEOUT)
        except TimeoutError:
            print(f"    [!] Zaman aşımı, yeniden deneme {attempt + 1}/{retries}")
            continue
        if resp == RESP_ACK:
            return
        if resp == RESP_NAK:
            print(f"    [!] CRC NAK — paket yeniden gönderiliyor ({attempt + 1}/{retries})")
            continue
        print(f"    [!] Beklenmeyen yanıt 0x{resp:02X}")
    raise RuntimeError("Paket gönderilemedi (maksimum deneme aşıldı)")


def upload(ser, hex_path: str, dry_run: bool = False) -> None:
    if hex_path.endswith('.o'):
        mem = parse_object_file(hex_path)
    else:
        mem = parse_verilog_hex(hex_path)
    regions = coalesce_regions(mem)
    total_bytes = sum(len(d) for _, d in regions)
    print(f"[+] {hex_path}: {len(regions)} bölge, {total_bytes} bayt")

    pkt_count = 0
    for addr, data in regions:
        for chunk in split_chunks(data, MAX_PKT):
            pkt = build_packet(addr, chunk)
            pkt_count += 1
            print(f"    Paket #{pkt_count}: addr=0x{addr:08X} size={len(chunk)}")
            if dry_run:
                addr += len(chunk)
                continue
            send_packet(ser, pkt)
            time.sleep(0.005)
            addr += len(chunk)

    if not dry_run:
        ser.write(SYNC_END)
        ser.flush()
        print(f"[+] Oturum sonu gönderildi ({SYNC_END.hex()})")
    print(f"[+] Yükleme tamamlandı — {pkt_count} paket")


def main():
    ap = argparse.ArgumentParser(description="RVI UART FPGA program yükleyici")
    ap.add_argument("hexfile", help="Linker çıktısı (.hex veya .o)")
    ap.add_argument("-p", "--port", default=None, help="Seri port (COM3, /dev/ttyUSB0)")
    ap.add_argument("-b", "--baud", type=int, default=DEFAULT_BAUD)
    ap.add_argument("--dry-run", action="store_true", help="UART açmadan paketleri listele")
    args = ap.parse_args()

    if args.dry_run:
        upload(None, args.hexfile, dry_run=True)
        return

    if not args.port:
        ap.error("UART yukleme icin -p/--port gerekli (dry-run haric)")

    serial = _import_serial()
    print(f"[+] Port açılıyor: {args.port} @ {args.baud}")
    with serial.Serial(args.port, args.baud, timeout=0.1) as ser:
        time.sleep(0.1)
        ser.reset_input_buffer()
        upload(ser, args.hexfile)


if __name__ == "__main__":
    main()
