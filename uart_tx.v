// uart_tx.v
// ---------------------------------------------------------------------------
// 8N1 UART transmitter — debug / ACK / NAK yanıtları için.
// Tek bayt gönderim kuyruğu: tx_start pulse ile başlar.
// ---------------------------------------------------------------------------

module uart_tx #(
    parameter integer CLK_FREQ  = 100_000_000,
    parameter integer BAUD_RATE = 115200
) (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] tx_data,
    input  wire       tx_start,
    output reg        tx_busy,
    output reg        txd
);

    localparam integer BAUD_DIV = CLK_FREQ / BAUD_RATE;
    localparam integer BAUD_DIV_W = $clog2(BAUD_DIV + 1);

    localparam [1:0]
        TX_IDLE  = 2'd0,
        TX_START = 2'd1,
        TX_DATA  = 2'd2,
        TX_STOP  = 2'd3;

    reg [1:0] tx_state;
    reg [BAUD_DIV_W-1:0] baud_cnt;
    reg [3:0] bit_idx;
    reg [7:0] shreg;
    reg pending;

    always @(posedge clk) begin
        if (rst) begin
            tx_state <= TX_IDLE;
            baud_cnt <= {BAUD_DIV_W{1'b0}};
            bit_idx  <= 4'd0;
            shreg    <= 8'h00;
            txd      <= 1'b1;
            tx_busy  <= 1'b0;
            pending  <= 1'b0;
        end else begin
            if (tx_start && tx_state == TX_IDLE && !pending) begin
                shreg   <= tx_data;
                pending <= 1'b1;
            end

            case (tx_state)
                TX_IDLE: begin
                    txd     <= 1'b1;
                    tx_busy <= 1'b0;
                    if (pending) begin
                        tx_state <= TX_START;
                        tx_busy  <= 1'b1;
                        txd      <= 1'b0;
                        baud_cnt <= BAUD_DIV[BAUD_DIV_W-1:0] - 1;
                        pending  <= 1'b0;
                    end
                end
                TX_START: begin
                    if (baud_cnt == {BAUD_DIV_W{1'b0}}) begin
                        tx_state <= TX_DATA;
                        baud_cnt <= BAUD_DIV[BAUD_DIV_W-1:0] - 1;
                        bit_idx  <= 4'd0;
                        txd      <= shreg[0];
                    end else begin
                        baud_cnt <= baud_cnt - 1'b1;
                    end
                end
                TX_DATA: begin
                    if (baud_cnt == {BAUD_DIV_W{1'b0}}) begin
                        if (bit_idx == 4'd7) begin
                            tx_state <= TX_STOP;
                            txd      <= 1'b1;
                        end else begin
                            shreg    <= {1'b0, shreg[7:1]};
                            txd      <= shreg[1];
                            bit_idx  <= bit_idx + 1'b1;
                        end
                        baud_cnt <= BAUD_DIV[BAUD_DIV_W-1:0] - 1;
                    end else begin
                        baud_cnt <= baud_cnt - 1'b1;
                    end
                end
                TX_STOP: begin
                    txd <= 1'b1;
                    if (baud_cnt == {BAUD_DIV_W{1'b0}}) begin
                        tx_state <= TX_IDLE;
                    end else begin
                        baud_cnt <= baud_cnt - 1'b1;
                    end
                end
                default: tx_state <= TX_IDLE;
            endcase
        end
    end

endmodule
