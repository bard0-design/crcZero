# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Structural tests for the Verilog-2001 testbench renderer."""

import re
import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations
from crczero.renderers.testbench_verilog import VerilogTestbenchRenderer


def _generate(name, data_width=8):
    alg = CATALOG[name]
    eqs = derive_equations(alg, data_width)
    return VerilogTestbenchRenderer().render(eqs, alg, data_width)


def test_timescale_present():
    code = _generate("CRC-32/ISO-HDLC")
    assert "`timescale" in code


def test_module_and_endmodule():
    code = _generate("CRC-32/ISO-HDLC")
    assert "module " in code
    assert "endmodule" in code


def test_tb_name_suffix():
    code = _generate("CRC-32/ISO-HDLC")
    assert "crc_32_iso_hdlc_d8_tb" in code


def test_dut_instantiation():
    code = _generate("CRC-32/ISO-HDLC")
    assert "crc_32_iso_hdlc_d8 dut" in code


def test_dumpfile_present():
    code = _generate("CRC-32/ISO-HDLC")
    assert "$dumpfile" in code


def test_dumpvars_present():
    code = _generate("CRC-32/ISO-HDLC")
    assert "$dumpvars" in code


def test_finish_present():
    code = _generate("CRC-32/ISO-HDLC")
    assert "$finish" in code


def test_pass_fail_present():
    code = _generate("CRC-32/ISO-HDLC")
    assert "PASS" in code
    assert "FAIL" in code


def test_port_widths_crc32():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "[7:0]" in code and "data_in" in code
    assert "[31:0]" in code and "crc_in" in code
    assert "wire" in code and "crc_out" in code


def test_port_widths_crc8():
    code = _generate("CRC-8/SMBUS", data_width=8)
    assert "[7:0]" in code and "data_in" in code
    assert "wire" in code and "crc_out" in code


def test_ends_with_newline():
    code = _generate("CRC-32/ISO-HDLC")
    assert code.endswith("\n")


@pytest.mark.parametrize("name", ["CRC-8/SMBUS", "CRC-16/ARC", "CRC-32/ISO-HDLC", "CRC-64/GO-ISO"])
def test_multiple_algorithms(name):
    code = _generate(name)
    assert "$dumpfile" in code
    assert "PASS" in code
