// heartbeat.v — blink LED at ~1.5 Hz from 100 MHz clock
// LED = counter bit 26: toggles every 2^26 cycles = 0.67 s half-period

module heartbeat (
    input  wire clk,
    input  wire rst_n,
    output wire led
);
    reg [26:0] cnt;

    always @(posedge clk) begin
        if (!rst_n)
            cnt <= 27'd0;
        else
            cnt <= cnt + 1'b1;
    end

    assign led = cnt[26];

endmodule
