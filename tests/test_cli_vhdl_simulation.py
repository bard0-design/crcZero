"""CLI VHDL simulation path and entity-name regressions."""
import pytest

from crczero.cli import main
from tests.simulation_helpers import tool


@pytest.mark.parametrize("relative", [False, True])
@pytest.mark.parametrize("module_name", [None, "custom_core"])
def test_cli_vhdl_simulation_paths(tmp_path, monkeypatch, relative, module_name):
    tool("ghdl")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "output dir"
    out.mkdir()
    stem = "output dir/unrelated_filename" if relative else str(out / "unrelated_filename")
    args = ["--algorithm", "CRC-8/SMBUS", "--lang", "vhdl", "--output", stem,
            "--testbench", "--simulate"]
    if module_name:
        args += ["--module-name", module_name]
    main(args)
    assert (out / ((module_name or "crc_8_smbus_d8") + "_tb.vcd")).exists()
