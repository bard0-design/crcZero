# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Compilation test: verify generated SystemVerilog parses with iverilog -g2012.

SystemVerilog output was previously only structurally tested (string matching).
This test actually compiles the generated SV to catch syntax errors.

Skipped automatically when iverilog is not found in PATH.
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


IVERILOG = _find_tool("iverilog")

requires_iverilog = pytest.mark.skipif(
    not IVERILOG,
    reason="iverilog not found in PATH",
)

# Cover reflected, normal, various CRC widths, and multiple data widths.
COMPILATION_CASES = [
    ("CRC-8/SMBUS",     8),
    ("CRC-16/ARC",      8),
    ("CRC-16/KERMIT",   8),
    ("CRC-32/ISO-HDLC", 8),
    ("CRC-32/ISO-HDLC", 32),
    ("CRC-32/MPEG-2",   8),
    ("CRC-64/GO-ISO",   8),
]


@requires_iverilog
@pytest.mark.parametrize("alg_name,data_width", COMPILATION_CASES)
def test_sv_dut_compiles(alg_name, data_width, tmp_path):
    """Generated SystemVerilog DUT must compile cleanly with iverilog -g2012."""
    alg = CATALOG[alg_name]
    gen = CrcGenerator(alg, data_width=data_width)
    dut_path = tmp_path / "dut.sv"
    dut_path.write_text(gen.generate_systemverilog(), encoding="utf-8")

    result = subprocess.run(
        [IVERILOG, "-g2012", "-t", "null", str(dut_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"{alg_name} D={data_width} iverilog -g2012 failed:\n{result.stderr}"
    )
    # Tolerate warnings about timescale but flag actual syntax warnings
    stderr_lines = [
        line for line in result.stderr.splitlines()
        if "timescale" not in line.lower()
    ]
    assert not stderr_lines, (
        f"{alg_name} D={data_width} iverilog warnings:\n" + "\n".join(stderr_lines)
    )


@requires_iverilog
@pytest.mark.parametrize("alg_name,data_width", COMPILATION_CASES)
def test_sv_axi_compiles(alg_name, data_width, tmp_path):
    """Generated SystemVerilog AXI-Stream wrapper must compile with iverilog -g2012."""
    alg = CATALOG[alg_name]
    gen = CrcGenerator(alg, data_width=data_width)
    dut_path = tmp_path / "dut.sv"
    axi_path = tmp_path / "axi.sv"
    dut_path.write_text(gen.generate_systemverilog(), encoding="utf-8")
    axi_path.write_text(gen.generate_axi_stream_sv(), encoding="utf-8")

    result = subprocess.run(
        [IVERILOG, "-g2012", "-t", "null", str(dut_path), str(axi_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"{alg_name} D={data_width} AXI SV iverilog -g2012 failed:\n{result.stderr}"
    )
