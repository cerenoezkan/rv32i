// bram_interface.v
// ---------------------------------------------------------------------------
// 4 KB program BRAM — PicoRV32 CPU portu + UART loader backdoor portu.
// ---------------------------------------------------------------------------

module bram_interface (
    input  wire        clk,
    input  wire        rst,

    input  wire        cpu_valid,
    input  wire [31:0] cpu_addr,
    input  wire [31:0] cpu_wdata,
    input  wire [ 3:0] cpu_wstrb,
    output reg  [31:0] cpu_rdata,
    output reg         cpu_ready,

    input  wire        ld_we,
    input  wire [31:0] ld_addr,
    input  wire [ 7:0] ld_wdata,
    input  wire        ld_wstrb,
    output wire        ld_ack,

    input  wire [31:0] dbg_addr,
    output wire [31:0] dbg_rdata
);

    /* synthesis syn_ramstyle = "block_ram" */
    reg [31:0] bram [0:1023];

    wire cpu_bram_sel = (cpu_addr[31:12] == 20'h00000);
    wire ld_bram_sel  = (ld_addr[31:12]  == 20'h00000);

    assign ld_ack = ld_we && ld_bram_sel;

    assign dbg_rdata = bram[dbg_addr[11:2]];

    // CPU senkron okuma (registered — Gowin block RAM cikisi)
    always @(posedge clk) begin
        if (cpu_bram_sel)
            cpu_rdata <= bram[cpu_addr[11:2]];
        else
            cpu_rdata <= 32'h0000_0000;
    end

    // CPU senkron yazma + ready (okuma ve yazma)
    always @(posedge clk) begin
        cpu_ready <= 1'b0;
        if (cpu_valid && cpu_bram_sel) begin
            if (|cpu_wstrb) begin
                if (cpu_wstrb[0]) bram[cpu_addr[11:2]][ 7: 0] <= cpu_wdata[ 7: 0];
                if (cpu_wstrb[1]) bram[cpu_addr[11:2]][15: 8] <= cpu_wdata[15: 8];
                if (cpu_wstrb[2]) bram[cpu_addr[11:2]][23:16] <= cpu_wdata[23:16];
                if (cpu_wstrb[3]) bram[cpu_addr[11:2]][31:24] <= cpu_wdata[31:24];
            end
            cpu_ready <= 1'b1;
        end
    end

    // Loader byte yazma
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
