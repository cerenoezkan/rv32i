// bram_interface.v
// 4 KB program BRAM — PicoRV32 CPU portu + UART loader backdoor portu.
// Loader aktifken CPU reset'te olduğu için çakışma önlenir.
//
// DÜZELTMELEr:
//   1. Gowin BRAM attribute: syn_ramstyle = "block_ram"
//   2. CPU okuma için ready sinyali eklendi (önceki versiyonda eksikti —
//      CPU sadece yazma işleminde ready alıyordu, okumada sonsuza kilitleniyor)
//   3. cpu_rdata registered yapıldı (Gowin block RAM output registered)

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

    // --- Debug okuma (isteğe bağlı) ---
    input  wire [31:0] dbg_addr,
    output wire [31:0] dbg_rdata
);

    // Gowin block RAM sentez yönergesi
    /* synthesis syn_ramstyle = "block_ram" */
    reg [31:0] bram [0:1023];  // 1024 x 32 bit = 4 KB

    wire cpu_bram_sel = (cpu_addr[31:12] == 20'h00000);
    wire ld_bram_sel  = (ld_addr[31:12]  == 20'h00000);

    // Loader ACK: kombinasyonel (ld_we ve adres geçerliyse anında)
    assign ld_ack    = ld_we && ld_bram_sel;
    assign dbg_rdata = bram[dbg_addr[11:2]];

    // -----------------------------------------------------------------------
    // CPU portu: senkron okuma + yazma
    //
    // KRİTİK DÜZELTME: Gowin block RAM senkron okuma yapar — veri bir
    // sonraki cycle'da gelir. Önceki kodda cpu_ready ve cpu_rdata aynı
    // cycle'da set ediliyordu; PicoRV32 ready=1 gördüğü cycle'da rdata'yı
    // okur ama veri henüz RAM'den çıkmamıştı → yanlış instruction fetch.
    //
    // Çözüm: okuma isteğini pipeline'a al (cpu_rd_pending), bir sonraki
    // cycle'da cpu_ready=1 üret. Bu 2-cycle latency Gowin EBR ile uyumludur.
    // -----------------------------------------------------------------------
    reg cpu_rd_pending;   // okuma bekliyor: bir sonraki cycle'da ready ver

    always @(posedge clk) begin
        cpu_ready      <= 1'b0;
        cpu_rd_pending <= 1'b0;

        if (cpu_valid && cpu_bram_sel) begin
            if (|cpu_wstrb) begin
                // YAZMA: byte-enable ile — aynı cycle'da ready
                if (cpu_wstrb[0]) bram[cpu_addr[11:2]][ 7: 0] <= cpu_wdata[ 7: 0];
                if (cpu_wstrb[1]) bram[cpu_addr[11:2]][15: 8] <= cpu_wdata[15: 8];
                if (cpu_wstrb[2]) bram[cpu_addr[11:2]][23:16] <= cpu_wdata[23:16];
                if (cpu_wstrb[3]) bram[cpu_addr[11:2]][31:24] <= cpu_wdata[31:24];
                cpu_ready <= 1'b1;
            end else begin
                // OKUMA 1. cycle: adresi RAM'e ver, veriyi tetikle
                cpu_rdata      <= bram[cpu_addr[11:2]];
                cpu_rd_pending <= 1'b1;   // bir sonraki cycle'da ready üret
            end
        end

        // OKUMA 2. cycle: veri artık cpu_rdata'da stabil → ready ver
        if (cpu_rd_pending)
            cpu_ready <= 1'b1;
    end

    // -----------------------------------------------------------------------
    // Loader portu: bayt-bazlı senkron yazma
    // CPU reset'te olduğu sürece çakışma yok.
    // -----------------------------------------------------------------------
    always @(posedge clk) begin
        if (ld_we && ld_bram_sel && ld_wstrb) begin
            case (ld_addr[1:0])
                2'b00: bram[ld_addr[11:2]][ 7: 0] <= ld_wdata;
                2'b01: bram[ld_addr[11:2]][15: 8] <= ld_wdata;
                2'b10: bram[ld_addr[11:2]][23:16] <= ld_wdata;
                2'b11: bram[ld_addr[11:2]][31:24] <= ld_wdata;
            endcase
        end
    end

endmodule