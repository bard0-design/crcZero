# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Integration test: compile and simulate generated Verilog with iverilog+vvp.

This closes the most critical gap in the test suite: it actually runs the
generated RTL through a simulator and verifies that all test vectors pass.

Skipped automatically when iverilog/vvp are not found in PATH.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from crczero.catalog import CATALOG
from crczero.generator import CrcGenerator


def _find_tool(name: str) -> str | None:
    """Search PATH for a tool; returns None if not found."""
    return shutil.which(name)


IVERILOG = _find_tool("iverilog")
VVP      = _find_tool("vvp")
XVLOG    = _find_tool("xvlog")
XELAB    = _find_tool("xelab")
XSIM     = _find_tool("xsim")

_HAS_IVERILOG = bool(IVERILOG and VVP)
_HAS_XSIM     = bool(XVLOG and XELAB and XSIM)

requires_iverilog = pytest.mark.skipif(
    not _HAS_IVERILOG and not _HAS_XSIM,
    reason="no Verilog simulator found (need iverilog/vvp or xvlog/xelab/xsim)",
)

# Where to persist VCDs across test runs
VCD_DIR = Path(__file__).parent / "vcd"


def _save_vcd(tmp_path: Path, tb_name: str) -> None:
    """Copy the VCD from tmp_path to tests/vcd/ for inspection."""
    vcd_src = tmp_path / f"{tb_name}.vcd"
    if not vcd_src.exists():
        return
    VCD_DIR.mkdir(exist_ok=True)
    import shutil as _shutil
    _shutil.copy2(vcd_src, VCD_DIR / f"{tb_name}.v.vcd")


def _run_iverilog(tmp_path: Path, dut_path: Path, tb_path: Path) -> str:
    sim_path = tmp_path / "sim"
    r = subprocess.run(
        [IVERILOG, "-o", str(sim_path), str(dut_path), str(tb_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"iverilog compilation failed:\n{r.stderr}"
    r = subprocess.run(
        [VVP, str(sim_path)],
        capture_output=True, text=True,
        cwd=str(tmp_path),
    )
    assert r.returncode == 0, (
        f"vvp exited with {r.returncode}:\n{r.stdout}\n{r.stderr}"
    )
    return r.stdout


def _run_xsim(tmp_path: Path, dut_path: Path, tb_path: Path, tb_module: str) -> str:
    r = subprocess.run(
        [XVLOG, str(dut_path), str(tb_path)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xvlog failed:\n{r.stdout}\n{r.stderr}"
    r = subprocess.run(
        [XELAB, tb_module, "-debug", "typical", "-timescale", "1ns/1ps"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xelab failed:\n{r.stdout}\n{r.stderr}"
    # The testbench uses $dumpfile/$dumpvars to write the VCD automatically.
    # Do NOT use a Tcl open_vcd alongside $dumpfile — xsim rejects two concurrent
    # VCD sessions and crashes on exit.
    r = subprocess.run(
        [XSIM, f"work.{tb_module}", "--runall", "--nolog"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xsim failed:\n{r.stdout}\n{r.stderr}"
    return r.stdout + r.stderr


def _run_simulation(tmp_path: Path, dut_code: str, tb_code: str, tb_name: str) -> str:
    """Compile and simulate; return simulator output. Raises on non-zero exit."""
    dut_path = tmp_path / "dut.v"
    tb_path  = tmp_path / "tb.v"
    dut_path.write_text(dut_code, encoding="utf-8")
    tb_path.write_text(tb_code,   encoding="utf-8")

    if _HAS_IVERILOG:
        output = _run_iverilog(tmp_path, dut_path, tb_path)
    else:
        output = _run_xsim(tmp_path, dut_path, tb_path, tb_name)

    _save_vcd(tmp_path, tb_name)
    return output


# Core algorithms covering: reflected, normal, 8-bit, 16-bit, 24-bit, 32-bit CRC widths.
# CRC-24/BLE has init=0x555555 (non-symmetric): exercises the hardware-init conversion.
SIMULATION_CASES = [
    ("CRC-8/SMBUS",     8),   # normal, CRC-8
    ("CRC-16/ARC",      8),   # reflected, CRC-16
    ("CRC-24/BLE",      8),   # reflected, non-symmetric init
    ("CRC-32/ISO-HDLC", 8),   # reflected, CRC-32 (Ethernet)
    ("CRC-32/MPEG-2",   8),   # normal, CRC-32
    ("CRC-32/ISO-HDLC", 32),  # reflected, 32-bit data width
]


@requires_iverilog
@pytest.mark.parametrize("alg_name,data_width", SIMULATION_CASES)
def test_verilog_simulation_all_pass(alg_name, data_width, tmp_path):
    """All test vectors in the generated Verilog testbench must report PASS."""
    alg = CATALOG[alg_name]
    gen = CrcGenerator(alg, data_width=data_width)

    from crczero.renderers.verilog import VerilogRenderer
    tb_name = VerilogRenderer().default_name(alg, data_width) + "_tb"

    dut_code = gen.generate_verilog()
    tb_code = gen.generate_testbench_verilog()

    stdout = _run_simulation(tmp_path, dut_code, tb_code, tb_name)

    # Verify no individual vector failure
    assert "FAIL vector" not in stdout, (
        f"{alg_name} D={data_width}: simulator reported failures:\n{stdout}"
    )
    # Verify the final summary confirms all passed
    assert "VECTORS PASSED" in stdout, (
        f"{alg_name} D={data_width}: expected 'VECTORS PASSED' in output:\n{stdout}"
    )
    assert "VECTORS FAILED" not in stdout, (
        f"{alg_name} D={data_width}: simulator reported failures:\n{stdout}"
    )


@requires_iverilog
@pytest.mark.parametrize("alg_name,data_width", SIMULATION_CASES)
def test_verilog_compiles_cleanly(alg_name, data_width, tmp_path):
    """DUT alone must compile without errors (iverilog or xvlog)."""
    alg = CATALOG[alg_name]
    gen = CrcGenerator(alg, data_width=data_width)
    dut_path = tmp_path / "dut.v"
    dut_path.write_text(gen.generate_verilog(), encoding="utf-8")

    if _HAS_IVERILOG:
        result = subprocess.run(
            [IVERILOG, "-t", "null", "-g2001", str(dut_path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"{alg_name} D={data_width} iverilog -t null failed:\n{result.stderr}"
        )
        assert result.stderr == "", (
            f"{alg_name} D={data_width} iverilog warnings:\n{result.stderr}"
        )
    else:
        result = subprocess.run(
            [XVLOG, str(dut_path)],
            capture_output=True, text=True, cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"{alg_name} D={data_width} xvlog failed:\n{result.stdout}\n{result.stderr}"
        )
