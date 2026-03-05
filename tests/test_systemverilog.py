"""Structural tests for the SystemVerilog renderer."""

import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations
from crczero.renderers.systemverilog import SystemVerilogRenderer


def _generate(name, data_width=8):
    alg = CATALOG[name]
    eqs = derive_equations(alg, data_width)
    return SystemVerilogRenderer().render(eqs, alg, data_width)


def test_module_keyword():
    code = _generate("CRC-32/ISO-HDLC")
    assert "module " in code


def test_named_endmodule():
    code = _generate("CRC-32/ISO-HDLC")
    assert "endmodule : crc_32_iso_hdlc_d8" in code


def test_logic_type_ports():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "input  logic [7:0]  data_in" in code
    assert "input  logic [31:0] crc_in" in code
    assert "output logic [31:0] crc_out" in code


def test_all_output_bits_assigned_crc32():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    for i in range(32):
        assert f"assign crc_out[{i}]" in code


def test_no_wire_keyword():
    """SV output must use 'logic', not 'wire'."""
    code = _generate("CRC-32/ISO-HDLC")
    assert "wire " not in code


def test_header_present():
    code = _generate("CRC-16/KERMIT")
    assert "crcZero" in code
    assert "CRC-16/KERMIT" in code


@pytest.mark.parametrize("name", ["CRC-8/SMBUS", "CRC-16/ARC", "CRC-32/ISO-HDLC"])
def test_ends_with_newline(name):
    assert _generate(name).endswith("\n")
