# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Structural tests for the SystemVerilog AXI4-Stream wrapper renderer."""

from __future__ import annotations

import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations
from crczero.renderers.axi_stream_sv import AxiStreamSVRenderer


def _generate(name, data_width=8):
    alg = CATALOG[name]
    eqs = derive_equations(alg, data_width)
    return AxiStreamSVRenderer().render(eqs, alg, data_width)


def test_module_name():
    code = _generate("CRC-32/ISO-HDLC")
    assert "module crc_32_iso_hdlc_d8_axis (" in code
    assert "endmodule : crc_32_iso_hdlc_d8_axis" in code


def test_logic_type_ports():
    code = _generate("CRC-32/ISO-HDLC")
    assert "input  logic        clk" in code
    assert "input  logic        rst_n" in code
    assert "input  logic [7:0]  s_axis_tdata" in code
    assert "output logic [31:0] m_axis_tdata" in code


def test_always_ff():
    code = _generate("CRC-32/ISO-HDLC")
    assert "always_ff @(posedge clk)" in code


def test_pipeline_register():
    code = _generate("CRC-32/ISO-HDLC")
    assert "if (s_axis_tready)" in code
    assert "if (s_axis_tvalid)" in code


def test_core_instantiation():
    code = _generate("CRC-32/ISO-HDLC")
    assert "crc_32_iso_hdlc_d8 u_crc_core" in code


def test_tready_assign():
    code = _generate("CRC-32/ISO-HDLC")
    assert "assign s_axis_tready = !m_axis_tvalid || m_axis_tready" in code


def test_tlast_registered():
    code = _generate("CRC-32/ISO-HDLC")
    assert "m_axis_tlast  <= s_axis_tlast" in code
    assert "assign m_axis_tlast" not in code


def test_backpressure_logic():
    code = _generate("CRC-32/ISO-HDLC")
    assert "!m_axis_tvalid || m_axis_tready" in code


@pytest.mark.parametrize("name", ["CRC-8/SMBUS", "CRC-16/ARC", "CRC-32/ISO-HDLC"])
def test_multiple_algorithms(name):
    code = _generate(name)
    assert "always_ff" in code
    assert "s_axis_tready = !m_axis_tvalid || m_axis_tready" in code
