module cpu_control #(
    parameter [31:0] DEFAULT_ENTRY_PC = 32'h0000_0000
) (
    input  wire        clk,             // 27 MHz Sistem Saati
    input  wire        rst,             // FPGA ana reset (aktif-yüksek)
    input  wire        sys_rst_n,       // Fiziksel reset butonu (aktif-alçak)
    input  wire        loader_done,     // "Yükleme hatasız bitti" sinyali
    input  wire        loader_active,   // "Şu an bilgisayardan kod yükleniyor" sinyali
    input  wire [31:0] entry_pc_in,     // Yükleyiciden gelen başlangıç adresi
    input  wire        entry_pc_load,   // Adresi yazma tetikleme sinyali
    output reg         cpu_resetn,      // PicoRV32 şalteri (0=CPU Donar, 1=CPU Koşar)
    output reg  [31:0] entry_pc,        // İşlemcinin program başlangıç adresi
    output wire        force_loader     // "Butona basıldı, yeni kod bekle" emri
);

    reg [3:0] pwr_cnt;  
    reg       pwr_done; 

    //Güvenli Güç Sayacı
    // Voltajın oturması için açılışta 15 çevrim bekler.
    always @(posedge clk) begin
        if (rst) begin
            pwr_cnt  <= 4'd0;
            pwr_done <= 1'b0;
        end else if (!pwr_done) begin
            if (pwr_cnt == 4'hF)
                pwr_done <= 1'b1; // Süre doldu, güç kararlı.
            else
                pwr_cnt <= pwr_cnt + 4'd1;
        end
    end

    // CPU Şalter Kontrolü (EMNİYET KİLİDİ)
    // Kod yüklenirken CPU'yu dondurur, yükleme bitince tazece uyanır.
    always @(posedge clk) begin
        if (rst) begin
            cpu_resetn <= 1'b0;                 // Reset anında CPU'yu kilitli tut.
            entry_pc   <= DEFAULT_ENTRY_PC;    // Başlangıç adresini varsayılan parametre değerine çek.
        end else begin
            if (entry_pc_load)
                entry_pc <= entry_pc_in;        // Yeni başlangıç adresini kaydet.

            // KILİT: Yükleme sürerken (!loader_active) CPU reset modunda (0) kalır.
            if (pwr_done && loader_done && sys_rst_n && !loader_active)
                cpu_resetn <= 1'b1; // Yükleme bitti ve güç tamsa şalteri kaldır, CPU çalışsın!
            else
                cpu_resetn <= 1'b0; // Tek bir şart bile bozulursa CPU'yu anında dondur.
        end
    end

    // Zorla Yükleme Hattı
    // Kullanıcı butona bastığı an Loader FSM'e yeni kod bekleme sinyali gönderir.
    assign force_loader = !sys_rst_n && pwr_done;

endmodule