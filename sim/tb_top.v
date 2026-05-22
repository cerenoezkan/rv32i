// sim/tb_top.v
// Tang Nano 9K simülasyon testbench — 27 MHz clock, aktif-low reset
//
// Test senaryosu:
//   1. sys_rst_n=0 → reset aktif (100 ns)
//   2. sys_rst_n=1 → reset bırak
//   3. UART üzerinden 1 paket + oturum sonu gönder
//      Paket: addr=0, size=4, data=0x00000013 (NOP), CRC=0x3AB7D211
//   4. loader_done=1 bekleniyor (max 5 ms)

`timescale 1ns / 1ps

module tb_top;

    localparam integer CLK_HZ     = 27_000_000;
    localparam integer BAUD       = 115200;
    localparam integer CLK_PERIOD = 37;            // ~37 ns (27 MHz)
    localparam integer BIT_CLKS   = CLK_HZ / BAUD; // 234 clock/bit

    reg        sys_clk   = 1'b0;
    reg        sys_rst_n = 1'b0;   // başlangıçta reset aktif (active-low)
    reg        uart_rx   = 1'b1;   // idle=1
    wire       uart_tx;
    wire [2:0] led;

    // DUT
    top u_dut (
        .sys_clk  (sys_clk),
        .sys_rst_n(sys_rst_n),
        .uart_rx  (uart_rx),
        .uart_tx  (uart_tx),
        .led      (led)
    );

    // İzleme sinyalleri
    wire loader_done   = u_dut.u_loader.loader_done;
    wire loader_active = u_dut.u_loader.loader_active;
    wire cpu_resetn    = u_dut.cpu_resetn;

    // Clock üreteci: 27 MHz → ~37 ns periyot
    always #(CLK_PERIOD / 2) sys_clk = ~sys_clk;

    // 8N1 UART bayt gönderim görevi
    task automatic uart_send_byte(input [7:0] data);
        integer i;
        begin
            uart_rx = 1'b0;                        // start bit
            repeat (BIT_CLKS) @(posedge sys_clk);
            for (i = 0; i < 8; i = i + 1) begin
                uart_rx = data[i];                 // LSB önce
                repeat (BIT_CLKS) @(posedge sys_clk);
            end
            uart_rx = 1'b1;                        // stop bit
            repeat (BIT_CLKS) @(posedge sys_clk);
        end
    endtask

    // Test akışı
    initial begin
        $display("=== TB: Tang Nano 9K UART Loader Testi ===");
        $display("    CLK=%0d Hz, BAUD=%0d, BIT_CLKS=%0d", CLK_HZ, BAUD, BIT_CLKS);

        // Reset: sys_rst_n=0 → aktif reset
        sys_rst_n = 1'b0;
        uart_rx   = 1'b1;
        #200;

        // Reset bırak
        sys_rst_n = 1'b1;
        $display("[TB] Reset bırakıldı @ %0t ns", $time);

        // UART modülü hazır olana kadar bekle
        repeat (1000) @(posedge sys_clk);

        // ------------------------------------------------------------------
        // Paket: [AA 55] [addr=0x00000000 LE] [size=0x0004 LE]
        //        [data=0x00000013 LE] [CRC32 LE=0x3AB7D211] [AA 56]
        // 0x00000013 = addi x0, x0, 0 (NOP)
        // CRC32(00 00 00 00 04 00 13 00 00 00) = 0x3AB7D211 (zlib uyumlu)
        // ------------------------------------------------------------------
        $display("[TB] UART paketi gönderiliyor...");

        uart_send_byte(8'hAA);   // sync 1
        uart_send_byte(8'h55);   // sync 2 / paket başı
        uart_send_byte(8'h00);   // addr byte 0
        uart_send_byte(8'h00);   // addr byte 1
        uart_send_byte(8'h00);   // addr byte 2
        uart_send_byte(8'h00);   // addr byte 3
        uart_send_byte(8'h04);   // size byte 0 (= 4)
        uart_send_byte(8'h00);   // size byte 1
        uart_send_byte(8'h13);   // data byte 0 (NOP LE)
        uart_send_byte(8'h00);   // data byte 1
        uart_send_byte(8'h00);   // data byte 2
        uart_send_byte(8'h00);   // data byte 3
        uart_send_byte(8'h11);   // CRC byte 0
        uart_send_byte(8'hD2);   // CRC byte 1
        uart_send_byte(8'hB7);   // CRC byte 2
        uart_send_byte(8'h3A);   // CRC byte 3
        uart_send_byte(8'hAA);   // oturum sonu 1
        uart_send_byte(8'h56);   // oturum sonu 2

        $display("[TB] Paket gönderildi @ %0t ns", $time);

        // loader_done bekle (max 5 ms @ 27 MHz = 135000 clock)
        fork
            begin : wait_done
                wait (loader_done === 1'b1);
                $display("[TB] PASS: loader_done=1 @ %0t ns, cpu_resetn=%b, led=%b",
                         $time, cpu_resetn, led);
            end
            begin : timeout_check
                repeat (135000) @(posedge sys_clk);
                if (loader_done !== 1'b1)
                    $display("[TB] FAIL: loader_done zaman asimi @ %0t ns (active=%b)",
                             $time, loader_active);
            end
        join_any
        disable fork;

        // 2 ms daha çalıştır, LED durumunu gözlemle
        repeat (54000) @(posedge sys_clk);
        $display("[TB] Son durum: loader_done=%b, cpu_resetn=%b, led=%b",
                 loader_done, cpu_resetn, led);
        $finish;
    end

    // VCD dump (isteğe bağlı simülatör)
    initial begin
        $dumpfile("sim/tb_top.vcd");
        $dumpvars(0, tb_top);
    end

endmodule