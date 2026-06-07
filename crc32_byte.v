// crc32_byte.v
// IEEE 802.3 CRC-32 — Bilgisayardaki zlib ile tam uyumlu donanımsal doğrulama motoru.

module crc32_byte (
    input  wire        clk,
    input  wire        rst,
    input  wire        init,        // Yeni paket başında CRC yazmacını sıfırlama sinyali
    input  wire        byte_valid,  // "Gelen bayt kararlı, hesaba kat" sinyali
    input  wire [7:0]  byte_in,     // Şifreye dahil edilecek 8-bitlik veri baytı
    output wire [31:0] crc_out      // Loader FSM'e giden 32-bitlik nihai şifre çıkışı
);

    reg [31:0] crc;

  // Kombinasyonel CRC-32 Güncelleme Fonksiyonu
  function [31:0] crc32_update;
    input [31:0] c;
    input [7:0]  d;
    integer i;
    reg [31:0] x;
    begin
      x = c ^ {24'd0, d}; // 8-bitlik veriyi 32-bite genişletip mevcut CRC ile XOR'la
      for (i = 0; i < 8; i = i + 1) // 1 bayt içindeki 8 bitin her birini sırayla işle
        x = (x[0]) ? ((x >> 1) ^ 32'hEDB88320) : (x >> 1); // Bit 1 ise standart polinomla XOR'la, 0 ise sağa kaydır
      crc32_update = x;
    end
  endfunction

    always @(posedge clk) begin
        if (rst || init)
            crc <= 32'hFFFF_FFFF; // Standart gereği başlangıç değerini tamamen 1'ler yap
        else if (byte_valid)
            crc <= crc32_update(crc, byte_in); // Her yeni geçerli baytta şifreyi güncelle
    end

    // Kritik: zlib standardıyla eşleşmesi için çıkan şifrenin tüm bitlerini ters çevir.
    assign crc_out = ~crc; 

endmodule