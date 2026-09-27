"""Shared simulator helpers for behavioral regression tests."""
import shutil
import subprocess

import pytest


def run(tmp_path, *args):
    result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr



def tool(name):
    executable = shutil.which(name)
    if not executable:
        pytest.skip(f"{name} is not available")
    return executable
