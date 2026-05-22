// top.v
// PicoRV32 + BRAM + UART Loader — Tang Nano 9K (Gowin GW1NR-9C, 27 MHz)
//
// Port isimleri constraints/tang_nano_9k.cst ile birebir eşleşmeli.
//
// Bellek haritası:
//   0x0000_0000 – 0x0000_0FFF : 4 KB BRAM (kod + veri)
//   0x0000_2000               : LED MMIO (sw komutu ile yaz, alt 3 bit)

module top (
    input  wire       sys_clk,    // 27 MHz, pin 52
    input  wire       sys_rst_n,  // aktif-LOW, S1 butonu, pin 4
    input  wire       uart_rx,    // UART alım, pin 18
    output wire       uart_tx,    // UART gönderim, pin 17
    output wire [2:0] led         // aktif-LOW LED, pin 10/11/13
);

    localparam CLK_FREQ  = 27_000_000;
    localparam BAUD_RATE = 115200;

    // aktif-low butonu → aktif-high iç reset
    wire sys_rst = ~sys_rst_n;

    // -----------------------------------------------------------------------
    // UART RX
    // -----------------------------------------------------------------------
    wire       rx_empty, rx_full;
    wire [7:0] rx_data;
    wire       rx_rd;

    uart_rx #(
        .CLK_FREQ (CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) u_uart_rx (
        .clk        (sys_clk),
        .rst        (sys_rst),
        .rxd        (uart_rx),
        .fifo_empty (rx_empty),
        .fifo_full  (rx_full),
        .fifo_dout  (rx_data),
        .fifo_rd_en (rx_rd)
    );

    // -----------------------------------------------------------------------
    // UART TX
    // -----------------------------------------------------------------------
    wire       tx_busy;
    wire [7:0] ldr_tx_data;
    wire       ldr_tx_start;

    uart_tx #(
        .CLK_FREQ (CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) u_uart_tx (
        .clk     (sys_clk),
        .rst     (sys_rst),
        .tx_data (ldr_tx_data),
        .tx_start(ldr_tx_start),
        .tx_busy (tx_busy),
        .txd     (uart_tx)
    );

    // -----------------------------------------------------------------------
    // Loader FSM
    // -----------------------------------------------------------------------
    wire        ld_we, ld_wstrb, ld_ack;
    wire [31:0] ld_addr;
    wire [ 7:0] ld_wdata;
    wire        loader_active, loader_done, force_reload;
    wire [31:0] entry_pc;
    wire        entry_pc_load;

    loader_fsm u_loader (
        .clk          (sys_clk),
        .rst          (sys_rst),
        .rx_empty     (rx_empty),
        .rx_data      (rx_data),
        .rx_rd        (rx_rd),
        .tx_data      (ldr_tx_data),
        .tx_start     (ldr_tx_start),
        .tx_busy      (tx_busy),
        .ld_we        (ld_we),
        .ld_addr      (ld_addr),
        .ld_wdata     (ld_wdata),
        .ld_wstrb     (ld_wstrb),
        .ld_ack       (ld_ack),
        .loader_active(loader_active),
        .loader_done  (loader_done),
        .entry_pc     (entry_pc),
        .entry_pc_load(entry_pc_load),
        .force_reload (force_reload)
    );

    // -----------------------------------------------------------------------
    // CPU Kontrol
    // -----------------------------------------------------------------------
    wire cpu_resetn;

    cpu_control #(
        .DEFAULT_ENTRY_PC(32'h0000_0000)
    ) u_cpu_ctrl (
        .clk          (sys_clk),
        .rst          (sys_rst),
        .sys_rst_n    (sys_rst_n),     // KRİTİK DÜZELTME: btnC→sys_rst_n (aktif-low)
        .loader_done  (loader_done),
        .loader_active(loader_active),
        .entry_pc_in  (entry_pc),
        .entry_pc_load(entry_pc_load),
        .cpu_resetn   (cpu_resetn),
        // entry_pc çıkışı cpu_control'da mevcut ama burada kullanılmıyor;
        // loader_fsm'in entry_pc'si doğrudan cpu_control.entry_pc_in'e bağlı.
        .force_loader (force_reload)
    );

    // -----------------------------------------------------------------------
    // PicoRV32
    // -----------------------------------------------------------------------
    wire        mem_valid, mem_instr;
    reg         mem_ready;
    wire [31:0] mem_addr, mem_wdata;
    reg  [31:0] mem_rdata;
    wire [ 3:0] mem_wstrb;

    picorv32 #(
        .STACKADDR    (32'h0000_0FFC),   // BRAM sonu
        .PROGADDR_RESET(32'h0000_0000),  // PC başlangıcı
        .ENABLE_MUL   (0),
        .ENABLE_DIV   (0),
        .BARREL_SHIFTER(1)
    ) u_cpu (
        .clk      (sys_clk),
        .resetn   (cpu_resetn),
        .mem_valid(mem_valid),
        .mem_instr(mem_instr),
        .mem_ready(mem_ready),
        .mem_addr (mem_addr),
        .mem_wdata(mem_wdata),
        .mem_wstrb(mem_wstrb),
        .mem_rdata(mem_rdata)
    );

    // -----------------------------------------------------------------------
    // BRAM
    // -----------------------------------------------------------------------
    wire [31:0] bram_rdata;
    wire        bram_ready;

    bram_interface u_bram (
        .clk      (sys_clk),
        .rst      (sys_rst),
        .cpu_valid(mem_valid),
        .cpu_addr (mem_addr),
        .cpu_wdata(mem_wdata),
        .cpu_wstrb(mem_wstrb),
        .cpu_rdata(bram_rdata),
        .cpu_ready(bram_ready),
        .ld_we    (ld_we),
        .ld_addr  (ld_addr),
        .ld_wdata (ld_wdata),
        .ld_wstrb (ld_wstrb),
        .ld_ack   (ld_ack),
        .dbg_addr (32'd0),
        .dbg_rdata()
    );

    // -----------------------------------------------------------------------
    // Adres çözümleme & mem_ready / mem_rdata
    // -----------------------------------------------------------------------
    wire bram_sel = (mem_addr[31:12] == 20'h00000);   // 0x0000_0000..0x0000_0FFF
    wire led_sel  = (mem_addr == 32'h0000_2000);        // LED MMIO

    reg [2:0] led_reg;
    assign led = ~led_reg;   // aktif-low: bit=1 → LED kapalı, bit=0 → LED açık

    always @(*) begin
        if (bram_sel)
            mem_rdata = bram_rdata;
        else if (led_sel)
            mem_rdata = {29'h0, led_reg};
        else
            mem_rdata = 32'h0000_0000;
    end

    always @(posedge sys_clk) begin
        mem_ready <= 1'b0;
        if (cpu_resetn && mem_valid) begin
            if (bram_sel) begin
                mem_ready <= bram_ready;
            end else if (led_sel) begin
                if (|mem_wstrb)
                    led_reg <= mem_wdata[2:0];
                mem_ready <= 1'b1;
            end else begin
                mem_ready <= 1'b1;   // bilinmeyen adres: takılma
            end
        end
    end

endmodule