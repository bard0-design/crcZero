// ==============================================================
// crcZero -- AXI4-Stream CRC Wrapper (SystemVerilog)
// https://github.com/bard0-design/crcZero
//
// Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
// License    : MIT
//
// Algorithm  : CRC-32/ISO-HDLC
// Wrapper    : crc_32_iso_hdlc_d8_axis
// CRC core   : crc_32_iso_hdlc_d8
// Data width : 8 bits
// Generated  : 2026-03-06T06:17:39Z
//
// Compile both files together:
//   iverilog -g2012 crc_32_iso_hdlc_d8.sv crc_32_iso_hdlc_d8_axis.sv ...
// ==============================================================

module crc_32_iso_hdlc_d8_axis (
    input  logic        clk,
    input  logic        rst_n,       // active-low synchronous reset
    // AXI4-Stream slave (data in)
    input  logic [7:0]  s_axis_tdata,
    input  logic        s_axis_tvalid,
    output logic        s_axis_tready,
    input  logic        s_axis_tlast,
    // AXI4-Stream master (running CRC out, one beat per input beat)
    output logic [31:0] m_axis_tdata,
    output logic        m_axis_tvalid,
    output logic        m_axis_tlast,
    input  logic        m_axis_tready
);

    localparam logic [31:0] HW_INIT = 32'hFFFFFFFF;
    localparam logic [31:0] XOR_OUT = 32'hFFFFFFFF;

    logic [31:0] crc_reg;
    logic [31:0] crc_next;

    // Combinatorial CRC core (generated separately)
    crc_32_iso_hdlc_d8 u_crc_core (
        .data_in (s_axis_tdata),
        .crc_in  (crc_reg),
        .crc_out (crc_next)
    );

    assign s_axis_tready = !m_axis_tvalid || m_axis_tready;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            crc_reg       <= HW_INIT;
            m_axis_tvalid <= 1'b0;
            m_axis_tlast  <= 1'b0;
            m_axis_tdata  <= 32'h0;
        end else begin
            if (s_axis_tready) begin
                if (s_axis_tvalid) begin
                    m_axis_tvalid <= 1'b1;
                    m_axis_tlast  <= s_axis_tlast;
                    m_axis_tdata  <= s_axis_tlast ? crc_next ^ XOR_OUT : crc_next;
                    crc_reg       <= s_axis_tlast ? HW_INIT : crc_next;
                end else begin
                    m_axis_tvalid <= 1'b0;
                    m_axis_tlast  <= 1'b0;
                end
            end
        end
    end

endmodule : crc_32_iso_hdlc_d8_axis
