"""Tests for the CLI entry point."""

import subprocess
import sys
import pytest
from crczero.cli import build_parser, main, _build_algorithm


# ---- --list-algorithms ----

def test_list_algorithms_exits_zero(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli", "--list-algorithms"],
        capture_output=True, text=True
    )
    assert result.returncode == 0


def test_list_algorithms_contains_crc32(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli", "--list-algorithms"],
        capture_output=True, text=True
    )
    assert "CRC-32/ISO-HDLC" in result.stdout


# ---- Verilog generation ----

def test_generate_verilog_stdout():
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--algorithm", "CRC-32/ISO-HDLC",
         "--data-width", "8",
         "--lang", "verilog"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "module " in result.stdout
    assert "endmodule" in result.stdout


def test_generate_sv_stdout():
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--algorithm", "CRC-16/KERMIT",
         "--lang", "sv"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "logic" in result.stdout
    assert "endmodule :" in result.stdout


def test_generate_vhdl_stdout():
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--algorithm", "CRC-8/SMBUS",
         "--lang", "vhdl"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "entity " in result.stdout
    assert "architecture rtl" in result.stdout


# ---- --lang all with file output ----

def test_lang_all_creates_three_files(tmp_path):
    stem = str(tmp_path / "crc32")
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--algorithm", "CRC-32/ISO-HDLC",
         "--lang", "all",
         "--output", stem],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert (tmp_path / "crc32.v").exists()
    assert (tmp_path / "crc32.sv").exists()
    assert (tmp_path / "crc32.vhd").exists()


def test_output_file_content(tmp_path):
    out = str(tmp_path / "out")
    subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--algorithm", "CRC-32/ISO-HDLC",
         "--lang", "verilog",
         "--output", out],
        check=True, capture_output=True
    )
    content = (tmp_path / "out.v").read_text()
    assert "module " in content
    assert "CRC-32/ISO-HDLC" in content


# ---- Custom algorithm ----

def test_custom_algorithm_stdout():
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--poly", "0x04C11DB7",
         "--width", "32",
         "--init", "0xFFFFFFFF",
         "--ref-in",
         "--ref-out",
         "--xor-out", "0xFFFFFFFF",
         "--lang", "verilog",
         "--no-self-test"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "module " in result.stdout


# ---- --module-name override ----

def test_module_name_override():
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--algorithm", "CRC-32/ISO-HDLC",
         "--lang", "verilog",
         "--module-name", "my_ethernet_crc"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "module my_ethernet_crc" in result.stdout


# ---- Error cases ----

def test_unknown_algorithm_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--algorithm", "TOTALLY_UNKNOWN_XYZ"],
        capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "error" in result.stderr.lower()


def test_missing_poly_and_algorithm_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--width", "32",
         "--lang", "verilog"],
        capture_output=True, text=True
    )
    assert result.returncode != 0


def test_invalid_data_width_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "crczero.cli",
         "--algorithm", "CRC-32/ISO-HDLC",
         "--data-width", "0",
         "--lang", "verilog"],
        capture_output=True, text=True
    )
    assert result.returncode != 0
