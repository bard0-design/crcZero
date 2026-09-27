"""Independent oracle and simulation failure regressions."""
from dataclasses import replace
import subprocess

import pytest

from crczero.catalog import CATALOG
from crczero.generator import CrcGenerator
from crczero.renderers.testbench_verilog import _build_test_vectors
from crczero.software_crc import compute_crc
from tests.simulation_helpers import run, tool


@pytest.mark.parametrize("ref_in", [False, True])
def test_vectors_use_independent_oracle(monkeypatch, ref_in):
    def forbidden(*args, **kwargs):
        raise AssertionError("Test vectors must not use the equation implementation")
    monkeypatch.setattr("crczero.equations.derive_equations", forbidden)
    monkeypatch.setattr("crczero.equations.simulate_equations", forbidden)
    alg = replace(CATALOG["CRC-16/ARC"], init=0x1234, xor_out=0x5678,
                  ref_in=ref_in, ref_out=not ref_in)
    vectors = _build_test_vectors(alg, 8)
    assert vectors[8][2] ^ alg.xor_out == compute_crc(alg, b"123456789")



def test_faulty_verilog_dut_fails_simulation(tmp_path):
    compiler, simulator = tool("iverilog"), tool("vvp")
    (tmp_path / "core.v").write_text(
        "module core(input [7:0] data_in, crc_in, output [7:0] crc_out); "
        "assign crc_out = 0; endmodule")
    gen = CrcGenerator(CATALOG["CRC-8/SMBUS"])
    (tmp_path / "tb.v").write_text(gen.generate_testbench_verilog("core"))
    run(tmp_path, compiler, "-g2001", "-o", "sim", "core.v", "tb.v")
    result = subprocess.run([simulator, "sim"], cwd=tmp_path, capture_output=True,
                            text=True, timeout=30)
    assert result.returncode != 0
    assert "VECTORS FAILED" in result.stdout
