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



    localparam [7:0] SYNC_B0  = 8'hAA;

    localparam [7:0] SYNC_B1  = 8'h55;

    localparam [7:0] SYNC_END = 8'h56;

    localparam [7:0] RESP_ACK = 8'h06;

    localparam [7:0] RESP_NAK = 8'h15;



    localparam [4:0]

        S_IDLE              = 5'd0,

        S_IDLE_WAIT         = 5'd1,   // rx_rd sonrası 1 cycle bekle

        S_WAIT_HEADER       = 5'd2,

        S_WAIT_HEADER_WAIT  = 5'd3,   // rx_rd sonrası 1 cycle bekle

        S_RECEIVE_PACKET    = 5'd4,

        S_RECEIVE_WAIT      = 5'd5,   // rx_rd sonrası 1 cycle bekle

        S_VALIDATE_CRC      = 5'd6,

        S_WRITE_BRAM        = 5'd7,

        S_NEXT_PACKET       = 5'd8,

        S_NEXT_PACKET_WAIT  = 5'd9,   // rx_rd sonrası 1 cycle bekle

        S_LOAD_DONE         = 5'd10,

        S_RELEASE_CPU_RESET = 5'd11;



    localparam [2:0]

        R_ADDR = 3'd0,

        R_SIZE = 3'd1,

        R_DATA = 3'd2,

        R_CRC  = 3'd3;



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

            // Pulse sinyallerini sıfırla

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



                // ----------------------------------------------------------

S_IDLE: begin
    loader_active <= !loader_done;
    if (!rx_empty) begin  // loader_done kontrolü kaldırıldı
        rx_rd <= 1'b1;
        state <= S_IDLE_WAIT;
    end
end

S_IDLE_WAIT: begin
    if (rx_data == SYNC_B0) begin
        loader_done <= 1'b0;  // yeni yükleme başlıyor
        state <= S_WAIT_HEADER;
    end else
        state <= S_IDLE;
end



                // ----------------------------------------------------------

                S_WAIT_HEADER: begin

                    if (!rx_empty) begin

                        rx_rd <= 1'b1;

                        state <= S_WAIT_HEADER_WAIT;

                    end

                end



                S_WAIT_HEADER_WAIT: begin

                    if (rx_data == SYNC_B1) begin

                        pkt_addr   <= 32'd0;

                        pkt_size   <= 16'd0;

                        hdr_idx    <= 2'd0;

                        data_idx   <= 16'd0;

                        crc_idx    <= 2'd0;

                        recv_phase <= R_ADDR;

                        crc_init   <= 1'b1;

                        state      <= S_RECEIVE_PACKET;

                    end else if (rx_data == SYNC_END) begin

                        state <= S_LOAD_DONE;

                    end else begin

                        state <= S_IDLE;

                    end

                end



                // ----------------------------------------------------------

                S_RECEIVE_PACKET: begin

                    if (!rx_empty) begin

                        rx_rd <= 1'b1;

                        state <= S_RECEIVE_WAIT;

                    end

                end



                S_RECEIVE_WAIT: begin

                    // rx_data stabil — işle

                    crc_byte_in <= rx_data;



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

                                recv_phase <= R_DATA;

                            end else

                                hdr_idx <= hdr_idx + 2'd1;

                            state <= S_RECEIVE_PACKET;

                        end



                        R_DATA: begin

                            if (pkt_size == 16'd0) begin

                                recv_phase <= R_CRC;

                                state      <= S_RECEIVE_PACKET;

                            end else begin

                                data_buf[data_idx] <= rx_data;

                                data_idx <= data_idx + 16'd1;

                                if (data_idx + 16'd1 == pkt_size)

                                    recv_phase <= R_CRC;

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

                                state      <= S_VALIDATE_CRC;

                            end else begin

                                crc_idx <= crc_idx + 2'd1;

                                state   <= S_RECEIVE_PACKET;

                            end

                        end

                    endcase

                end



                // ----------------------------------------------------------

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

                            if (!tx_busy) begin

                                tx_data  <= RESP_NAK;

                                tx_start <= 1'b1;

                                state    <= S_NEXT_PACKET;

                            end

                        end

                    end

                end



                // ----------------------------------------------------------

                S_WRITE_BRAM: begin

                    if (data_idx < pkt_size) begin

                        ld_we    <= 1'b1;

                        ld_wstrb <= 1'b1;

                        ld_addr  <= pkt_addr + {16'd0, data_idx};

                        ld_wdata <= data_buf[data_idx];

                        if (ld_ack)

                            data_idx <= data_idx + 16'd1;

                    end else begin

                        if (!tx_busy) begin

                            tx_data  <= RESP_ACK;

                            tx_start <= 1'b1;

                            state    <= S_NEXT_PACKET;

                        end

                    end

                end



                // ----------------------------------------------------------

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

                        state <= S_WAIT_HEADER;

                    else

                        state <= S_NEXT_PACKET;  // bekle

                end



                // ----------------------------------------------------------

                S_LOAD_DONE: begin

                    loader_active <= 1'b0;

                    entry_pc      <= 32'h0000_0000;

                    entry_pc_load <= 1'b1;

                    state         <= S_RELEASE_CPU_RESET;

                end



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