"""Structural tests for the Verilog-2001 renderer."""

import re
import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations
from crczero.renderers.verilog import VerilogRenderer


def _generate(name, data_width=8):
    alg = CATALOG[name]
    eqs = derive_equations(alg, data_width)
    return VerilogRenderer().render(eqs, alg, data_width)


def test_module_keyword():
    code = _generate("CRC-32/ISO-HDLC")
    assert "module " in code
    assert "endmodule" in code


def test_port_declarations():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "input  [7:0]  data_in" in code
    assert "input  [31:0] crc_in" in code
    assert "output [31:0] crc_out" in code


def test_all_output_bits_assigned_crc32():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    for i in range(32):
        assert f"assign crc_out[{i}]" in code, f"Missing assignment for crc_out[{i}]"


def test_all_output_bits_assigned_crc8():
    code = _generate("CRC-8/SMBUS", data_width=8)
    for i in range(8):
        assert f"assign crc_out[{i}]" in code


def test_all_output_bits_assigned_crc64():
    code = _generate("CRC-64/GO-ISO", data_width=8)
    for i in range(64):
        assert f"assign crc_out[{i}]" in code


def test_no_reg_keyword():
    """Verilog-2001 output must not use 'reg' (all combinatorial assigns)."""
    code = _generate("CRC-32/ISO-HDLC")
    # Allow 'reg' in comments, not in code
    code_no_comments = re.sub(r'//[^\n]*', '', code)
    assert "reg " not in code_no_comments


def test_module_name_default():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "module crc_32_iso_hdlc_d8" in code


def test_module_name_custom():
    alg = CATALOG["CRC-32/ISO-HDLC"]
    eqs = derive_equations(alg, 8)
    code = VerilogRenderer().render(eqs, alg, 8, name="my_crc")
    assert "module my_crc" in code
    assert "endmodule  // my_crc" in code


def test_header_contains_algorithm_name():
    code = _generate("CRC-32/ISO-HDLC")
    assert "CRC-32/ISO-HDLC" in code


def test_header_contains_check_value():
    code = _generate("CRC-32/ISO-HDLC")
    assert "0xCBF43926" in code.upper() or "cbf43926" in code.lower()


def test_wide_data_width():
    """64-bit data width generates 32 assignments (CRC width, not data width)."""
    code = _generate("CRC-32/ISO-HDLC", data_width=64)
    assert "input  [63:0]  data_in" in code
    for i in range(32):
        assert f"assign crc_out[{i}]" in code


@pytest.mark.parametrize("name", ["CRC-8/SMBUS", "CRC-16/ARC", "CRC-32/ISO-HDLC", "CRC-64/GO-ISO"])
def test_ends_with_newline(name):
    code = _generate(name)
    assert code.endswith("\n")
