// uart_rx.v
// 8N1 UART alıcı — senkron, tek clock domain.
// Tang Nano 9K: 27 MHz sistem clock
// 115200 baud → BAUD_DIV = 27_000_000 / 115200 = 234
// Alınan baytlar 256 bayt senkron FIFO'ya yazılır.

module uart_rx #(
    parameter integer CLK_FREQ   = 27_000_000,
    parameter integer BAUD_RATE  = 115200,
    parameter integer FIFO_DEPTH = 512   // DÜZELTME: 256→512 (büyük paket taşma koruması)
) (
    input  wire       clk,
    input  wire       rst,         // senkron, aktif-yüksek
    input  wire       rxd,
    output wire       fifo_empty,
    output wire       fifo_full,
    output wire [7:0] fifo_dout,
    input  wire       fifo_rd_en  // DÜZELTME: input olmalı (loader FSM okur)
);

    localparam integer BAUD_DIV   = CLK_FREQ / BAUD_RATE;       // 234
    localparam integer BAUD_DIV_W = $clog2(BAUD_DIV + 1);       // 8

    // -----------------------------------------------------------------------
    // 2-FF senkronizasyon (metastabilite önleme)
    // -----------------------------------------------------------------------
    reg rxd_meta, rxd_sync;
    always @(posedge clk) begin
        if (rst) begin
            rxd_meta <= 1'b1;
            rxd_sync <= 1'b1;
        end else begin
            rxd_meta <= rxd;
            rxd_sync <= rxd_meta;
        end
    end

    // -----------------------------------------------------------------------
    // UART RX FSM
    // -----------------------------------------------------------------------
    localparam [1:0]
        RX_IDLE  = 2'd0,
        RX_START = 2'd1,
        RX_DATA  = 2'd2,
        RX_STOP  = 2'd3;

    reg [1:0]            rx_state;
    reg [BAUD_DIV_W-1:0] baud_cnt;
    reg [3:0]            bit_idx;
    reg [7:0]            shift_reg;
    reg                  byte_ready;
    reg [7:0]            byte_out;

    always @(posedge clk) begin
        if (rst) begin
            rx_state   <= RX_IDLE;
            baud_cnt   <= {BAUD_DIV_W{1'b0}};
            bit_idx    <= 4'd0;
            shift_reg  <= 8'h00;
            byte_ready <= 1'b0;
            byte_out   <= 8'h00;
        end else begin
            byte_ready <= 1'b0;

            case (rx_state)

                RX_IDLE: begin
                    if (!rxd_sync) begin                         // start bit kenarı
                        baud_cnt <= (BAUD_DIV[BAUD_DIV_W-1:0] >> 1); // orta noktaya atla
                        rx_state <= RX_START;
                    end
                end

                RX_START: begin
                    if (baud_cnt == {BAUD_DIV_W{1'b0}}) begin
                        // Start bit ortasında — hâlâ 0 mı kontrol et
                        if (!rxd_sync) begin
                            baud_cnt  <= BAUD_DIV[BAUD_DIV_W-1:0] - 1;
                            bit_idx   <= 4'd0;
                            shift_reg <= 8'h00;
                            rx_state  <= RX_DATA;
                        end else begin
                            rx_state <= RX_IDLE;  // gürültü, iptal
                        end
                    end else begin
                        baud_cnt <= baud_cnt - 1'b1;
                    end
                end

                RX_DATA: begin
                    if (baud_cnt == {BAUD_DIV_W{1'b0}}) begin
                        shift_reg <= {rxd_sync, shift_reg[7:1]};  // LSB önce
                        baud_cnt  <= BAUD_DIV[BAUD_DIV_W-1:0] - 1;
                        if (bit_idx == 4'd7) begin
                            rx_state <= RX_STOP;
                        end else begin
                            bit_idx <= bit_idx + 1'b1;
                        end
                    end else begin
                        baud_cnt <= baud_cnt - 1'b1;
                    end
                end

                RX_STOP: begin
                    if (baud_cnt == {BAUD_DIV_W{1'b0}}) begin
                        if (rxd_sync) begin          // geçerli stop bit
                            byte_out   <= shift_reg;
                            byte_ready <= 1'b1;
                        end
                        rx_state <= RX_IDLE;
                    end else begin
                        baud_cnt <= baud_cnt - 1'b1;
                    end
                end

                default: rx_state <= RX_IDLE;
            endcase
        end
    end

    // -----------------------------------------------------------------------
    // Senkron FIFO — 8 bit x 512
    // DÜZELTME: 256→512 derinlik; ptr 9 bit → 10 bit (dolu/boş ayrımı için +1 bit)
    // -----------------------------------------------------------------------
    reg [7:0]  fifo_mem [0:FIFO_DEPTH-1];
    reg [9:0]  wr_ptr;   // 1 ekstra bit → dolu/boş ayrımı
    reg [9:0]  rd_ptr;

    wire fifo_push = byte_ready && !fifo_full;
    wire fifo_pop  = fifo_rd_en && !fifo_empty;

    assign fifo_empty = (wr_ptr == rd_ptr);
    assign fifo_full  = (wr_ptr[8:0] == rd_ptr[8:0]) &&
                        (wr_ptr[9]   != rd_ptr[9]);

    always @(posedge clk) begin
        if (rst) begin
            wr_ptr <= 10'd0;
            rd_ptr <= 10'd0;
        end else begin
            if (fifo_push) begin
                fifo_mem[wr_ptr[8:0]] <= byte_out;
                wr_ptr <= wr_ptr + 10'd1;
            end
            if (fifo_pop) begin
                rd_ptr <= rd_ptr + 10'd1;
            end
        end
    end

    assign fifo_dout = fifo_mem[rd_ptr[8:0]];

endmodule