# Contributing to crcZero

Thank you for your interest in contributing! This document covers everything you need to get started.

---

## Development Setup

```bash
git clone https://github.com/bard0-design/crcZero.git
cd crcZero

# Create a virtual environment (Python 3.9+)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify the installation
crcZero --list-algorithms
pytest
```

---

## Running Tests

```bash
# Full test suite
pytest

# With coverage report
pytest --cov=crczero --cov-report=term-missing

# Single test file
pytest tests/test_equations.py -v

# Skip slow simulation tests (requires iverilog)
pytest -m "not slow" -v
```

### Optional test dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| `iverilog` + `vvp` | Verilog simulation tests | [Icarus Verilog](https://steveicarus.github.io/iverilog/) |
| `ghdl` | VHDL simulation tests | [GHDL](https://ghdl.github.io/ghdl/) |
| `xvlog`/`xvhdl`/`xelab`/`xsim` | Simulation fallback (Vivado) | Xilinx/AMD Vivado |
| `crcmod` | Cross-validation against known-good CRC library | `pip install crcmod` |
| `yowasp-yosys` | Verilog synthesis checking | `pip install yowasp-yosys` |

Tests that require missing tools are **automatically skipped** — they never fail due to a missing tool.

---

## Project Layout

```
src/crczero/
├── algorithm.py        # Algorithm frozen dataclass + poly helpers
├── catalog.py          # Named CRC algorithm catalog (dict)
├── equations.py        # GF(2) symbolic unrolling → CrcEquations
├── software_crc.py     # Pure-Python CRC oracle (Williams model)
├── generator.py        # CrcGenerator — public API entry point
├── cli.py              # argparse CLI
└── renderers/
    ├── base.py                 # Abstract BaseRenderer
    ├── verilog.py              # Verilog-2001 renderer
    ├── systemverilog.py        # SystemVerilog renderer
    ├── vhdl.py                 # VHDL-1993 renderer
    ├── testbench_verilog.py    # Combinatorial Verilog testbench
    ├── testbench_vhdl.py       # Combinatorial VHDL testbench
    ├── axi_stream_verilog.py   # AXI4-Stream wrapper (Verilog-2001)
    ├── axi_stream_sv.py        # AXI4-Stream wrapper (SystemVerilog)
    ├── axi_stream_vhdl.py      # AXI4-Stream wrapper (VHDL-1993)
    ├── testbench_axi_verilog.py # AXI4-Stream testbench (Verilog)
    └── testbench_axi_vhdl.py   # AXI4-Stream testbench (VHDL)

tests/
├── test_software_crc.py          # Oracle vs catalog check values
├── test_equations.py             # Equation derivation correctness
├── test_verilog.py               # Verilog renderer (structural)
├── test_systemverilog.py         # SystemVerilog renderer (structural)
├── test_vhdl.py                  # VHDL renderer (structural)
├── test_testbench_verilog.py     # Verilog testbench renderer
├── test_testbench_vhdl.py        # VHDL testbench renderer
├── test_axi_stream_verilog.py    # AXI4-Stream Verilog wrapper (structural)
├── test_axi_stream_sv.py         # AXI4-Stream SV wrapper (structural)
├── test_axi_stream_vhdl.py       # AXI4-Stream VHDL wrapper (structural)
├── test_cli.py                   # CLI argument parsing and output
├── test_crcmod.py                # Cross-check vs crcmod library (optional)
├── test_simulation_verilog.py    # Combinatorial Verilog simulation (optional)
├── test_simulation_vhdl.py       # Combinatorial VHDL simulation (optional)
├── test_simulation_axi_verilog.py # AXI Verilog simulation (optional)
└── test_simulation_axi_vhdl.py   # AXI VHDL simulation (optional)
```

---

## Adding a New Algorithm to the Catalog

1. Look up the algorithm parameters in the [RevEng catalog](https://reveng.sourceforge.io/crc-catalogue/).
2. Open [src/crczero/catalog.py](src/crczero/catalog.py) and add an entry:

```python
"CRC-16/EXAMPLE": Algorithm(
    name="CRC-16/EXAMPLE",
    width=16,
    poly=0x1234,
    init=0x0000,
    ref_in=False,
    ref_out=False,
    xor_out=0x0000,
    check=0xABCD,   # CRC of b"123456789"
    residue=0x0000,
),
```

3. The `check` value is automatically verified by `tests/test_software_crc.py` and `tests/test_equations.py`. Run `pytest` to confirm it passes.

---

## Adding a New Language Renderer

1. Create `src/crczero/renderers/<language>.py` subclassing `BaseRenderer`.
2. Implement `render(equations, algorithm, data_width, module_name)`.
3. Add a `generate_<language>()` method to `CrcGenerator` in `generator.py`.
4. Add a `--lang <language>` choice to the CLI in `cli.py`.
5. Write tests in `tests/test_<language>.py` following the same pattern as `test_verilog.py`.

---

## Code Style

- **Zero runtime dependencies** — stdlib only in `src/crczero/`.
- **No Jinja2, no NumPy** — string building and bitmask arithmetic only.
- Standard Python style (PEP 8). No formatter is enforced currently; keep consistent with surrounding code.
- All public functions and classes must have docstrings.
- Type hints are encouraged (Python 3.9+ syntax).

---

## Pull Request Checklist

- [ ] `pytest` passes with no failures
- [ ] New algorithms include a `check` value from the RevEng catalog
- [ ] New renderers include structural tests (module name, port declarations, XOR terms)
- [ ] No new runtime dependencies added to `pyproject.toml`
- [ ] Docstrings added for new public API symbols

---

## Reporting Bugs

Please open an issue with:
- The `crcZero` version (`pip show crczero`)
- The exact command or API call that produced the unexpected result
- The expected output vs the actual output
- For RTL issues: the algorithm name, data width, and a test vector that fails

---

## Algorithm Correctness Standard

Every generated RTL module must produce bit-for-bit identical results to the Williams model reference implementation in `software_crc.py`. The verification chain is:

```
RevEng catalog check value
    → software_crc.compute_crc    (Williams model oracle)
        → equations.simulate_equations  (symbolic GF(2) unrolling)
            → rendered HDL              (Verilog / SV / VHDL)
                → iverilog/ghdl/xsim simulation  (actual waveform, VCD to tests/vcd/)
```

Any discrepancy at any level is a bug.
