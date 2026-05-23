// crc32_byte.v

// ---------------------------------------------------------------------------

// IEEE 802.3 CRC-32 — bayt-seri güncelleme (zlib/binascii ile uyumlu).

// Polynomial: 0x04C11DB7, init=0xFFFFFFFF, final XOR=0xFFFFFFFF

// ---------------------------------------------------------------------------



module crc32_byte (

    input  wire        clk,

    input  wire        rst,

    input  wire        init,        // CRC sıfırla

    input  wire        byte_valid,

    input  wire [7:0]  byte_in,

    output wire [31:0] crc_out

);



    reg [31:0] crc;



  function [31:0] crc32_update;

    input [31:0] c;

    input [7:0]  d;

    integer i;

    reg [31:0] x;

    begin

      x = c ^ {24'd0, d};

      for (i = 0; i < 8; i = i + 1)

        x = (x[0]) ? ((x >> 1) ^ 32'hEDB88320) : (x >> 1);

      crc32_update = x;

    end

  endfunction



    always @(posedge clk) begin

        if (rst || init)

            crc <= 32'hFFFF_FFFF;

        else if (byte_valid)

            crc <= crc32_update(crc, byte_in);

    end



    assign crc_out = ~crc;



endmodule