// tb_bram_interface.v — BRAM CPU okuma/yazma + loader backdoor testi
`timescale 1ns / 1ps

module tb_bram_interface;

    reg clk = 0;
    reg rst = 0;
    reg cpu_valid = 0;
    reg [31:0] cpu_addr = 0;
    reg [31:0] cpu_wdata = 0;
    reg [3:0] cpu_wstrb = 0;
    wire [31:0] cpu_rdata;
    wire cpu_ready;
    reg ld_we = 0;
    reg [31:0] ld_addr = 0;
    reg [7:0] ld_wdata = 0;
    reg ld_wstrb = 0;
    wire ld_ack;

    bram_interface uut (
        .clk(clk), .rst(rst),
        .cpu_valid(cpu_valid), .cpu_addr(cpu_addr),
        .cpu_wdata(cpu_wdata), .cpu_wstrb(cpu_wstrb),
        .cpu_rdata(cpu_rdata), .cpu_ready(cpu_ready),
        .ld_we(ld_we), .ld_addr(ld_addr),
        .ld_wdata(ld_wdata), .ld_wstrb(ld_wstrb),
        .ld_ack(ld_ack),
        .dbg_addr(32'd0), .dbg_rdata()
    );

    always #18 clk = ~clk;

    task cpu_write;
        input [31:0] addr;
        input [31:0] data;
        begin
            @(posedge clk);
            cpu_valid = 1;
            cpu_addr  = addr;
            cpu_wdata = data;
            cpu_wstrb = 4'hF;
            @(posedge clk);
            wait (cpu_ready === 1'b1);
            cpu_valid = 0;
            cpu_wstrb = 0;
            @(posedge clk);
        end
    endtask

    task cpu_read;
        input [31:0] addr;
        output [31:0] data;
        begin
            @(posedge clk);
            cpu_valid = 1;
            cpu_addr  = addr;
            cpu_wstrb = 0;
            @(posedge clk);
            wait (cpu_ready === 1'b1);
            data = cpu_rdata;
            cpu_valid = 0;
            @(posedge clk);
        end
    endtask

    reg [31:0] rd;

    initial begin
        rst = 1;
        repeat (5) @(posedge clk);
        rst = 0;

        ld_we = 1; ld_wstrb = 1;
        ld_addr = 32'h4; ld_wdata = 8'hAB;
        @(posedge clk);
        ld_we = 0; ld_wstrb = 0;
        @(posedge clk);

        cpu_write(32'h4, 32'h1234_5678);
        cpu_read(32'h4, rd);
        if (rd[7:0] !== 8'h78)
            $display("FAIL: CPU read %08X", rd);
        else
            $display("PASS: BRAM loader+CPU OK, rd=%08X", rd);
        $finish;
    end

endmodule
