module top (
    input  wire       sys_clk,
    input  wire       sys_rst_n,
    input  wire       uart_rx,
    output wire       uart_tx,
  output wire [5:0] led
);

    localparam CLK_FREQ  = 27_000_000;
    localparam BAUD_RATE = 115200;

    wire sys_rst = ~sys_rst_n;

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

    wire        mem_valid, mem_instr;
    reg         mem_ready;
    wire [31:0] mem_addr, mem_wdata;
    reg  [31:0] mem_rdata;
    wire [ 3:0] mem_wstrb;

    picorv32 #(
        .STACKADDR     (32'h0000_0FFC),
        .PROGADDR_RESET(32'h0000_0000),
        .ENABLE_MUL    (0),
        .ENABLE_DIV    (0),
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

    wire bram_sel = (mem_addr[31:12] == 20'h00000);
    wire led_sel  = (mem_addr == 32'h0000_2000);
    wire btn_sel  = (mem_addr == 32'h0000_2004);  // buton MMIO

  reg [5:0] led_reg;
    assign led = ~led_reg;

    always @(*) begin
        if (bram_sel)
            mem_rdata = bram_rdata;
        else if (led_sel)
            mem_rdata = {26'h0, led_reg};
        else if (btn_sel)
           mem_rdata = {31'h0, sys_rst_n};  // bırakılı=1, basılı=0 // basılı=1, bırakılı=0  // bırakılı=1, basılı=0
        else
            mem_rdata = 32'h00000013;
    end

    always @(posedge sys_clk) begin
        mem_ready <= 1'b0;
        if (sys_rst) begin
            led_reg <= 3'b000;
        end else if (mem_valid) begin
            if (bram_sel) begin
                mem_ready <= bram_ready;
            end else begin
                if (led_sel && mem_wstrb != 4'b0000)
                    led_reg <= mem_wdata[5:0];  // 3 bit yerine 6 bit
                mem_ready <= 1'b1;
            end
        end
    end

endmodule