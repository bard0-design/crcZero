// ==============================================================
// crcZero — Verilog-2001 Testbench
// https://github.com/bard0-design/crcZero
//
// Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
// License    : MIT
//
// Algorithm  : CRC-32/ISO-HDLC
// DUT module : crc_32_iso_hdlc_d32
// Data width : 32 bits
// Generated  : 2026-03-06T06:17:39Z
//
// Simulate with iverilog + vvp:
//   iverilog -o sim.vvp crc_32_iso_hdlc_d32.v crc_32_iso_hdlc_d32_tb.v
//   vvp sim.vvp
//   # VCD written to crc_32_iso_hdlc_d32_tb.vcd
// ==============================================================

`timescale 1ns/1ps

module crc_32_iso_hdlc_d32_tb;

    // DUT ports
    reg  [31:0]  data_in;
    reg  [31:0] crc_in;
    wire [31:0] crc_out;

    // DUT
    crc_32_iso_hdlc_d32 dut (
        .data_in (data_in),
        .crc_in  (crc_in),
        .crc_out (crc_out)
    );

    integer fail_count;
    integer i;

    // Test vectors: {crc_in, data_in, expected_crc_out}
    reg [31:0] tv_crc_in  [18:0];
    reg [31:0] tv_data_in [18:0];
    reg [31:0] tv_expected [18:0];

    initial begin
        // VCD waveform dump
        $dumpfile("crc_32_iso_hdlc_d32_tb.vcd");
        $dumpvars(0, crc_32_iso_hdlc_d32_tb);

        tv_crc_in[0]   = 32'hFFFFFFFF;
        tv_data_in[0]  = 32'h34333231;
        tv_expected[0] = 32'h641C1F5C;
        tv_crc_in[1]   = 32'h641C1F5C;
        tv_data_in[1]  = 32'h38373635;
        tv_expected[1] = 32'h651F2550;
        tv_crc_in[2]   = 32'h651F2550;
        tv_data_in[2]  = 32'h00000039;
        tv_expected[2] = 32'h882AA7CB;
        tv_crc_in[3]   = 32'hFFFFFFFF;
        tv_data_in[3]  = 32'hDAF0DA09;
        tv_expected[3] = 32'h511705F8;
        tv_crc_in[4]   = 32'h511705F8;
        tv_data_in[4]  = 32'hCAA9EEC1;
        tv_expected[4] = 32'h350F4190;
        tv_crc_in[5]   = 32'h350F4190;
        tv_data_in[5]  = 32'h89C3D0BA;
        tv_expected[5] = 32'h96C6FA78;
        tv_crc_in[6]   = 32'h96C6FA78;
        tv_data_in[6]  = 32'h5A80808D;
        tv_expected[6] = 32'hDC2F6D0B;
        tv_crc_in[7]   = 32'hDC2F6D0B;
        tv_data_in[7]  = 32'hF945C7A1;
        tv_expected[7] = 32'h222F76BD;
        tv_crc_in[8]   = 32'h222F76BD;
        tv_data_in[8]  = 32'h43F2A2D2;
        tv_expected[8] = 32'hE7E69025;
        tv_crc_in[9]   = 32'hE7E69025;
        tv_data_in[9]  = 32'h5AC84F03;
        tv_expected[9] = 32'hBD5B44F2;
        tv_crc_in[10]   = 32'hBD5B44F2;
        tv_data_in[10]  = 32'hFDB75298;
        tv_expected[10] = 32'hC82735D5;
        tv_crc_in[11]   = 32'hC82735D5;
        tv_data_in[11]  = 32'hE2C6E7AA;
        tv_expected[11] = 32'h218F5AEF;
        tv_crc_in[12]   = 32'h218F5AEF;
        tv_data_in[12]  = 32'hEB2B7084;
        tv_expected[12] = 32'h6827E177;
        tv_crc_in[13]   = 32'h6827E177;
        tv_data_in[13]  = 32'h0562FFAA;
        tv_expected[13] = 32'h7C8B499B;
        tv_crc_in[14]   = 32'h7C8B499B;
        tv_data_in[14]  = 32'hF48E4E19;
        tv_expected[14] = 32'hDC0B9762;
        tv_crc_in[15]   = 32'hDC0B9762;
        tv_data_in[15]  = 32'h4516EFBE;
        tv_expected[15] = 32'h40DF7835;
        tv_crc_in[16]   = 32'h40DF7835;
        tv_data_in[16]  = 32'h9D467AE2;
        tv_expected[16] = 32'hE0E6CA74;
        tv_crc_in[17]   = 32'hE0E6CA74;
        tv_data_in[17]  = 32'h52C3E040;
        tv_expected[17] = 32'h870FAE87;
        tv_crc_in[18]   = 32'h870FAE87;
        tv_data_in[18]  = 32'hA812C039;
        tv_expected[18] = 32'hEB598EC6;

        fail_count = 0;

        for (i = 0; i < 19; i = i + 1) begin
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
            $display("ALL 19 VECTORS PASSED (CRC-32/ISO-HDLC)");
        else
            $display("%0d / 19 VECTORS FAILED", fail_count);

        $finish;
    end

endmodule  // crc_32_iso_hdlc_d32_tb
