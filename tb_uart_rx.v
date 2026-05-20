// tb_uart_rx.v — UART RX + FIFO birim testi (27 MHz, 115200)
`timescale 1ns / 1ps

module tb_uart_rx;

    localparam CLK_HZ     = 27_000_000;
    localparam BAUD       = 115200;
    localparam CLK_PERIOD = 37;
    localparam BIT_CLKS   = CLK_HZ / BAUD;

    reg clk = 0;
    reg rst = 0;
    reg rxd = 1;
    wire fifo_empty, fifo_full;
    wire [7:0] fifo_dout;
    reg fifo_rd_en;

    uart_rx #(.CLK_FREQ(CLK_HZ), .BAUD_RATE(BAUD)) uut (
        .clk(clk), .rst(rst), .rxd(rxd),
        .fifo_empty(fifo_empty), .fifo_full(fifo_full),
        .fifo_dout(fifo_dout), .fifo_rd_en(fifo_rd_en)
    );

    always #(CLK_PERIOD/2) clk = ~clk;

    task uart_bit;
        input b;
        begin
            rxd = b;
            repeat (BIT_CLKS) @(posedge clk);
        end
    endtask

    task uart_byte;
        input [7:0] d;
        integer i;
        begin
            uart_bit(0);
            for (i = 0; i < 8; i = i + 1)
                uart_bit(d[i]);
            uart_bit(1);
        end
    endtask

    initial begin
        fifo_rd_en = 0;
        rst = 1;
        repeat (10) @(posedge clk);
        rst = 0;
        repeat (100) @(posedge clk);

        uart_byte(8'hA5);
        repeat (5000) @(posedge clk);

        if (fifo_empty) begin
            $display("FAIL: FIFO bos");
            $finish;
        end
        fifo_rd_en = 1;
        @(posedge clk);
        fifo_rd_en = 0;
        if (fifo_dout !== 8'hA5)
            $display("FAIL: beklenen A5, alinan %02X", fifo_dout);
        else
            $display("PASS: UART RX byte OK");
        $finish;
    end

endmodule
