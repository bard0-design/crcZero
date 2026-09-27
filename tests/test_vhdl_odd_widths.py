"""VHDL compilation and simulation for non-nibble CRC widths."""
import pytest

from crczero.catalog import CATALOG
from crczero.generator import CrcGenerator
from tests.simulation_helpers import run, tool


@pytest.mark.parametrize("name", ["CRC-3/GSM", "CRC-5/USB", "CRC-7/MMC"])
def test_vhdl_odd_width_testbench_and_wrapper(tmp_path, name):
    ghdl = tool("ghdl")
    gen = CrcGenerator(CATALOG[name], 8)
    (tmp_path / "core.vhd").write_text(gen.generate_vhdl("core"))
    (tmp_path / "axis.vhd").write_text(gen.generate_axi_stream_vhdl("core"))
    (tmp_path / "tb.vhd").write_text(gen.generate_testbench_vhdl("core"))
    run(tmp_path, ghdl, "-a", "--std=93", "core.vhd", "axis.vhd", "tb.vhd")
    run(tmp_path, ghdl, "-e", "--std=93", "core_tb")
    assert "VECTORS PASSED" in run(tmp_path, ghdl, "-r", "--std=93", "core_tb")
    run(tmp_path, ghdl, "--synth", "--std=93", "core_axis")
