// =============================================================================
// Modül   : top
// Amaç    : PicoRV32 tabanlı FPGA sistemi üst modülü
// İçerik  : PicoRV32 işlemci + BRAM bellek + UART RX/TX + LED çevre birimi
//           + Loader FSM (UART üzerinden program yükleme)
// Saat    : 27 MHz (Sipeed Tang Nano 9K dahili osilatör)
// =============================================================================

module top (
    input  wire       sys_clk,   // 27 MHz sistem saati
    input  wire       sys_rst_n, // Aktif-düşük reset (butona bağlı)
    input  wire       uart_rx,   // UART alım hattı
    output wire       uart_tx,   // UART gönderim hattı
    output wire [5:0] led        // 6-bit LED çıkışı (aktif-düşük)
);

    localparam CLK_FREQ  = 27_000_000; // Baud hesabı için saat frekansı
    localparam BAUD_RATE = 115200;     // UART baud hızı

    wire sys_rst = ~sys_rst_n; // Aktif-yüksek reset türet

    // -------------------------------------------------------------------------
    // UART RX FIFO Kontrol
    // cpu_rx_rd: CPU'nun UART verisini okuma koşulları:
    //   1. loader_done=1  → Program yüklemesi bitti, CPU çalışıyor
    //   2. !rx_empty      → FIFO'da okunacak veri var
    //   3. mem_valid       → CPU geçerli bir bellek erişimi yapıyor
    //   4. uart_data_sel   → Erişilen adres UART veri yazmacı (0x2008)
    //   5. wstrb==0000     → Bu bir okuma işlemi
    // -------------------------------------------------------------------------
    wire       rx_empty, rx_full;
    wire [7:0] rx_data;
    wire       ldr_rx_rd;
    wire       cpu_rx_rd = loader_done && !rx_empty && mem_valid && uart_data_sel && (mem_wstrb == 4'b0000);
    wire       rx_rd = loader_done ? cpu_rx_rd : ldr_rx_rd; // Loader önce, CPU sonra

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

    // -------------------------------------------------------------------------
    // UART TX
    // Sadece Loader FSM tarafından kullanılır (ACK/durum mesajları gönderir)
    // -------------------------------------------------------------------------
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

    // -------------------------------------------------------------------------
    // Loader FSM
    // UART üzerinden gelen binary veriyi BRAM'e byte byte yazar
    // loader_done=0 süresince CPU reset'te tutulur, bellek Loader'a aittir
    // loader_done=1 olduğunda CPU serbest bırakılır
    // -------------------------------------------------------------------------
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
        .rx_rd        (ldr_rx_rd),
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

    // -------------------------------------------------------------------------
    // CPU Kontrol
    // Loader tamamlanana kadar CPU'yu reset'te tutar
    // entry_pc: Loader'ın bildirdiği program başlangıç adresi
    // -------------------------------------------------------------------------
    wire cpu_resetn;

    cpu_control #(
        .DEFAULT_ENTRY_PC(32'h0000_0000)
    ) u_cpu_ctrl (
        .clk          (sys_clk),
        .rst          (sys_rst),
        .sys_rst_n    (sys_rst_n),
        .loader_done  (loader_done),
        .loader_active(loader_active),
        .entry_pc_in  (entry_pc),
        .entry_pc_load(entry_pc_load),
        .cpu_resetn   (cpu_resetn),
        .entry_pc     (),
        .force_loader (force_reload)
    );

    // -------------------------------------------------------------------------
    // PicoRV32 İşlemci
    // Bellek arayüzü: valid/ready el sıkışması (handshake)
    //   mem_valid=1 → CPU erişim istiyor
    //   mem_ready=1 → Bellek/çevre birimi cevap verdi, işlem tamamlandı
    // STACKADDR: Stack işaretçisinin başlangıç adresi
    //   → BRAM 128 byte olduğundan 0x007C olarak ayarlandı (son kelime)
    // -------------------------------------------------------------------------
    wire        mem_valid, mem_instr;
    wire        mem_ready;       // CPU'ya giden ana hazır sinyali
    reg         mem_ready_reg;   // Çevre birimleri (LED/UART) için hazır yazmacı
    wire [31:0] mem_addr, mem_wdata;
    reg  [31:0] mem_rdata;
    wire [ 3:0] mem_wstrb;

    picorv32 #(
        .STACKADDR     (32'h0000_007C), // 128 byte BRAM sınırına göre ayarlandı
        .PROGADDR_RESET(32'h0000_0000), // Program 0x0 adresinden başlar
        .ENABLE_MUL    (0),             // Çarpma devre dışı (kaynak tasarrufu)
        .ENABLE_DIV    (0),             // Bölme devre dışı (kaynak tasarrufu)
        .BARREL_SHIFTER(1)              // Hızlı kaydırma etkin
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

    // -------------------------------------------------------------------------
    // BRAM Arayüzü
    // Loader ve CPU erişimlerini zaman paylaşımlı MUX ile yönetir
    // dbg_addr: Port B'yi aktif tutmak için CPU adresiyle besleniyor
    //           → Gowin sentezleyicinin SDPB primitifi kullanmasını sağlar
    // -------------------------------------------------------------------------
    wire [31:0] bram_rdata;
    wire        bram_ready;

    bram_interface u_bram (
        .clk          (sys_clk),
        .rst          (sys_rst),
        .loader_done  (loader_done),
        .cpu_valid    (mem_valid),
        .cpu_addr     (mem_addr),
        .cpu_wdata    (mem_wdata),
        .cpu_wstrb    (mem_wstrb),
        .cpu_rdata    (bram_rdata),
        .cpu_ready    (bram_ready),
        .ld_we        (ld_we),
        .ld_addr      (ld_addr),
        .ld_wdata     (ld_wdata),
        .ld_wstrb     (ld_wstrb),
        .ld_ack       (ld_ack),
        .dbg_addr     (mem_addr), // Port B'yi aktif tut → SDPB eşlemesi garanti
        .dbg_rdata    ()
    );

    // -------------------------------------------------------------------------
    // Adres Haritası (Memory Map)
    // 0x0000_0000 – 0x0000_007F : BRAM (128 byte) — kod + veri
    // 0x0000_2000                : LED yazmacı (6-bit)
    // 0x0000_2008                : UART RX veri yazmacı
    // 0x0000_200C                : UART RX hazır durum yazmacı
    //
    // bram_sel: bit[31:7]==0 kontrolü → 2^7=128 byte BRAM alanını seçer
    //           Eski tasarımda bit[31:12] kullanılıyordu (4KB), BRAM boyutuyla
    //           uyumsuzdu — şimdi düzeltildi
    // -------------------------------------------------------------------------
    wire bram_sel      = (mem_addr[31:7] == 25'h0000000);
    wire led_sel       = (mem_addr == 32'h0000_2000);
    wire uart_data_sel = (mem_addr == 32'h0000_2008);
    wire uart_rdy_sel  = (mem_addr == 32'h0000_200C);

    // -------------------------------------------------------------------------
    // UART RX Veri Tamponu
    // cpu_rx_rd tetiklendiğinde rx_data yakalanır, CPU okuyana kadar saklanır
    // uart_data_valid: CPU'nun okuduğunu bildiren flag
    // -------------------------------------------------------------------------
    reg [7:0] uart_data_reg;
    reg       uart_data_valid;

    always @(posedge sys_clk) begin
        if (sys_rst) begin
            uart_data_reg   <= 8'h00;
            uart_data_valid <= 1'b0;
        end else begin
            if (cpu_rx_rd) begin
                uart_data_reg   <= rx_data;
                uart_data_valid <= 1'b1;
            end
            if (mem_valid && uart_data_sel && mem_wstrb == 4'b0000 && uart_data_valid)
                uart_data_valid <= 1'b0;
        end
    end

    reg [5:0] led_reg;
    assign led = ~led_reg; // LED aktif-düşük: reg=1 → LED söner, reg=0 → LED yanar

    // -------------------------------------------------------------------------
    // Bus Veri Çoklayıcı
    // CPU mem_rdata'yı okurken hangi kaynaktan geldiğine burada karar verilir
    // Öncelik: BRAM > LED > UART data > UART ready > NOP
    // NOP (0x00000013): Tanımsız adrese erişimde CPU'nun takılmaması için
    // -------------------------------------------------------------------------
    always @(*) begin
        if (bram_sel)
            mem_rdata = bram_rdata;
        else if (led_sel)
            mem_rdata = {26'h0, led_reg};
        else if (uart_data_sel)
            mem_rdata = {24'h0, uart_data_reg};
        else if (uart_rdy_sel)
            mem_rdata = {31'h0, uart_data_valid};
        else
            mem_rdata = 32'h00000013; // RISC-V NOP güvenlik değeri
    end

    // -------------------------------------------------------------------------
    // Çevre Birimi Ready Üreteci
    // BRAM dışındaki erişimler (LED, UART) için mem_ready_reg üretilir
    // mem_ready_reg her cycle sıfırlanır → tek cycle'lık darbe (pulse) olur
    // Bu, CPU'nun aynı işlemi iki kez yapmasını önler
    // -------------------------------------------------------------------------
    always @(posedge sys_clk) begin
        mem_ready_reg <= 1'b0;
        if (sys_rst) begin
            led_reg <= 6'b000000;
        end else if (mem_valid) begin
            if (!bram_sel) begin
                if (led_sel && mem_wstrb != 4'b0000)
                    led_reg <= mem_wdata[5:0];
                mem_ready_reg <= 1'b1;
            end
        end
    end

    // -------------------------------------------------------------------------
    // mem_ready Kombinasyonel Köprü
    // Senkron BRAM okuması 1 cycle gecikme getirir — bram_ready bunu yansıtır
    // Çevre birimleri için mem_ready_reg kullanılır (register tabanlı)
    // İkisi arasında bram_sel ile kombinasyonel seçim yapılır
    // -------------------------------------------------------------------------
    assign mem_ready = bram_sel ? bram_ready : mem_ready_reg;

endmodule