// loader_fsm.v — DÜZELTME: her rx_rd sonrası 1 cycle bekleme eklendi

module loader_fsm #(
    parameter integer MAX_PKT_SIZE = 256
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        rx_empty,
    input  wire [7:0]  rx_data,
    output reg         rx_rd,
    output reg  [7:0]  tx_data,
    output reg         tx_start,
    input  wire        tx_busy,
    output reg         ld_we,
    output reg  [31:0] ld_addr,
    output reg  [ 7:0] ld_wdata,
    output reg         ld_wstrb,
    input  wire        ld_ack,
    output reg         loader_active,
    output reg         loader_done,
    output reg  [31:0] entry_pc,
    output reg         entry_pc_load,
    input  wire        force_reload
);

    // Protokol Şifreleri ve Onay Kodları
    localparam [7:0] SYNC_B0  = 8'hAA;   // Birinci paket başı senkronizasyon şifresi
    localparam [7:0] SYNC_B1  = 8'h55;   // İkinci paket başı senkronizasyon şifresi
    localparam [7:0] SYNC_END = 8'h56;   // Oturum sonlandırma (Yükleme bitti) şifresi
    localparam [7:0] RESP_ACK = 8'h06;   // Paket başarıyla yazıldı onay kodu (ACK)
    localparam [7:0] RESP_NAK = 8'h15;   // CRC şifresi hatalı çıktı hata kodu (NAK)

    // Ana Durumlar
    localparam [4:0]
        S_IDLE              = 5'd0,      // UART tamponunda veri bekler
        S_IDLE_WAIT         = 5'd1,      // FIFO okuma kararlılığı için 1 çevrim bekleme
        S_WAIT_HEADER       = 5'd2,      // İkinci şifreyi (0x55) denetleme durumu
        S_WAIT_HEADER_WAIT  = 5'd3,      // FIFO okuma kararlılığı için 1 çevrim bekleme
        S_RECEIVE_PACKET    = 5'd4,      // Paket gövdesini bayt bayt toplama tetiklemesi
        S_RECEIVE_WAIT      = 5'd5,      // Baytları donanımsal alt fazlara dağıtma ve bekleme
        S_VALIDATE_CRC      = 5'd6,      // Hesaplanan CRC ile gelen CRC şifresini karşılaştırma
        S_WRITE_BRAM        = 5'd7,      // Doğrulanan kodları BRAM'e satır satır yazma
        S_NEXT_PACKET       = 5'd8,      // ACK/NAK sinyalinin hattan çıkmasını bekleme
        S_NEXT_PACKET_WAIT  = 5'd9,      // Sonraki yeni paketin gelmesini 1 çevrim bekleme
        S_LOAD_DONE         = 5'd10,     // Yüklemeyi bitirip başlangıç adresini kilitleme
        S_RELEASE_CPU_RESET = 5'd11;     // CPU reset hattını serbest bırakıp işlemi başlatma

    // Paket Alım Alt Fazları
    localparam [2:0]
        R_ADDR = 3'd0,                   // 4 baytlık hedef RAM adresi toplama fazı
        R_SIZE = 3'd1,                   // 2 baytlık kod boyutu toplama fazı
        R_DATA = 3'd2,                   // Saf makine kodlarını toplama fazı
        R_CRC  = 3'd3;                   // 4 baytlık bütünsel paket CRC şifresi toplama fazı

    reg [4:0]  state;
    reg [2:0]  recv_phase;
    reg [31:0] pkt_addr;
    reg [15:0] pkt_size;
    reg [15:0] data_idx;
    reg [1:0]  hdr_idx;
    reg [1:0]  crc_idx;
    reg [31:0] crc_recv;
    reg [7:0]  data_buf [0:MAX_PKT_SIZE-1];

    reg        crc_init;
    reg        crc_feed;
    reg [7:0]  crc_byte_in;
    reg [1:0]  crc_settle;
    wire [31:0] crc_computed;

    crc32_byte u_crc (
        .clk        (clk),
        .rst        (rst),
        .init       (crc_init),
        .byte_valid (crc_feed),
        .byte_in    (crc_byte_in),
        .crc_out    (crc_computed)
    );

    always @(posedge clk) begin
        if (rst) begin
            state         <= S_IDLE;
            recv_phase    <= R_ADDR;
            rx_rd         <= 1'b0;
            ld_we         <= 1'b0;
            ld_addr       <= 32'd0;
            ld_wdata      <= 8'd0;
            ld_wstrb      <= 1'b0;
            loader_active <= 1'b0;
            loader_done   <= 1'b0;
            entry_pc      <= 32'h0000_0000;
            entry_pc_load <= 1'b0;
            tx_data       <= 8'd0;
            tx_start      <= 1'b0;
            pkt_addr      <= 32'd0;
            pkt_size      <= 16'd0;
            data_idx      <= 16'd0;
            hdr_idx       <= 2'd0;
            crc_idx       <= 2'd0;
            crc_recv      <= 32'd0;
            crc_init      <= 1'b0;
            crc_feed      <= 1'b0;
            crc_byte_in   <= 8'd0;
            crc_settle    <= 2'd0;
        end else begin
            rx_rd         <= 1'b0;
            ld_we         <= 1'b0;
            ld_wstrb      <= 1'b0;
            tx_start      <= 1'b0;
            entry_pc_load <= 1'b0;
            crc_init      <= 1'b0;
            crc_feed      <= 1'b0;

            if (force_reload) begin
                loader_done   <= 1'b0;
                loader_active <= 1'b1;
                state         <= S_IDLE;
            end

            case (state)

                S_IDLE: begin
                    loader_active <= !loader_done;
                    if (!rx_empty) begin  
                        rx_rd <= 1'b1;    // FIFO'dan ilk bayt okumasını tetikle
                        state <= S_IDLE_WAIT;
                    end
                end

                S_IDLE_WAIT: begin
                    if (rx_data == SYNC_B0) begin // İlk bayt 0xAA ise seansı başlat
                        loader_done <= 1'b0;  
                        state <= S_WAIT_HEADER;
                    end else
                        state <= S_IDLE;
                end

                S_WAIT_HEADER: begin
                    if (!rx_empty) begin
                        rx_rd <= 1'b1;    // İkinci bayt okumasını tetikle
                        state <= S_WAIT_HEADER_WAIT;
                    end
                end

                S_WAIT_HEADER_WAIT: begin
                    if (rx_data == SYNC_B1) begin // İkinci bayt 0x55 ise alt fazları kur
                        pkt_addr   <= 32'd0;
                        pkt_size   <= 16'd0;
                        hdr_idx    <= 2'd0;
                        data_idx   <= 16'd0;
                        crc_idx    <= 2'd0;
                        recv_phase <= R_ADDR;     // Hedef adres fazını aktif et
                        crc_init   <= 1'b1;       // CRC donanım modülünü sıfırla
                        state      <= S_RECEIVE_PACKET;
                    end else if (rx_data == SYNC_END) begin // 0x56 geldiyse bitişe geç
                        state <= S_LOAD_DONE;
                    end else begin
                        state <= S_IDLE;
                    end
                end

                S_RECEIVE_PACKET: begin
                    if (!rx_empty) begin
                        rx_rd <= 1'b1;    // Paket gövdesinden yeni bayt tetikle
                        state <= S_RECEIVE_WAIT;
                    end
                end

                S_RECEIVE_WAIT: begin
                    crc_byte_in <= rx_data;

                    // Adres, Boyut ve Veri baytlarını gerçek zamanlı CRC modülüne besle
                    if (recv_phase == R_ADDR ||
                        recv_phase == R_SIZE ||
                        recv_phase == R_DATA)
                        crc_feed <= 1'b1;

                    case (recv_phase)
                        R_ADDR: begin
                            case (hdr_idx)
                                2'd0: pkt_addr[ 7: 0] <= rx_data;
                                2'd1: pkt_addr[15: 8] <= rx_data;
                                2'd2: pkt_addr[23:16] <= rx_data;
                                2'd3: pkt_addr[31:24] <= rx_data;
                            endcase
                            if (hdr_idx == 2'd3) begin
                                hdr_idx    <= 2'd0;
                                recv_phase <= R_SIZE; // 4 bayt bitti, boyuta geç
                            end else
                                hdr_idx <= hdr_idx + 2'd1;
                            state <= S_RECEIVE_PACKET;
                        end

                        R_SIZE: begin
                            case (hdr_idx)
                                2'd0: pkt_size[ 7: 0] <= rx_data;
                                2'd1: pkt_size[15: 8] <= rx_data;
                            endcase
                            if (hdr_idx == 2'd1) begin
                                hdr_idx    <= 2'd0;
                                data_idx   <= 16'd0;
                                recv_phase <= R_DATA; // 2 bayt bitti, saf koda geç
                            end else
                                hdr_idx <= hdr_idx + 2'd1;
                            state <= S_RECEIVE_PACKET;
                        end

                        R_DATA: begin
                            if (pkt_size == 16'd0) begin
                                recv_phase <= R_CRC;
                                state      <= S_RECEIVE_PACKET;
                            end else begin
                                data_buf[data_idx] <= rx_data; // Kodları donanım dizisine yaz
                                data_idx <= data_idx + 16'd1;
                                if (data_idx + 16'd1 == pkt_size)
                                    recv_phase <= R_CRC; // Belirtilen boyut doldu, CRC'ye geç
                                state <= S_RECEIVE_PACKET;
                            end
                        end

                        R_CRC: begin
                            case (crc_idx)
                                2'd0: crc_recv[ 7: 0] <= rx_data;
                                2'd1: crc_recv[15: 8] <= rx_data;
                                2'd2: crc_recv[23:16] <= rx_data;
                                2'd3: crc_recv[31:24] <= rx_data;
                            endcase
                            if (crc_idx == 2'd3) begin
                                crc_settle <= 2'd0;
                                state      <= S_VALIDATE_CRC; // Gelen şifre tamam, kontrole geç
                            end else begin
                                crc_idx <= crc_idx + 2'd1;
                                state   <= S_RECEIVE_PACKET;
                            end
                        end
                    endcase
                end

                S_VALIDATE_CRC: begin
                    if (crc_settle < 2'd2) begin
                        crc_settle <= crc_settle + 2'd1; // CRC lojik hat yerleşimi için 2 çevrim dur
                    end else begin
                        crc_settle <= 2'd0;
                        if (crc_computed == crc_recv) begin // Eşleşme tamsa RAM yazımına dallan
                            ld_addr  <= pkt_addr;
                            data_idx <= 16'd0;
                            state    <= S_WRITE_BRAM;
                        end else begin
                            if (!tx_busy) begin
                                tx_data  <= RESP_NAK; // Şifre hatalıysa NAK yükle
                                tx_start <= 1'b1;     // Bilgisayara hata raporu fırlat
                                state    <= S_NEXT_PACKET;
                            end
                        end
                    end
                end

                S_WRITE_BRAM: begin
                    if (data_idx < pkt_size) begin
                        ld_we    <= 1'b1; // RAM arayüzü yazma yetkisi (Write Enable)
                        ld_wstrb <= 1'b1; // Bayt seçim sinyali
                        ld_addr  <= pkt_addr + {16'd0, data_idx};
                        ld_wdata <= data_buf[data_idx];
                        if (ld_ack)
                            data_idx <= data_idx + 16'd1; // RAM'den onay geldikçe sayacı artır
                    end else begin
                        if (!tx_busy) begin
                            tx_data  <= RESP_ACK; // Tüm paket yazımı bittiyse ACK yükle
                            tx_start <= 1'b1;     // Bilgisayara başarı raporu fırlat
                            state    <= S_NEXT_PACKET;
                        end
                    end
                end

                S_NEXT_PACKET: begin
                    if (!tx_busy) begin
                        if (!rx_empty) begin
                            rx_rd <= 1'b1;
                            state <= S_NEXT_PACKET_WAIT;
                        end
                    end
                end

                S_NEXT_PACKET_WAIT: begin
                    if (rx_data == SYNC_B0)
                        state <= S_WAIT_HEADER; // Yeni paket geliyorsa döngüyü başa sar
                    else
                        state <= S_NEXT_PACKET; 
                end

                S_LOAD_DONE: begin
                    loader_active <= 1'b0;
                    entry_pc      <= 32'h0000_0000; // Başlangıç adresini esnek parametreye bağla
                    entry_pc_load <= 1'b1;          // Yeni PC adresini cpu_control'e kilitle
                    state         <= S_RELEASE_CPU_RESET;
                end

                S_RELEASE_CPU_RESET: begin
                    loader_done   <= 1'b1;          // Yükleme tam bitti sinyalini ateşle
                    loader_active <= 1'b0;
                    state         <= S_IDLE;        // Sistemi ilk konumuna güvenle çek
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule