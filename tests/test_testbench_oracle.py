"""Independent oracle and simulation failure regressions."""
from dataclasses import replace
import subprocess

import pytest

from crczero.catalog import CATALOG
from crczero.cli import _simulate_verilog
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



@pytest.mark.parametrize("case", ["pass", "fail", "incomplete"])
def test_verilog_runner_checks_completion(tmp_path, monkeypatch, capsys, case):
    compiler, simulator = tool("iverilog"), tool("vvp")
    monkeypatch.chdir(tmp_path)
    gen = CrcGenerator(CATALOG["CRC-8/SMBUS"])
    core = gen.generate_verilog("core")
    tb = gen.generate_testbench_verilog("core")
    assert "$fatal" not in tb
    if case == "fail":
        core = ("module core(input [7:0] data_in, crc_in, output [7:0] crc_out); "
                "assign crc_out = 0; endmodule")
    elif case == "incomplete":
        tb = "module core_tb; initial $finish; endmodule"
    (tmp_path / "core.v").write_text(core)
    (tmp_path / "tb.v").write_text(tb)
    run(tmp_path, compiler, "-g2001", "-o", "sim", "core.v", "tb.v")
    result = subprocess.run([simulator, "sim"], cwd=tmp_path, capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0  # Portable $finish does not carry pass/fail status.
    if case == "pass":
        _simulate_verilog(tmp_path / "core.v", tmp_path / "tb.v")
        assert "CRCZERO_TEST_PASS" in capsys.readouterr().out
    else:
        with pytest.raises(SystemExit) as exc:
            _simulate_verilog(tmp_path / "core.v", tmp_path / "tb.v")
        assert exc.value.code != 0
        assert "failed or did not complete" in capsys.readouterr().err
