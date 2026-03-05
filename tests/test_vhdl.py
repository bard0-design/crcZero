"""Structural tests for the VHDL-1993 renderer."""

import re
import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations
from crczero.renderers.vhdl import VhdlRenderer


def _generate(name, data_width=8):
    alg = CATALOG[name]
    eqs = derive_equations(alg, data_width)
    return VhdlRenderer().render(eqs, alg, data_width)


def test_library_use():
    code = _generate("CRC-32/ISO-HDLC")
    assert "library ieee;" in code
    assert "use ieee.std_logic_1164.all;" in code


def test_entity_vhdl93_style():
    """VHDL-1993: end uses name only, no 'entity' keyword after end."""
    code = _generate("CRC-32/ISO-HDLC")
    assert "entity crc_32_iso_hdlc_d8 is" in code
    assert "end crc_32_iso_hdlc_d8;" in code
    # Must NOT use VHDL-2008 'end entity' form
    assert "end entity" not in code


def test_architecture_vhdl93_style():
    """VHDL-1993: end uses architecture label only."""
    code = _generate("CRC-32/ISO-HDLC")
    assert "architecture rtl of crc_32_iso_hdlc_d8 is" in code
    assert "end rtl;" in code
    # Must NOT use 'end architecture' form
    assert "end architecture" not in code


def test_port_declarations():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "data_in : in  std_logic_vector(7 downto 0)" in code
    assert "crc_in  : in  std_logic_vector(31 downto 0)" in code
    assert "crc_out : out std_logic_vector(31 downto 0)" in code


def test_vhdl_array_index_style():
    """VHDL uses parentheses for array indexing, not brackets."""
    code = _generate("CRC-8/SMBUS")
    assert "crc_out(0) <=" in code
    assert "crc_out[0]" not in code


def test_xor_keyword_not_caret():
    """VHDL uses 'xor' operator, not '^'."""
    code = _generate("CRC-32/ISO-HDLC")
    code_no_comments = re.sub(r'--[^\n]*', '', code)
    assert "^" not in code_no_comments


def test_concurrent_assignment_operator():
    """VHDL signal assignments use '<=' not '='."""
    code = _generate("CRC-8/SMBUS")
    assert "<=" in code


def test_all_output_bits_assigned_crc32():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    for i in range(32):
        assert f"crc_out({i}) <=" in code


def test_all_output_bits_assigned_crc8():
    code = _generate("CRC-8/SMBUS", data_width=8)
    for i in range(8):
        assert f"crc_out({i}) <=" in code


def test_all_output_bits_assigned_crc64():
    code = _generate("CRC-64/GO-ISO", data_width=8)
    for i in range(64):
        assert f"crc_out({i}) <=" in code


def test_header_present():
    code = _generate("CRC-16/MODBUS")
    assert "crcZero" in code
    assert "CRC-16/MODBUS" in code


def test_custom_entity_name():
    alg = CATALOG["CRC-32/ISO-HDLC"]
    eqs = derive_equations(alg, 8)
    code = VhdlRenderer().render(eqs, alg, 8, name="my_crc_entity")
    assert "entity my_crc_entity is" in code
    assert "end my_crc_entity;" in code


@pytest.mark.parametrize("name", ["CRC-8/SMBUS", "CRC-16/ARC", "CRC-32/ISO-HDLC", "CRC-64/GO-ISO"])
def test_ends_with_newline(name):
    assert _generate(name).endswith("\n")
