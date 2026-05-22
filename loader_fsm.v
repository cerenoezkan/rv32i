// loader_fsm.v
// UART tabanlı program yükleyici — ana durum makinesi.
//
// Paket formatı (host_uploader.py ile birebir uyumlu):
//   [0xAA][0x55] [ADDR:4 LE] [SIZE:2 LE] [DATA...] [CRC32:4 LE]
//   Oturum sonu: [0xAA][0x56]
//
// DÜZELTME: S_WRITE_BRAM state'inde state <= S_NEXT_PACKET,
//           !tx_busy kontrolünün DIŞINA çıkmıştı → ACK hiç gönderilmiyordu.
//           Düzeltildi: state geçişi if(!tx_busy) bloğunun içine alındı.

module loader_fsm #(
    parameter integer MAX_PKT_SIZE = 256
) (
    input  wire        clk,
    input  wire        rst,

    // UART RX FIFO arayüzü
    input  wire        rx_empty,
    input  wire [7:0]  rx_data,
    output reg         rx_rd,

    // UART TX arayüzü
    output reg  [7:0]  tx_data,
    output reg         tx_start,
    input  wire        tx_busy,

    // BRAM loader portu
    output reg         ld_we,
    output reg  [31:0] ld_addr,
    output reg  [ 7:0] ld_wdata,
    output reg         ld_wstrb,
    input  wire        ld_ack,

    // CPU kontrol sinyalleri
    output reg         loader_active,
    output reg         loader_done,
    output reg  [31:0] entry_pc,
    output reg         entry_pc_load,

    input  wire        force_reload   // btnC: yeniden yükleme isteği
);

    // Senkron byte'lar
    localparam [7:0] SYNC_B0  = 8'hAA;
    localparam [7:0] SYNC_B1  = 8'h55;
    localparam [7:0] SYNC_END = 8'h56;
    localparam [7:0] RESP_ACK = 8'h06;
    localparam [7:0] RESP_NAK = 8'h15;

    // FSM state'leri
    localparam [3:0]
        S_IDLE              = 4'd0,
        S_WAIT_HEADER       = 4'd1,
        S_RECEIVE_PACKET    = 4'd2,
        S_VALIDATE_CRC      = 4'd3,
        S_WRITE_BRAM        = 4'd4,
        S_NEXT_PACKET       = 4'd5,
        S_LOAD_DONE         = 4'd6,
        S_RELEASE_CPU_RESET = 4'd7;

    // Alım fazları
    localparam [2:0]
        R_ADDR = 3'd0,
        R_SIZE = 3'd1,
        R_DATA = 3'd2,
        R_CRC  = 3'd3;

    reg [3:0]  state;
    reg [2:0]  recv_phase;
    reg [31:0] pkt_addr;
    reg [15:0] pkt_size;
    reg [15:0] data_idx;
    reg [1:0]  hdr_idx;
    reg [1:0]  crc_idx;
    reg [31:0] crc_recv;

    reg [7:0] data_buf [0:MAX_PKT_SIZE-1];

    // CRC modülü sinyalleri
    reg        crc_init;
    reg        crc_feed;
    reg [7:0]  crc_byte_in;
    reg [1:0]  crc_settle;  // CRC hesabının stabilize olması için 2-cycle bekleme
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
            state           <= S_IDLE;
            recv_phase      <= R_ADDR;
            rx_rd           <= 1'b0;
            ld_we           <= 1'b0;
            ld_addr         <= 32'd0;
            ld_wdata        <= 8'd0;
            ld_wstrb        <= 1'b0;
            loader_active   <= 1'b0;
            loader_done     <= 1'b0;
            entry_pc        <= 32'h0000_0000;
            entry_pc_load   <= 1'b0;
            tx_data         <= 8'd0;
            tx_start        <= 1'b0;
            pkt_addr        <= 32'd0;
            pkt_size        <= 16'd0;
            data_idx        <= 16'd0;
            hdr_idx         <= 2'd0;
            crc_idx         <= 2'd0;
            crc_recv        <= 32'd0;
            crc_init        <= 1'b0;
            crc_feed        <= 1'b0;
            crc_byte_in     <= 8'd0;
            crc_settle      <= 2'd0;
        end else begin
            // Varsayılan: pulse sinyallerini sıfırla
            rx_rd           <= 1'b0;
            ld_we           <= 1'b0;
            ld_wstrb        <= 1'b0;
            tx_start        <= 1'b0;
            entry_pc_load   <= 1'b0;
            crc_init        <= 1'b0;
            crc_feed        <= 1'b0;

            // Kullanıcı yeniden yükleme isteği
            if (force_reload) begin
                loader_done   <= 1'b0;
                loader_active <= 1'b1;
                state         <= S_IDLE;
            end

            case (state)

                // ----------------------------------------------------------
                S_IDLE: begin
                    loader_active <= !loader_done;
                    if (!rx_empty && rx_data == SYNC_B0) begin
                        rx_rd <= 1'b1;
                        state <= S_WAIT_HEADER;
                    end
                end

                // ----------------------------------------------------------
                S_WAIT_HEADER: begin
                    if (!rx_empty) begin
                        rx_rd <= 1'b1;
                        if (rx_data == SYNC_B1) begin
                            // Yeni paket başlıyor
                            pkt_addr   <= 32'd0;
                            pkt_size   <= 16'd0;
                            hdr_idx    <= 2'd0;
                            data_idx   <= 16'd0;
                            crc_idx    <= 2'd0;
                            recv_phase <= R_ADDR;
                            crc_init   <= 1'b1;    // CRC'yi sıfırla
                            state      <= S_RECEIVE_PACKET;
                        end else if (rx_data == SYNC_END) begin
                            state <= S_LOAD_DONE;
                        end else begin
                            state <= S_IDLE;       // geçersiz byte, yeniden bekle
                        end
                    end
                end

                // ----------------------------------------------------------
                S_RECEIVE_PACKET: begin
                    if (!rx_empty) begin
                        rx_rd       <= 1'b1;
                        crc_byte_in <= rx_data;

                        // CRC'ye ADDR + SIZE + DATA dahil, CRC kendisi dahil değil
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
                                    recv_phase <= R_SIZE;
                                end else
                                    hdr_idx <= hdr_idx + 2'd1;
                            end

                            R_SIZE: begin
                                case (hdr_idx)
                                    2'd0: pkt_size[ 7: 0] <= rx_data;
                                    2'd1: pkt_size[15: 8] <= rx_data;
                                endcase
                                if (hdr_idx == 2'd1) begin
                                    hdr_idx    <= 2'd0;
                                    data_idx   <= 16'd0;
                                    recv_phase <= R_DATA;
                                end else
                                    hdr_idx <= hdr_idx + 2'd1;
                            end

                            R_DATA: begin
                                if (pkt_size == 16'd0) begin
                                    recv_phase <= R_CRC;
                                end else begin
                                    data_buf[data_idx] <= rx_data;
                                    data_idx <= data_idx + 16'd1;
                                    if (data_idx + 16'd1 == pkt_size)
                                        recv_phase <= R_CRC;
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
                                    crc_settle <= 2'd0;  // sayacı sıfırla
                                    state <= S_VALIDATE_CRC;
                                end else
                                    crc_idx <= crc_idx + 2'd1;
                            end
                        endcase
                    end
                end

                // ----------------------------------------------------------
                // KRİTİK DÜZELTME: CRC hesabı senkron (crc32_byte pipeline).
                // Son byte feed'inin ardından crc_computed en az 2 cycle
                // sonra stabil olur. crc_settle sayacı 0→1→2 adımlarını
                // sayar; 2'ye ulaşınca karşılaştırma güvenlidir.
                S_VALIDATE_CRC: begin
                    if (crc_settle < 2'd2) begin
                        crc_settle <= crc_settle + 2'd1;
                    end else begin
                        crc_settle <= 2'd0;
                        if (crc_computed == crc_recv) begin
                            ld_addr  <= pkt_addr;
                            data_idx <= 16'd0;
                            state    <= S_WRITE_BRAM;
                        end else begin
                            // CRC hata: NAK gönder
                            if (!tx_busy) begin
                                tx_data  <= RESP_NAK;
                                tx_start <= 1'b1;
                                state    <= S_NEXT_PACKET;
                            end
                        end
                    end
                end

                // ----------------------------------------------------------
                // DÜZELTME: state <= S_NEXT_PACKET artık if(!tx_busy) İÇİNDE
                S_WRITE_BRAM: begin
                    if (data_idx < pkt_size) begin
                        ld_we    <= 1'b1;
                        ld_wstrb <= 1'b1;
                        ld_addr  <= pkt_addr + {16'd0, data_idx};
                        ld_wdata <= data_buf[data_idx];
                        if (ld_ack)
                            data_idx <= data_idx + 16'd1;
                    end else begin
                        // Tüm baytlar yazıldı, ACK gönder
                        if (!tx_busy) begin
                            tx_data  <= RESP_ACK;
                            tx_start <= 1'b1;
                            state    <= S_NEXT_PACKET;  // ← if içinde!
                        end
                    end
                end

                // ----------------------------------------------------------
                S_NEXT_PACKET: begin
                    // TX bitmesini bekle, sonra yeni 0xAA ara
                    if (!tx_busy) begin
                        if (!rx_empty) begin
                            if (rx_data == SYNC_B0) begin
                                rx_rd <= 1'b1;
                                state <= S_WAIT_HEADER;
                            end else begin
                                rx_rd <= 1'b1;  // istenmeyen byte'ı tüket
                            end
                        end
                    end
                end

                // ----------------------------------------------------------
                S_LOAD_DONE: begin
                    loader_active <= 1'b0;
                    entry_pc      <= 32'h0000_0000;  // PC = 0x0
                    entry_pc_load <= 1'b1;
                    state         <= S_RELEASE_CPU_RESET;
                end

                // ----------------------------------------------------------
                S_RELEASE_CPU_RESET: begin
                    loader_done   <= 1'b1;
                    loader_active <= 1'b0;
                    state         <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule