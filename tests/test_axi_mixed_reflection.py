"""Mixed-reflection AXI-Stream simulation regressions."""
from dataclasses import replace

import pytest

from crczero.catalog import CATALOG
from crczero.generator import CrcGenerator
from tests.simulation_helpers import run, tool
from tests.test_simulation_axi_verilog import _build_axis_tb_verilog
from tests.test_simulation_axi_vhdl import _build_axis_tb_vhdl


@pytest.mark.parametrize("data_width", [8, 16, 32, 64])
@pytest.mark.parametrize("xor_out", [0, 0x5678])
@pytest.mark.parametrize("ref_in", [False, True])
@pytest.mark.parametrize("lang", ["verilog", "sv", "vhdl"])
def test_mixed_reflection_axis(tmp_path, monkeypatch, ref_in, lang, xor_out, data_width):
    alg = replace(CATALOG["CRC-16/ARC"], name="mixed", init=0x1234,
                  xor_out=xor_out, ref_in=ref_in, ref_out=not ref_in)
    monkeypatch.setitem(CATALOG, "mixed", alg)
    gen = CrcGenerator(alg, data_width)
    packets = [b"123456789", b"another packet", b"x"]
    if lang == "vhdl":
        ghdl = tool("ghdl")
        (tmp_path / "core.vhd").write_text(gen.generate_vhdl("core"))
        (tmp_path / "axis.vhd").write_text(gen.generate_axi_stream_vhdl("core"))
        (tmp_path / "tb.vhd").write_text(
            _build_axis_tb_vhdl("mixed", "core", "core_axis", data_width, packets, [0, 3, 1]))
        run(tmp_path, ghdl, "-a", "--std=08", "core.vhd", "axis.vhd", "tb.vhd")
        run(tmp_path, ghdl, "-e", "--std=08", "core_axis_sim_tb")
        output = run(tmp_path, ghdl, "-r", "--std=08", "core_axis_sim_tb", "--stop-time=100us")
    else:
        compiler, simulator = tool("iverilog"), tool("vvp")
        core = gen.generate_systemverilog if lang == "sv" else gen.generate_verilog
        axis = gen.generate_axi_stream_sv if lang == "sv" else gen.generate_axi_stream_verilog
        (tmp_path / "core.v").write_text(core("core"))
        (tmp_path / "axis.v").write_text(axis("core"))
        (tmp_path / "tb.v").write_text(
            _build_axis_tb_verilog("mixed", "core", data_width, packets, [0, 3, 1]))
        run(tmp_path, compiler, "-g2012" if lang == "sv" else "-g2001",
            "-o", "sim", "core.v", "axis.v", "tb.v")
        output = run(tmp_path, simulator, "sim")
    assert "PASSED" in output and "FAIL" not in output


@pytest.mark.parametrize("lang", ["verilog", "sv", "vhdl"])
def test_intermediate_output_corruption_is_detected(tmp_path, monkeypatch, lang):
    method = {"verilog": "generate_axi_stream_verilog",
              "sv": "generate_axi_stream_sv", "vhdl": "generate_axi_stream_vhdl"}[lang]
    original = getattr(CrcGenerator, method)

    def corrupt(self, name):
        code = original(self, name)
        if lang == "vhdl":
            changed = code.replace("m_tdata_r <= crc_next;", "m_tdata_r <= (others => '0');")
        else:
            changed = code.replace("s_axis_tlast ? crc_next ^ XOR_OUT : crc_next",
                                   "s_axis_tlast ? crc_next ^ XOR_OUT : 16'h0")
        assert changed != code
        return changed

    monkeypatch.setattr(CrcGenerator, method, corrupt)
    with pytest.raises(AssertionError, match="FAIL"):
        test_mixed_reflection_axis(tmp_path, monkeypatch, True, lang, 0x5678, 32)
