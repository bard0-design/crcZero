"""Structural tests for the Verilog-2001 AXI4-Stream wrapper renderer."""

from __future__ import annotations

import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations
from crczero.renderers.axi_stream_verilog import AxiStreamVerilogRenderer


def _generate(name, data_width=8):
    alg  = CATALOG[name]
    eqs  = derive_equations(alg, data_width)
    return AxiStreamVerilogRenderer().render(eqs, alg, data_width)


def test_module_name():
    code = _generate("CRC-32/ISO-HDLC")
    assert "module crc_32_iso_hdlc_d8_axis (" in code
    assert "endmodule  // crc_32_iso_hdlc_d8_axis" in code


def test_clock_and_reset_ports():
    code = _generate("CRC-32/ISO-HDLC")
    assert "input  wire        clk" in code
    assert "input  wire        rst_n" in code


def test_slave_ports():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "input  wire [7:0]  s_axis_tdata" in code
    assert "input  wire        s_axis_tvalid" in code
    assert "output wire        s_axis_tready" in code
    assert "input  wire        s_axis_tlast" in code


def test_master_ports():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "output reg  [31:0] m_axis_tdata" in code
    assert "output reg         m_axis_tvalid" in code
    assert "output reg         m_axis_tlast" in code
    assert "input  wire        m_axis_tready" in code


def test_pipeline_register():
    code = _generate("CRC-32/ISO-HDLC")
    assert "if (s_axis_tready)" in code
    assert "if (s_axis_tvalid)" in code


def test_core_instantiation():
    code = _generate("CRC-32/ISO-HDLC")
    assert "crc_32_iso_hdlc_d8 u_crc_core" in code
    assert ".data_in (s_axis_tdata)" in code
    assert ".crc_in  (crc_reg)" in code
    assert ".crc_out (crc_next)" in code


def test_tready_assign():
    code = _generate("CRC-32/ISO-HDLC")
    assert "assign s_axis_tready = !m_axis_tvalid || m_axis_tready" in code


def test_tlast_registered():
    code = _generate("CRC-32/ISO-HDLC")
    assert "m_axis_tlast  <= s_axis_tlast" in code
    assert "assign m_axis_tlast" not in code


def test_hw_init_constant():
    code = _generate("CRC-32/ISO-HDLC")
    # CRC-32/ISO-HDLC: ref_in=True, init=0xFFFFFFFF → hw_init = 0xFFFFFFFF
    assert "HW_INIT" in code
    assert "FFFFFFFF" in code.upper()


def test_xor_out_constant():
    code = _generate("CRC-32/ISO-HDLC")
    # xor_out=0xFFFFFFFF
    assert "XOR_OUT" in code


def test_no_xor_out_when_zero():
    # CRC-8/SMBUS has xor_out=0x00
    code = _generate("CRC-8/SMBUS")
    assert "XOR_OUT" not in code


def test_active_low_reset():
    code = _generate("CRC-32/ISO-HDLC")
    assert "if (!rst_n)" in code


def test_posedge_clk():
    code = _generate("CRC-32/ISO-HDLC")
    assert "always @(posedge clk)" in code


def test_backpressure_logic():
    code = _generate("CRC-32/ISO-HDLC")
    # slave stalls when output occupied and downstream not ready
    assert "!m_axis_tvalid || m_axis_tready" in code


def test_crc_reg_reset_after_packet():
    code = _generate("CRC-32/ISO-HDLC")
    # crc_reg resets to HW_INIT on the tlast beat
    assert "HW_INIT : crc_next" in code


def test_slave_data_width_32():
    code = _generate("CRC-32/ISO-HDLC", data_width=32)
    assert "input  wire [31:0]  s_axis_tdata" in code


def test_ends_with_newline():
    code = _generate("CRC-32/ISO-HDLC")
    assert code.endswith("\n")


@pytest.mark.parametrize("name", ["CRC-8/SMBUS", "CRC-16/ARC", "CRC-32/ISO-HDLC", "CRC-64/GO-ISO"])
def test_multiple_algorithms(name):
    code = _generate(name)
    assert "s_axis_tready = !m_axis_tvalid || m_axis_tready" in code
    assert "m_axis_tlast  <= s_axis_tlast" in code
    assert "u_crc_core" in code
