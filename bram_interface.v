// =============================================================================
// Modül   : bram_interface
// Amaç    : PicoRV32 işlemcisi ve Loader FSM için zaman paylaşımlı BRAM arayüzü
// Bellek  : 32 kelime × 32 bit = 128 byte
//           → Test 4 "bellek sınırı zorlama" senaryosu için bilinçli seçilmiştir
//           → TEXT (0x00–0x33) + DATA (0x60–0x7C) tam olarak sığmaktadır
// BRAM    : Senkron okuma + 2 bağımsız erişim bloğu sayesinde Gowin sentezleyici
//           bu belleği DFF yerine fiziksel BSRAM (SDPB) primitiflerine eşler
// =============================================================================

module bram_interface (
    input  wire        clk,
    input  wire        rst,
    input  wire        loader_done, // Loader bitti mi? 0=Loader aktif, 1=CPU aktif
    
    // CPU Hatları
    input  wire        cpu_valid,   // CPU geçerli bir bellek erişimi başlatıyor
    input  wire [31:0] cpu_addr,    // CPU'nun erişmek istediği 32-bit adres
    input  wire [31:0] cpu_wdata,   // CPU'nun yazmak istediği 32-bit veri
    input  wire [ 3:0] cpu_wstrb,   // Byte seçim maskesi: 0000=okuma, xxxx=yazma
    output reg  [31:0] cpu_rdata,   // BRAM'den CPU'ya dönen okuma verisi
    output reg         cpu_ready,   // Handshake: işlem tamamlandı sinyali
    
    // Loader Hatları — UART üzerinden program yükleyici
    input  wire        ld_we,       // Loader yazma isteği
    input  wire [31:0] ld_addr,     // Loader'ın yazdığı hedef adres
    input  wire [ 7:0] ld_wdata,    // Loader'dan gelen 8-bit veri (byte byte yüklenir)
    input  wire        ld_wstrb,    // Loader yazma geçerlilik sinyali
    output wire        ld_ack,      // Loader'a yazmanın kabul edildiğini bildirir
    
    // Debug Hatları — Port B üzerinden bağımsız okuma
    input  wire [31:0] dbg_addr,    // Debug okuma adresi (şu an CPU adresiyle aynı)
    output reg  [31:0] dbg_rdata    // Debug okuma çıkışı (kullanılmıyor, port B kanıtı)
);

    // -------------------------------------------------------------------------
    // BRAM Tanımı
    // 32 kelime = 128 byte
    // Senkron okuma yapıldığı için Gowin sentezleyici bunu BSRAM'e eşler (DFF değil)
    // Sentez raporunda "4 SDPB" olarak görünür → fiziksel BRAM kullanımı kanıtlanır
    // -------------------------------------------------------------------------
    reg [31:0] bram [0:31];

    // -------------------------------------------------------------------------
    // Adres Seçim Sinyalleri
    // cpu_bram_sel: CPU adresi 0x00–0x7F aralığında mı? (bit[31:7] == 0)
    // ld_bram_sel : Loader adresi aynı aralıkta mı?
    // Neden [31:7]? → 2^7 = 128 byte = BRAM boyutu
    // -------------------------------------------------------------------------
    wire cpu_bram_sel = (cpu_addr[31:7] == 25'h0000000);
    wire ld_bram_sel  = (ld_addr[31:7]  == 25'h0000000);

    // Loader yazma aktif mi? (3 koşul birden sağlanmalı)
    wire ld_active = ld_we && ld_bram_sel && ld_wstrb;
    assign ld_ack  = ld_active; // Loader'a anında kabul sinyali

    // -------------------------------------------------------------------------
    // PORT A: Zamansal Çoklayıcı (Time-Division MUX)
    // loader_done=0 → BRAM'e Loader erişir (program yükleme aşaması)
    // loader_done=1 → BRAM'e CPU erişir (program çalışma aşaması)
    // Bu yapı sayesinde tek fiziksel port iki farklı kaynağı sırayla kullanır
    // -------------------------------------------------------------------------
    wire [4:0] port_a_addr  = loader_done ? cpu_addr[6:2] : ld_addr[6:2];
    // Neden [6:2]? → 32 kelime için 5-bit indeks gerekir (2^5=32), bit[1:0] byte seçimi
    
    wire       port_a_valid = loader_done ? (cpu_valid && cpu_bram_sel) : 1'b0;
    wire [3:0] port_a_wstrb = loader_done ? cpu_wstrb : 4'b0000;

    always @(posedge clk) begin
        cpu_ready <= 1'b0; // Her cycle varsayılan olarak sıfırla (tek cycle ready)

        if (loader_done) begin

            // --- CPU Okuma ---
            // wstrb==0000 → yazma yok → okuma isteği
            // Senkron okuma: veri bir sonraki cycle'da cpu_rdata'da hazır olur
            // Bu 1-cycle gecikme top.v'deki kombinasyonel assign ile telafi edilir
            if (port_a_valid && (port_a_wstrb == 4'b0000)) begin
                cpu_rdata <= bram[port_a_addr];
                cpu_ready <= 1'b1;
            end

            // --- CPU Yazma ---
            // wstrb byte maskeleri: [0]=bit7:0, [1]=bit15:8, [2]=bit23:16, [3]=bit31:24
            // Örn: sw komutu → wstrb=1111, sh → 0011 veya 1100, sb → 0001/0010/0100/1000
            if (port_a_valid && (port_a_wstrb != 4'b0000)) begin
                if (port_a_wstrb[0]) bram[port_a_addr][ 7: 0] <= cpu_wdata[ 7: 0];
                if (port_a_wstrb[1]) bram[port_a_addr][15: 8] <= cpu_wdata[15: 8];
                if (port_a_wstrb[2]) bram[port_a_addr][23:16] <= cpu_wdata[23:16];
                if (port_a_wstrb[3]) bram[port_a_addr][31:24] <= cpu_wdata[31:24];
                cpu_ready <= 1'b1;
            end

        end else begin

            // --- Loader Yazma ---
            // Loader byte byte veri gönderir (8-bit)
            // addr[1:0] hangi byte'ın yazılacağını belirler
            if (ld_active) begin
                case (ld_addr[1:0])
                    2'b00: bram[port_a_addr][ 7: 0] <= ld_wdata;
                    2'b01: bram[port_a_addr][15: 8] <= ld_wdata;
                    2'b10: bram[port_a_addr][23:16] <= ld_wdata;
                    2'b11: bram[port_a_addr][31:24] <= ld_wdata;
                endcase
            end

        end
    end

    // -------------------------------------------------------------------------
    // PORT B: Bağımsız Senkron Debug Kapısı
    // Port A'dan tamamen bağımsız ikinci erişim yolu
    // Bu ikinci always bloğu sayesinde sentezleyici SDPB (Simple Dual Port B)
    // primitifini kullanır → sentez raporunda "4 SDPB" çıkmasının sebebi budur
    // Şu an dbg_rdata kullanılmıyor ama port varlığı BRAM eşlemesini garanti eder
    // -------------------------------------------------------------------------
    always @(posedge clk) begin
        dbg_rdata <= bram[dbg_addr[6:2]];
    end

endmodule