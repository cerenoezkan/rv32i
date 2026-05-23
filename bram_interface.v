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

    reg [31:0] bram [0:31];



    wire cpu_bram_sel = (cpu_addr[31:12] == 20'h00000);

    wire ld_bram_sel  = (ld_addr[31:12]  == 20'h00000);

    wire ld_active    = ld_we && ld_bram_sel && ld_wstrb;



    assign ld_ack    = ld_active;

    assign dbg_rdata = bram[dbg_addr[6:2]];



    // Kombinasyonel okuma

    always @(*) begin

        cpu_rdata = bram[cpu_addr[6:2]];

    end



    always @(posedge clk) begin

        cpu_ready <= 1'b0;



        if (ld_active) begin

            case (ld_addr[1:0])

                2'b00: bram[ld_addr[6:2]][ 7: 0] <= ld_wdata;

                2'b01: bram[ld_addr[6:2]][15: 8] <= ld_wdata;

                2'b10: bram[ld_addr[6:2]][23:16] <= ld_wdata;

                2'b11: bram[ld_addr[6:2]][31:24] <= ld_wdata;

            endcase

        end



        if (cpu_valid && cpu_bram_sel) begin

            if (cpu_wstrb != 4'b0000) begin

                if (cpu_wstrb[0]) bram[cpu_addr[6:2]][ 7: 0] <= cpu_wdata[ 7: 0];

                if (cpu_wstrb[1]) bram[cpu_addr[6:2]][15: 8] <= cpu_wdata[15: 8];

                if (cpu_wstrb[2]) bram[cpu_addr[6:2]][23:16] <= cpu_wdata[23:16];

                if (cpu_wstrb[3]) bram[cpu_addr[6:2]][31:24] <= cpu_wdata[31:24];

            end

            cpu_ready <= 1'b1;

        end

    end



endmodule