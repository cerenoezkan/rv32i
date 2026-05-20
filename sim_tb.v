// sim_tb.v
// ---------------------------------------------------------------------------
// Vivado simülasyon testbench — UART loader doğrulama
//
// Senaryo:
//   - btnC: 100 ns boyunca 1 (reset), sonra 0
//   - uart_rxd üzerinden tek paket + oturum sonu
//   - loader_done gözlemi (10 ms)
// ---------------------------------------------------------------------------

`timescale 1ns / 1ps

module sim_tb;

    localparam integer CLK_HZ      = 100_000_000;
    localparam integer BAUD        = 115200;
    localparam integer CLK_PERIOD  = 10;          // ns
    localparam integer BIT_CLKS    = CLK_HZ / BAUD;

    reg        clk = 1'b0;
    reg        btnC = 1'b1;
    reg        uart_rxd = 1'b1;
    wire       uart_txd;
    wire [15:0] led;

    reg [7:0] pkt [0:17];

    top u_dut (
        .clk     (clk),
        .btnC    (btnC),
        .uart_rxd(uart_rxd),
        .uart_txd(uart_txd),
        .led     (led)
    );

    wire loader_done = u_dut.u_loader.loader_done;
    wire loader_active = u_dut.u_loader.loader_active;

    always #(CLK_PERIOD / 2) clk = ~clk;

    // 8N1 UART bayt gönderimi (uart_rxd hattına)
    task automatic uart_send_byte(input [7:0] data);
        integer i;
        begin
            uart_rxd = 1'b0;  // start
            repeat (BIT_CLKS) @(posedge clk);

            for (i = 0; i < 8; i = i + 1) begin
                uart_rxd = data[i];
                repeat (BIT_CLKS) @(posedge clk);
            end

            uart_rxd = 1'b1;  // stop
            repeat (BIT_CLKS) @(posedge clk);
        end
    endtask

    initial begin
        $display("=== sim_tb: UART loader testi basladi ===");

        // Reset: btnC aktif-yuksek (top.sys_rst = btnC)
        btnC = 1'b1;
        uart_rxd = 1'b1;
        #(100);
        btnC = 1'b0;
        $display("[TB] btnC serbest @ %0t ns", $time);

        // UART modulunun hazir olmasi icin kisa bekleme
        repeat (2000) @(posedge clk);

        // Paket: [AA 55][addr LE][size LE][data][crc32 LE][AA 56]
        // addr=0x00000000, size=4, data=13 00 00 00 (addi x0,x0,0 / nop)
        // CRC32(addr||size||data) = 0x3AB7D211 (IEEE, zlib uyumlu)
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

        // loader_done bekle (en fazla 5 ms)
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

        // Toplam sim sure: 10 ms
        #10_000_000;
        $display("[TB] Simulasyon bitti @ %0t ns, loader_done=%b", $time, loader_done);
        $finish;
    end

    initial begin
        $dumpfile("sim_tb.vcd");
        $dumpvars(0, sim_tb);
    end

endmodule
