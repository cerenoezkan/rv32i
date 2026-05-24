module cpu_control #(
    parameter [31:0] DEFAULT_ENTRY_PC = 32'h0000_0000
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        sys_rst_n,
    input  wire        loader_done,
    input  wire        loader_active,
    input  wire [31:0] entry_pc_in,
    input  wire        entry_pc_load,
    output reg         cpu_resetn,
    output reg  [31:0] entry_pc,
    output wire        force_loader
);
    reg [3:0] pwr_cnt;
    reg       pwr_done;

    always @(posedge clk) begin
        if (rst) begin
            pwr_cnt  <= 4'd0;
            pwr_done <= 1'b0;
        end else if (!pwr_done) begin
            if (pwr_cnt == 4'hF)
                pwr_done <= 1'b1;
            else
                pwr_cnt <= pwr_cnt + 4'd1;
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            cpu_resetn <= 1'b0;
            entry_pc   <= DEFAULT_ENTRY_PC;
        end else begin
            if (entry_pc_load)
                entry_pc <= entry_pc_in;
            if (pwr_done && loader_done && sys_rst_n && !loader_active)
                cpu_resetn <= 1'b1;
            else
                cpu_resetn <= 1'b0;
        end
    end

    assign force_loader = !sys_rst_n && pwr_done;

endmodule