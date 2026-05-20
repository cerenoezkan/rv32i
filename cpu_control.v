// cpu_control.v
// ---------------------------------------------------------------------------
// CPU reset ve program başlangıç adresi kontrolü.
// Loader bitene kadar cpu_resetn = 0 (CPU durur).
// ---------------------------------------------------------------------------

module cpu_control #(
    parameter [31:0] DEFAULT_ENTRY_PC = 32'h0000_0000
) (
    input  wire        clk,
    input  wire        rst,             // senkron, aktif-yüksek

    input  wire        btnC,            // kullanıcı reset (aktif-yüksek)
    input  wire        loader_done,     // loader programı bitirdi
    input  wire        loader_active, // loader şu an çalışıyor
    input  wire [31:0] entry_pc_in,
    input  wire        entry_pc_load,

    output reg         cpu_resetn,      // aktif-düşük reset
    output reg  [31:0] entry_pc,
    output wire        force_loader      // btnC uzun basış yerine: yeniden yükle
);

    // Güç-açılışı senkron reset sayacı
    reg [3:0] pwr_cnt;
    reg       pwr_done;

    always @(posedge clk) begin
        if (rst) begin
            pwr_cnt  <= 4'd0;
            pwr_done <= 1'b0;
        end else if (!pwr_done) begin
            if (pwr_cnt == 4'hF) begin
                pwr_done <= 1'b1;
            end else begin
                pwr_cnt <= pwr_cnt + 4'd1;
            end
        end
    end

  always @(posedge clk) begin
        if (rst) begin
            cpu_resetn    <= 1'b0;
            entry_pc      <= DEFAULT_ENTRY_PC;
        end else begin
            if (entry_pc_load)
                entry_pc <= entry_pc_in;

            // CPU ancak: güç-açılışı bitti, loader bitti, buton basılı değil
            if (pwr_done && loader_done && !btnC && !loader_active)
                cpu_resetn <= 1'b1;
            else
                cpu_resetn <= 1'b0;
        end
    end

    // btnC basılı tutulunca yeniden yükleme moduna geçiş isteği
    assign force_loader = btnC && pwr_done;

endmodule
