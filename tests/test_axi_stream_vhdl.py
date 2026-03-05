"""Structural tests for the VHDL-1993 AXI4-Stream wrapper renderer."""

from __future__ import annotations

import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations
from crczero.renderers.axi_stream_vhdl import AxiStreamVhdlRenderer


def _generate(name, data_width=8):
    alg = CATALOG[name]
    eqs = derive_equations(alg, data_width)
    return AxiStreamVhdlRenderer().render(eqs, alg, data_width)


def test_library_clause():
    code = _generate("CRC-32/ISO-HDLC")
    assert "library ieee;" in code
    assert "use ieee.std_logic_1164.all;" in code


def test_entity_and_end():
    code = _generate("CRC-32/ISO-HDLC")
    assert "entity crc_32_iso_hdlc_d8_axis is" in code
    assert "end crc_32_iso_hdlc_d8_axis;" in code


def test_architecture():
    code = _generate("CRC-32/ISO-HDLC")
    assert "architecture rtl of crc_32_iso_hdlc_d8_axis is" in code
    assert "end rtl;" in code


def test_clock_and_reset_ports():
    code = _generate("CRC-32/ISO-HDLC")
    assert "clk           : in  std_logic" in code
    assert "rst_n         : in  std_logic" in code


def test_slave_ports():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "s_axis_tdata  : in  std_logic_vector(7 downto 0)" in code
    assert "s_axis_tvalid : in  std_logic" in code
    assert "s_axis_tready : out std_logic" in code
    assert "s_axis_tlast  : in  std_logic" in code


def test_master_ports():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "m_axis_tdata  : out std_logic_vector(31 downto 0)" in code
    assert "m_axis_tvalid : out std_logic" in code
    assert "m_axis_tlast  : out std_logic" in code
    assert "m_axis_tready : in  std_logic" in code


def test_pipeline_register():
    code = _generate("CRC-32/ISO-HDLC")
    assert "if s_tready_i = '1' then" in code
    assert "if s_axis_tvalid = '1' then" in code


def test_direct_entity_instantiation():
    code = _generate("CRC-32/ISO-HDLC")
    assert "entity work.crc_32_iso_hdlc_d8(rtl)" in code


def test_port_map():
    code = _generate("CRC-32/ISO-HDLC")
    assert "data_in => s_axis_tdata" in code
    assert "crc_in  => crc_reg" in code
    assert "crc_out => crc_next" in code


def test_tready_concurrent():
    code = _generate("CRC-32/ISO-HDLC")
    assert "s_tready_i    <= '1' when m_tvalid_r = '0' or m_axis_tready = '1' else '0'" in code
    assert "s_axis_tready <= s_tready_i" in code


def test_tlast_registered():
    code = _generate("CRC-32/ISO-HDLC")
    assert "m_tlast_r  <= s_axis_tlast" in code
    assert "m_axis_tlast  <= m_tlast_r" in code


def test_hw_init_constant():
    code = _generate("CRC-32/ISO-HDLC")
    assert "HW_INIT" in code
    assert "FFFFFFFF" in code.upper()


def test_xor_out_constant():
    code = _generate("CRC-32/ISO-HDLC")
    assert "XOR_OUT" in code


def test_no_xor_out_when_zero():
    code = _generate("CRC-8/SMBUS")
    assert "XOR_OUT" not in code


def test_synchronous_reset():
    code = _generate("CRC-32/ISO-HDLC")
    assert "rising_edge(clk)" in code
    assert "rst_n = '0'" in code


def test_backpressure_logic():
    code = _generate("CRC-32/ISO-HDLC")
    assert "m_tvalid_r = '0' or m_axis_tready = '1'" in code


def test_crc_reg_reset_after_packet():
    code = _generate("CRC-32/ISO-HDLC")
    assert "crc_reg   <= HW_INIT" in code


def test_ends_with_newline():
    code = _generate("CRC-32/ISO-HDLC")
    assert code.endswith("\n")


@pytest.mark.parametrize("name", ["CRC-8/SMBUS", "CRC-16/ARC", "CRC-32/ISO-HDLC", "CRC-64/GO-ISO"])
def test_multiple_algorithms(name):
    code = _generate(name)
    assert "m_tvalid_r = '0' or m_axis_tready = '1'" in code
    assert "rising_edge(clk)" in code
