// ==============================================================
// crcZero — Verilog-2001 Testbench
// https://github.com/bard0-design/crcZero
//
// Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
// License    : MIT
//
// Algorithm  : CRC-32/ISO-HDLC
// DUT module : crc_32_iso_hdlc_d8
// Data width : 8 bits
// Generated  : 2026-03-06T06:17:39Z
//
// Simulate with iverilog + vvp:
//   iverilog -o sim.vvp crc_32_iso_hdlc_d8.v crc_32_iso_hdlc_d8_tb.v
//   vvp sim.vvp
//   # VCD written to crc_32_iso_hdlc_d8_tb.vcd
// ==============================================================

`timescale 1ns/1ps

module crc_32_iso_hdlc_d8_tb;

    // DUT ports
    reg  [7:0]  data_in;
    reg  [31:0] crc_in;
    wire [31:0] crc_out;

    // DUT
    crc_32_iso_hdlc_d8 dut (
        .data_in (data_in),
        .crc_in  (crc_in),
        .crc_out (crc_out)
    );

    integer fail_count;
    integer i;

    // Test vectors: {crc_in, data_in, expected_crc_out}
    reg [31:0] tv_crc_in  [24:0];
    reg [7:0] tv_data_in [24:0];
    reg [31:0] tv_expected [24:0];

    initial begin
        // VCD waveform dump
        $dumpfile("crc_32_iso_hdlc_d8_tb.vcd");
        $dumpvars(0, crc_32_iso_hdlc_d8_tb);

        tv_crc_in[0]   = 32'hFFFFFFFF;
        tv_data_in[0]  = 8'h31;
        tv_expected[0] = 32'h7C231048;
        tv_crc_in[1]   = 32'h7C231048;
        tv_data_in[1]  = 8'h32;
        tv_expected[1] = 32'hB0ACBB32;
        tv_crc_in[2]   = 32'hB0ACBB32;
        tv_data_in[2]  = 8'h33;
        tv_expected[2] = 32'h77B79C2D;
        tv_crc_in[3]   = 32'h77B79C2D;
        tv_data_in[3]  = 8'h34;
        tv_expected[3] = 32'h641C1F5C;
        tv_crc_in[4]   = 32'h641C1F5C;
        tv_data_in[4]  = 8'h35;
        tv_expected[4] = 32'h340AC5E3;
        tv_crc_in[5]   = 32'h340AC5E3;
        tv_data_in[5]  = 8'h36;
        tv_expected[5] = 32'hF68D2C9E;
        tv_crc_in[6]   = 32'hF68D2C9E;
        tv_data_in[6]  = 8'h37;
        tv_expected[6] = 32'hAFFC9660;
        tv_crc_in[7]   = 32'hAFFC9660;
        tv_data_in[7]  = 8'h38;
        tv_expected[7] = 32'h651F2550;
        tv_crc_in[8]   = 32'h651F2550;
        tv_data_in[8]  = 8'h39;
        tv_expected[8] = 32'h340BC6D9;
        tv_crc_in[9]   = 32'hFFFFFFFF;
        tv_data_in[9]  = 8'h09;
        tv_expected[9] = 32'h5421A8D6;
        tv_crc_in[10]   = 32'h5421A8D6;
        tv_data_in[10]  = 8'hDA;
        tv_expected[10] = 32'h09E26D83;
        tv_crc_in[11]   = 32'h09E26D83;
        tv_data_in[11]  = 8'hF0;
        tv_expected[11] = 32'hC905C2EB;
        tv_crc_in[12]   = 32'hC905C2EB;
        tv_data_in[12]  = 8'hDA;
        tv_expected[12] = 32'h511705F8;
        tv_crc_in[13]   = 32'h511705F8;
        tv_data_in[13]  = 8'hC1;
        tv_expected[13] = 32'h5F549F0D;
        tv_crc_in[14]   = 32'h5F549F0D;
        tv_data_in[14]  = 8'hEE;
        tv_expected[14] = 32'h395CE75D;
        tv_crc_in[15]   = 32'h395CE75D;
        tv_data_in[15]  = 8'hA9;
        tv_expected[15] = 32'hBAE96AE2;
        tv_crc_in[16]   = 32'hBAE96AE2;
        tv_data_in[16]  = 8'hCA;
        tv_expected[16] = 32'h350F4190;
        tv_crc_in[17]   = 32'h350F4190;
        tv_data_in[17]  = 8'hBA;
        tv_expected[17] = 32'hDB8EC697;
        tv_crc_in[18]   = 32'hDB8EC697;
        tv_data_in[18]  = 8'hD0;
        tv_expected[18] = 32'hE8635AF5;
        tv_crc_in[19]   = 32'hE8635AF5;
        tv_data_in[19]  = 8'hC3;
        tv_expected[19] = 32'hCF52F6C3;
        tv_crc_in[20]   = 32'hCF52F6C3;
        tv_data_in[20]  = 8'h89;
        tv_expected[20] = 32'h96C6FA78;
        tv_crc_in[21]   = 32'h96C6FA78;
        tv_data_in[21]  = 8'h8D;
        tv_expected[21] = 32'hCD41C069;
        tv_crc_in[22]   = 32'hCD41C069;
        tv_data_in[22]  = 8'h80;
        tv_expected[22] = 32'hD91B1B1C;
        tv_crc_in[23]   = 32'hD91B1B1C;
        tv_data_in[23]  = 8'h80;
        tv_expected[23] = 32'hF960C474;
        tv_crc_in[24]   = 32'hF960C474;
        tv_data_in[24]  = 8'h5A;
        tv_expected[24] = 32'hDC2F6D0B;

        fail_count = 0;

        for (i = 0; i < 25; i = i + 1) begin
            crc_in  = tv_crc_in[i];
            data_in = tv_data_in[i];
            #10;  // allow combinatorial logic to settle
            if (crc_out !== tv_expected[i]) begin
                $display("FAIL vector %0d: crc_in=%0h data_in=%0h", i, tv_crc_in[i], tv_data_in[i]);
                $display("  expected=%0h  got=%0h", tv_expected[i], crc_out);
                fail_count = fail_count + 1;
            end else begin
                $display("PASS vector %0d", i);
            end
        end

        if (fail_count == 0)
            $display("ALL 25 VECTORS PASSED (CRC-32/ISO-HDLC)");
        else
            $display("%0d / 25 VECTORS FAILED", fail_count);

        $finish;
    end

endmodule  // crc_32_iso_hdlc_d8_tb
