module memory(
    input clk,
    input [31:0] addr,
    output reg [31:0] data
);

reg [31:0] mem [0:1023];

initial begin
    $readmemh("output_mem.hex", mem);
end

always @(posedge clk) begin
    data <= mem[addr[11:2]];
end

endmodule