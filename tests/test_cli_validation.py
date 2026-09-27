"""CLI argument validation regressions."""
import pytest

from crczero.cli import main


@pytest.mark.parametrize("args", [
    ["--poly", "7", "--width", "-1"],
    ["--poly", "7", "--width", "0"],
    ["--poly", "nope", "--width", "8"],
    ["--poly", "7", "--width", "8", "--init", "nope"],
    ["--algorithm", "CRC-8/SMBUS", "--data-width", "3", "--testbench"],
])
def test_cli_invalid_inputs_are_argument_errors(capsys, args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "error:" in error and "Traceback" not in error
