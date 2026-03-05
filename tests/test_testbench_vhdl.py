"""Structural tests for the VHDL-1993 testbench renderer."""

import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations
from crczero.renderers.testbench_vhdl import VhdlTestbenchRenderer


def _generate(name, data_width=8):
    alg = CATALOG[name]
    eqs = derive_equations(alg, data_width)
    return VhdlTestbenchRenderer().render(eqs, alg, data_width)


def test_library_clause():
    code = _generate("CRC-32/ISO-HDLC")
    assert "library ieee;" in code


def test_entity_and_end():
    code = _generate("CRC-32/ISO-HDLC")
    assert "entity crc_32_iso_hdlc_d8_tb is" in code
    assert "end entity;" in code


def test_architecture_sim():
    code = _generate("CRC-32/ISO-HDLC")
    assert "architecture sim of crc_32_iso_hdlc_d8_tb is" in code
    assert "end sim;" in code


def test_direct_entity_instantiation():
    code = _generate("CRC-32/ISO-HDLC")
    assert "entity work.crc_32_iso_hdlc_d8(rtl)" in code


def test_port_map():
    code = _generate("CRC-32/ISO-HDLC")
    assert "port map" in code
    assert "data_in => data_in" in code
    assert "crc_in  => crc_in" in code
    assert "crc_out => crc_out" in code


def test_stimulus_process():
    code = _generate("CRC-32/ISO-HDLC")
    assert "stim : process" in code


def test_pass_fail_report():
    code = _generate("CRC-32/ISO-HDLC")
    assert "PASS" in code
    assert "FAIL" in code
    assert "severity error" in code
    assert "severity failure" in code


def test_wait_for_settle():
    code = _generate("CRC-32/ISO-HDLC")
    assert "wait for 10 ns" in code


def test_port_widths_crc32():
    code = _generate("CRC-32/ISO-HDLC", data_width=8)
    assert "std_logic_vector(7 downto 0)" in code
    assert "std_logic_vector(31 downto 0)" in code


def test_port_widths_crc8():
    code = _generate("CRC-8/SMBUS", data_width=8)
    assert "std_logic_vector(7 downto 0)" in code


def test_ends_with_newline():
    code = _generate("CRC-32/ISO-HDLC")
    assert code.endswith("\n")


@pytest.mark.parametrize("name", ["CRC-8/SMBUS", "CRC-16/ARC", "CRC-32/ISO-HDLC", "CRC-64/GO-ISO"])
def test_multiple_algorithms(name):
    code = _generate(name)
    assert "stim : process" in code
    assert "severity failure" in code
