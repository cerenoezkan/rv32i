# RVI Linker Script — FPGA BRAM (4 KB) için
# DATA bölümü BRAM içinde (0x400), LED MMIO 0x2000 dışında kalır

TEXT_BASE = 0x00000000;
DATA_BASE = 0x00000400;