// uart_rx.v
// ---------------------------------------------------------------------------
// 8N1 UART receiver — senkron, tek clock domain.
// CLK_FREQ / BAUD_RATE baud bölücüsü ile örnekleme.
// Alınan baytlar 8-bit x 256 senkron FIFO'ya yazılır.
// ---------------------------------------------------------------------------

module uart_rx #(
    parameter integer CLK_FREQ  = 100_000_000,
    parameter integer BAUD_RATE = 115200,
    parameter integer FIFO_DEPTH = 256
) (
    input  wire       clk,
    input  wire       rst,          // senkron, aktif-yüksek
    input  wire       rxd,
    output wire       fifo_empty,
    output wire       fifo_full,
    output wire [7:0] fifo_dout,
    output wire       fifo_rd_en
);

    localparam integer BAUD_DIV = CLK_FREQ / BAUD_RATE;
    localparam integer BAUD_DIV_W = $clog2(BAUD_DIV + 1);

    // -----------------------------------------------------------------------
    // UART RX FSM
    // -----------------------------------------------------------------------
    localparam [1:0]
        RX_IDLE  = 2'd0,
        RX_START = 2'd1,
        RX_DATA  = 2'd2,
        RX_STOP  = 2'd3;

    reg [1:0] rx_state;
    reg [BAUD_DIV_W-1:0] baud_cnt;
    reg [3:0] bit_idx;
    reg [7:0] shift_reg;
    reg byte_ready;
    reg [7:0] byte_out;

    wire rxd_sync;
    reg rxd_meta, rxd_sync_r;

    always @(posedge clk) begin
        if (rst) begin
            rxd_meta   <= 1'b1;
            rxd_sync_r <= 1'b1;
        end else begin
            rxd_meta   <= rxd;
            rxd_sync_r <= rxd_meta;
        end
    end
    assign rxd_sync = rxd_sync_r;

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
                    if (!rxd_sync) begin
                        rx_state <= RX_START;
                        baud_cnt <= BAUD_DIV[BAUD_DIV_W-1:0] >> 1; // orta-bit örnekleme
                    end
                end
                RX_START: begin
                    if (baud_cnt == {BAUD_DIV_W{1'b0}}) begin
                        rx_state <= RX_DATA;
                        baud_cnt <= BAUD_DIV[BAUD_DIV_W-1:0] - 1;
                        bit_idx  <= 4'd0;
                        shift_reg <= 8'h00;
                    end else begin
                        baud_cnt <= baud_cnt - 1'b1;
                    end
                end
                RX_DATA: begin
                    if (baud_cnt == {BAUD_DIV_W{1'b0}}) begin
                        shift_reg <= {rxd_sync, shift_reg[7:1]};
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
                        byte_out   <= shift_reg;
                        byte_ready <= 1'b1;
                        rx_state   <= RX_IDLE;
                    end else begin
                        baud_cnt <= baud_cnt - 1'b1;
                    end
                end
                default: rx_state <= RX_IDLE;
            endcase
        end
    end

    // -----------------------------------------------------------------------
    // Senkron FIFO (8-bit)
    // -----------------------------------------------------------------------
    reg [7:0] fifo_mem [0:FIFO_DEPTH-1];
    reg [8:0] wr_ptr;   // 1 ekstra bit — dolu/boş ayrımı
    reg [8:0] rd_ptr;

    wire fifo_push = byte_ready && !fifo_full;
    wire fifo_pop  = fifo_rd_en && !fifo_empty;

    assign fifo_empty = (wr_ptr == rd_ptr);
    assign fifo_full  = (wr_ptr[7:0] == rd_ptr[7:0]) && (wr_ptr[8] != rd_ptr[8]);

    always @(posedge clk) begin
        if (rst) begin
            wr_ptr <= 9'd0;
            rd_ptr <= 9'd0;
        end else begin
            if (fifo_push) begin
                fifo_mem[wr_ptr[7:0]] <= byte_out;
                wr_ptr <= wr_ptr + 9'd1;
            end
            if (fifo_pop) begin
                rd_ptr <= rd_ptr + 9'd1;
            end
        end
    end

    assign fifo_dout = fifo_mem[rd_ptr[7:0]];

endmodule
