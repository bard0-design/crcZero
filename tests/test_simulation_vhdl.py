"""Integration test: compile and simulate generated VHDL with ghdl.

Closes the VHDL verification gap: actually runs the generated RTL through
a simulator and confirms all test vectors match the software oracle.

Skipped automatically when ghdl is not found in PATH.

GHDL workflow:
    ghdl -a --std=93 dut.vhd tb.vhd   # analyse
    ghdl -e --std=93 <tb_entity>       # elaborate
    ghdl -r --std=93 <tb_entity>       # run
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from crczero.catalog import CATALOG
from crczero.generator import CrcGenerator


def _find_tool(name: str) -> str | None:
    return shutil.which(name)


GHDL  = _find_tool("ghdl")
XVHDL = _find_tool("xvhdl")
XELAB = _find_tool("xelab")
XSIM  = _find_tool("xsim")

_HAS_GHDL = bool(GHDL)
_HAS_XSIM = bool(XVHDL and XELAB and XSIM)

requires_ghdl = pytest.mark.skipif(
    not _HAS_GHDL and not _HAS_XSIM,
    reason="no VHDL simulator found (need ghdl or xvhdl/xelab/xsim)",
)

# Where to persist VCDs across test runs
VCD_DIR = Path(__file__).parent / "vcd"


def _save_vcd(tmp_path: Path, tb_entity: str) -> None:
    """Copy the VCD from tmp_path to tests/vcd/ for inspection."""
    vcd_src = tmp_path / f"{tb_entity}.vcd"
    if not vcd_src.exists():
        return
    VCD_DIR.mkdir(exist_ok=True)
    import shutil as _shutil
    _shutil.copy2(vcd_src, VCD_DIR / f"{tb_entity}.vhd.vcd")


def _run_ghdl(tmp_path: Path, dut_path: Path, tb_path: Path, tb_entity: str) -> str:
    vcd_path = tmp_path / f"{tb_entity}.vcd"
    r = subprocess.run(
        [GHDL, "-a", "--std=93", str(dut_path), str(tb_path)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"ghdl -a failed:\n{r.stdout}\n{r.stderr}"
    r = subprocess.run(
        [GHDL, "-e", "--std=93", tb_entity],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"ghdl -e failed:\n{r.stdout}\n{r.stderr}"
    r = subprocess.run(
        [GHDL, "-r", "--std=93", tb_entity, f"--vcd={vcd_path}"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    output = r.stdout + r.stderr
    assert r.returncode == 0, f"ghdl -r exited {r.returncode}:\n{output}"
    return output


def _run_xsim_vhdl(tmp_path: Path, dut_path: Path, tb_path: Path, tb_entity: str) -> str:
    r = subprocess.run(
        [XVHDL, str(dut_path), str(tb_path)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xvhdl failed:\n{r.stdout}\n{r.stderr}"
    r = subprocess.run(
        [XELAB, tb_entity, "-debug", "typical"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xelab failed:\n{r.stdout}\n{r.stderr}"
    vcd_name = f"{tb_entity}.vcd"
    tcl_path = tmp_path / "sim.tcl"
    tcl_path.write_text(
        f"open_vcd {vcd_name}\nlog_vcd /*\nrun all\nclose_vcd\nquit\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [XSIM, f"work.{tb_entity}", "--nolog", "--tclbatch", "sim.tcl"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xsim failed:\n{r.stdout}\n{r.stderr}"
    return r.stdout + r.stderr


def _run_simulation(tmp_path: Path, dut_code: str, tb_code: str, tb_entity: str) -> str:
    """Analyse, elaborate and simulate; return output. Raises on failure."""
    dut_path = tmp_path / "dut.vhd"
    tb_path  = tmp_path / "tb.vhd"
    dut_path.write_text(dut_code, encoding="utf-8")
    tb_path.write_text(tb_code,   encoding="utf-8")

    if _HAS_GHDL:
        output = _run_ghdl(tmp_path, dut_path, tb_path, tb_entity)
    else:
        output = _run_xsim_vhdl(tmp_path, dut_path, tb_path, tb_entity)

    _save_vcd(tmp_path, tb_entity)
    return output


# Same algorithm set as the Verilog simulation tests for direct comparability.
SIMULATION_CASES = [
    ("CRC-8/SMBUS",     8),   # normal, CRC-8
    ("CRC-16/ARC",      8),   # reflected, CRC-16
    ("CRC-24/BLE",      8),   # reflected, non-symmetric init
    ("CRC-32/ISO-HDLC", 8),   # reflected, CRC-32 (Ethernet)
    ("CRC-32/MPEG-2",   8),   # normal, CRC-32
    ("CRC-32/ISO-HDLC", 32),  # reflected, 32-bit data width
]


@requires_ghdl
@pytest.mark.parametrize("alg_name,data_width", SIMULATION_CASES)
def test_vhdl_simulation_all_pass(alg_name, data_width, tmp_path):
    """All test vectors in the generated VHDL testbench must report PASS."""
    alg = CATALOG[alg_name]
    gen = CrcGenerator(alg, data_width=data_width)

    dut_code = gen.generate_vhdl()
    tb_code = gen.generate_testbench_vhdl()

    # Derive tb entity name the same way the renderer does
    from crczero.renderers.vhdl import VhdlRenderer
    tb_entity = VhdlRenderer().default_name(alg, data_width) + "_tb"

    output = _run_simulation(tmp_path, dut_code, tb_code, tb_entity)

    assert "FAIL vector" not in output, (
        f"{alg_name} D={data_width}: simulator reported failures:\n{output}"
    )
    assert "VECTORS PASSED" in output, (
        f"{alg_name} D={data_width}: expected 'VECTORS PASSED' in output:\n{output}"
    )


@requires_ghdl
@pytest.mark.parametrize("alg_name,data_width", SIMULATION_CASES)
def test_vhdl_analyses_cleanly(alg_name, data_width, tmp_path):
    """DUT alone must analyse without errors (ghdl or xvhdl)."""
    alg = CATALOG[alg_name]
    gen = CrcGenerator(alg, data_width=data_width)
    dut_path = tmp_path / "dut.vhd"
    dut_path.write_text(gen.generate_vhdl(), encoding="utf-8")

    if _HAS_GHDL:
        result = subprocess.run(
            [GHDL, "-a", "--std=93", str(dut_path)],
            capture_output=True, text=True, cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"{alg_name} D={data_width} ghdl -a failed:\n{result.stderr}"
        )
    else:
        result = subprocess.run(
            [XVHDL, str(dut_path)],
            capture_output=True, text=True, cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"{alg_name} D={data_width} xvhdl failed:\n{result.stdout}\n{result.stderr}"
        )
