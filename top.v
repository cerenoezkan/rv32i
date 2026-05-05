// top.v
// PicoRV32 + BRAM + LED çıkışı — Basys 3 (Artix-7)
//
// Bellek haritası:
//   0x00000000 – 0x00000FFF : Program BRAM (4KB, $readmemh ile yüklenir)
//   0x00002000              : LED çıkış register'ı (sw komutuyla yazılır)

module top (
    input         clk,        // 100 MHz sistem saati
    input         btnC,       // Merkez buton → reset
    output [15:0] led         // 16 LED
);

// =========================================================
// 1. Reset sinyali (buton aktif-yüksek, 1 tık reset)
// =========================================================
reg reset = 1;
reg [3:0] reset_cnt = 0;

always @(posedge clk) begin
    if (reset_cnt < 4'hF) begin
        reset_cnt <= reset_cnt + 1;
        reset     <= 1;
    end else begin
        reset <= btnC;   // butona basınca tekrar reset
    end
end


// =========================================================
// 2. PicoRV32 sinyalleri
// =========================================================
wire        mem_valid;
wire        mem_instr;
reg         mem_ready;
wire [31:0] mem_addr;
wire [31:0] mem_wdata;
wire [ 3:0] mem_wstrb;
wire [31:0] mem_rdata;

picorv32 #(
    .STACKADDR(32'h0000_0FFC),   // Stack → BRAM sonuna
    .PROGADDR_RESET(32'h0000_0000),
    .ENABLE_MUL(0),
    .ENABLE_DIV(0),
    .BARREL_SHIFTER(1)
) cpu (
    .clk        (clk),
    .resetn     (~reset),
    .mem_valid  (mem_valid),
    .mem_instr  (mem_instr),
    .mem_ready  (mem_ready),
    .mem_addr   (mem_addr),
    .mem_wdata  (mem_wdata),
    .mem_wstrb  (mem_wstrb),
    .mem_rdata  (mem_rdata)
);


// =========================================================
// 3. Program BRAM (4KB = 1024 × 32-bit)
// =========================================================
reg [31:0] bram [0:1023];

initial begin
    $readmemh("output.hex", bram);   // linker çıktısı buraya yüklenir
end

wire bram_sel = (mem_addr[31:12] == 20'h00000);  // 0x00000xxx


// =========================================================
// 4. LED register (adres 0x00002000)
// =========================================================
reg [15:0] led_reg = 0;
assign led = led_reg;

wire led_sel = (mem_addr == 32'h0000_2000);


// =========================================================
// 5. Bellek arayüzü (tek döngülü)
// =========================================================
// Kombinasyonel okuma
always @(*) begin
    if (bram_sel)
        mem_rdata = bram[mem_addr[11:2]];
    else
        mem_rdata = 32'h0000_0000;
end

// Senkron yazma + ready
always @(posedge clk) begin
    mem_ready <= 0;
    if (mem_valid && !mem_ready) begin
        if (bram_sel) begin
            if (mem_wstrb[0]) bram[mem_addr[11:2]][ 7: 0] <= mem_wdata[ 7: 0];
            if (mem_wstrb[1]) bram[mem_addr[11:2]][15: 8] <= mem_wdata[15: 8];
            if (mem_wstrb[2]) bram[mem_addr[11:2]][23:16] <= mem_wdata[23:16];
            if (mem_wstrb[3]) bram[mem_addr[11:2]][31:24] <= mem_wdata[31:24];
            mem_ready <= 1;
        end
        else if (led_sel && mem_wstrb != 4'b0000) begin
            led_reg   <= mem_wdata[15:0];
            mem_ready <= 1;
        end
        else begin
            mem_ready <= 1;
        end
    end
end

endmodule