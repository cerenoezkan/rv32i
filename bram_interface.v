// bram_interface.v
// 4 KB program BRAM — PicoRV32 CPU portu + UART loader backdoor portu.
// Loader aktifken CPU reset'te olduğu için gerçek çakışma olmaz.
//
// Düzeltmeler:
//   1. Gowin block RAM attribute: syn_ramstyle = "block_ram"
//   2. CPU okuma 2-cycle pipeline (Gowin EBR senkron okuma gerektirir)
//   3. CPU ve loader yazmaları TEK always bloğuna alındı → sentez uyarısı yok

module bram_interface (
    input  wire        clk,
    input  wire        rst,

    // --- PicoRV32 bellek busu ---
    input  wire        cpu_valid,
    input  wire [31:0] cpu_addr,
    input  wire [31:0] cpu_wdata,
    input  wire [ 3:0] cpu_wstrb,
    output reg  [31:0] cpu_rdata,
    output reg         cpu_ready,

    // --- Loader backdoor yazma ---
    input  wire        ld_we,
    input  wire [31:0] ld_addr,
    input  wire [ 7:0] ld_wdata,
    input  wire        ld_wstrb,
    output wire        ld_ack,

    // --- Debug okuma ---
    input  wire [31:0] dbg_addr,
    output wire [31:0] dbg_rdata
);

    /* synthesis syn_ramstyle = "block_ram" */
    reg [31:0] bram [0:1023];  // 1024 x 32 bit = 4 KB

    wire cpu_bram_sel = (cpu_addr[31:12] == 20'h00000);
    wire ld_bram_sel  = (ld_addr[31:12]  == 20'h00000);

    assign ld_ack    = ld_we && ld_bram_sel;
    assign dbg_rdata = bram[dbg_addr[11:2]];

    // -----------------------------------------------------------------------
    // TEK always bloğu — CPU yazma + loader yazma + CPU okuma pipeline
    // Gowin sentezleyicisi birden fazla always bloğunun aynı reg'e yazmasından
    // "multiple driver" uyarısı verir. Tek blokta toplayarak bu önlenir.
    //
    // CPU okuma 2-cycle:
    //   Cycle 1: cpu_rdata <= bram[addr]  (RAM'den veri çıkışı)
    //   Cycle 2: cpu_ready <= 1           (PicoRV32 bu cycle'da rdata'yı okur)
    // -----------------------------------------------------------------------
    reg cpu_rd_pending;

    always @(posedge clk) begin
        cpu_ready      <= 1'b0;
        cpu_rd_pending <= 1'b0;

        if (rst) begin
            cpu_ready      <= 1'b0;
            cpu_rd_pending <= 1'b0;
        end else begin
            // --- Loader yazma (öncelik: CPU reset'te, çakışma yok) ---
            if (ld_we && ld_bram_sel && ld_wstrb) begin
                case (ld_addr[1:0])
                    2'b00: bram[ld_addr[11:2]][ 7: 0] <= ld_wdata;
                    2'b01: bram[ld_addr[11:2]][15: 8] <= ld_wdata;
                    2'b10: bram[ld_addr[11:2]][23:16] <= ld_wdata;
                    2'b11: bram[ld_addr[11:2]][31:24] <= ld_wdata;
                endcase
            end

            // --- CPU erişimi ---
            if (cpu_valid && cpu_bram_sel) begin
                if (|cpu_wstrb) begin
                    // YAZMA: byte-enable, aynı cycle'da ready
                    if (cpu_wstrb[0]) bram[cpu_addr[11:2]][ 7: 0] <= cpu_wdata[ 7: 0];
                    if (cpu_wstrb[1]) bram[cpu_addr[11:2]][15: 8] <= cpu_wdata[15: 8];
                    if (cpu_wstrb[2]) bram[cpu_addr[11:2]][23:16] <= cpu_wdata[23:16];
                    if (cpu_wstrb[3]) bram[cpu_addr[11:2]][31:24] <= cpu_wdata[31:24];
                    cpu_ready <= 1'b1;
                end else begin
                    // OKUMA cycle 1: veriyi RAM'den al
                    cpu_rdata      <= bram[cpu_addr[11:2]];
                    cpu_rd_pending <= 1'b1;
                end
            end

            // OKUMA cycle 2: veri stabil → ready ver
            if (cpu_rd_pending)
                cpu_ready <= 1'b1;
        end
    end

endmodule