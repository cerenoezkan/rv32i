// tb_loader_fsm.v — Loader FSM + CRC + mock RX FIFO testi
`timescale 1ns / 1ps

module tb_loader_fsm;

    reg clk = 0;
    reg rst = 1;
    reg rx_empty = 1;
    reg [7:0] rx_data = 0;
    wire rx_rd;
    wire [7:0] tx_data;
    wire tx_start;
    reg tx_busy = 0;
    wire ld_we;
    wire [31:0] ld_addr;
    wire [7:0] ld_wdata;
    wire ld_wstrb;
    wire ld_ack;
    wire loader_active, loader_done;
    wire [31:0] entry_pc;
    wire entry_pc_load;

    reg [7:0] fifo [0:63];
    reg [5:0] fifo_cnt;
    reg [5:0] fifo_rd;

    loader_fsm uut (
        .clk(clk), .rst(rst),
        .rx_empty(rx_empty), .rx_data(rx_data), .rx_rd(rx_rd),
        .tx_data(tx_data), .tx_start(tx_start), .tx_busy(tx_busy),
        .ld_we(ld_we), .ld_addr(ld_addr), .ld_wdata(ld_wdata),
        .ld_wstrb(ld_wstrb), .ld_ack(ld_ack),
        .loader_active(loader_active), .loader_done(loader_done),
        .entry_pc(entry_pc), .entry_pc_load(entry_pc_load),
        .force_reload(1'b0)
    );

    assign ld_ack = ld_we;

    always #18 clk = ~clk;

    always @(posedge clk) begin
        if (rx_rd && !rx_empty) begin
            fifo_rd <= fifo_rd + 1;
            if (fifo_cnt > 0)
                fifo_cnt <= fifo_cnt - 1;
        end
        rx_empty <= (fifo_cnt == 0);
        if (fifo_cnt > 0)
            rx_data <= fifo[fifo_rd];
    end

    task push_byte;
        input [7:0] b;
        begin
            fifo[fifo_cnt] = b;
            fifo_cnt = fifo_cnt + 1;
            rx_empty = 0;
            rx_data  = fifo[fifo_rd];
        end
    endtask

    initial begin
        fifo_cnt = 0;
        fifo_rd  = 0;
        repeat (20) @(posedge clk);
        rst = 0;

        push_byte(8'hAA); push_byte(8'h55);
        push_byte(8'h00); push_byte(8'h00);
        push_byte(8'h00); push_byte(8'h00);
        push_byte(8'h04); push_byte(8'h00);
        push_byte(8'h13); push_byte(8'h00);
        push_byte(8'h00); push_byte(8'h00);
        push_byte(8'h11); push_byte(8'hD2);
        push_byte(8'hB7); push_byte(8'h3A);

        repeat (50000) @(posedge clk);
        if (tx_start)
            $display("INFO: TX ACK/NAK istendi");
        repeat (50000) @(posedge clk);

        push_byte(8'hAA); push_byte(8'h56);
        repeat (100000) @(posedge clk);

        if (loader_done)
            $display("PASS: loader_done=1");
        else
            $display("FAIL: loader_done=0 state beklenmiyor");
        $finish;
    end

endmodule
