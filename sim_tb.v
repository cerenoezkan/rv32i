// sim_tb.v
// ---------------------------------------------------------------------------
// Gowin / Modelsim simülasyon testbench — UART loader doğrulama
// Tang Nano 9K: 27 MHz sys_clk
//
// Senaryo:
//   - sys_rst_n: 100 ns boyunca 0 (reset, active-low), sonra 1
//   - uart_rx hattına tek paket + oturum sonu
//   - loader_done gözlemi (10 ms)
// ---------------------------------------------------------------------------

`timescale 1ns / 1ps

module sim_tb;

    localparam integer CLK_HZ      = 27_000_000;
    localparam integer BAUD        = 115200;
    localparam integer CLK_PERIOD  = 37;          // ns (~27 MHz)
    localparam integer BIT_CLKS    = CLK_HZ / BAUD;  // 234

    reg        sys_clk = 1'b0;
    reg        sys_rst_n = 1'b0;
    reg        uart_rx = 1'b1;
    wire       uart_tx;
    wire [2:0] led;

    reg [7:0] pkt [0:17];

    top u_dut (
        .sys_clk   (sys_clk),
        .sys_rst_n (sys_rst_n),
        .uart_rx   (uart_rx),
        .uart_tx   (uart_tx),
        .led       (led)
    );

    wire loader_done = u_dut.u_loader.loader_done;
    wire loader_active = u_dut.u_loader.loader_active;

    always #(CLK_PERIOD / 2) sys_clk = ~sys_clk;

    task automatic uart_send_byte(input [7:0] data);
        integer i;
        begin
            uart_rx = 1'b0;
            repeat (BIT_CLKS) @(posedge sys_clk);

            for (i = 0; i < 8; i = i + 1) begin
                uart_rx = data[i];
                repeat (BIT_CLKS) @(posedge sys_clk);
            end

            uart_rx = 1'b1;
            repeat (BIT_CLKS) @(posedge sys_clk);
        end
    endtask

    initial begin
        $display("=== sim_tb: UART loader testi basladi (27 MHz) ===");

        // Reset: sys_rst_n active-low (0 = basili)
        sys_rst_n = 1'b0;
        uart_rx   = 1'b1;
        #(100);
        sys_rst_n = 1'b1;
        $display("[TB] sys_rst_n serbest @ %0t ns", $time);

        repeat (2000) @(posedge sys_clk);

        pkt[0]=8'hAA;  pkt[1]=8'h55;
        pkt[2]=8'h00;  pkt[3]=8'h00;
        pkt[4]=8'h00;  pkt[5]=8'h00;
        pkt[6]=8'h04;  pkt[7]=8'h00;
        pkt[8]=8'h13;  pkt[9]=8'h00;
        pkt[10]=8'h00; pkt[11]=8'h00;
        pkt[12]=8'h11; pkt[13]=8'hD2;
        pkt[14]=8'hB7; pkt[15]=8'h3A;
        pkt[16]=8'hAA; pkt[17]=8'h56;
        begin: send_loop
            integer k;
            for (k=0; k<18; k=k+1)
                uart_send_byte(pkt[k]);
        end

        $display("[TB] UART paketi gonderildi @ %0t ns", $time);

        // fork/join_any: Modelsim ve Gowin sim ile uyumlu
        fork
            begin
                wait (loader_done === 1'b1);
                $display("[TB] PASS: loader_done=1 @ %0t ns", $time);
            end
            begin
                #5_000_000;
                if (loader_done !== 1'b1)
                    $display("[TB] FAIL: loader_done zaman asimi @ %0t ns (active=%b)",
                             $time, loader_active);
            end
        join_any
        disable fork;

        #10_000_000;
        $display("[TB] Simulasyon bitti @ %0t ns, loader_done=%b", $time, loader_done);
        $finish;
    end

    initial begin
        $dumpfile("sim_tb.vcd");
        $dumpvars(0, sim_tb);
    end

endmodule
