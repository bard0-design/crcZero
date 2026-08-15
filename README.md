

# crcZero

[![CI](https://github.com/bard0-design/crcZero/actions/workflows/ci.yml/badge.svg)](https://github.com/bard0-design/crcZero/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/crczero)](https://pypi.org/project/crczero/)
[![Hardware Tested](https://img.shields.io/badge/hardware%20tested-Arty%20A7--100T-brightgreen)](hw_test/)

**Parallel CRC HDL code generator** — Verilog-2001, SystemVerilog, VHDL-1993, plus a portable C reference. Hardware tested on Arty A7-100T.

Generates synthesizable, parallel CRC modules from a built-in catalog of 80+ named algorithms
(reveng-verified), or from user-supplied polynomial parameters.
Includes self-checking testbenches, AXI4-Stream wrappers, and multi-vendor synthesis checks.

## Features

- **Three output targets** — Verilog-2001, SystemVerilog, VHDL-1993, and a portable C reference
- **80+ named algorithms** — CRC-8 through CRC-64, parameters sourced from the
  [reveng CRC catalogue](https://reveng.sourceforge.io/crc-catalogue/), all check values verified
- **Custom polynomials** — normal (Williams) or Koopman notation; check value auto-computed when not provided
- **Any data width** — 8, 16, 32, 64, or any positive integer bits per clock
- **AXI4-Stream wrappers** — clocked wrapper with slave (data in) and master (CRC out) interfaces,
  2-state FSM, full backpressure support
- **Self-checking testbenches** — Verilog and VHDL (iverilog/vvp, ghdl, and Vivado xsim compatible),
  25 test vectors each, VCD waveform output saved to `tests/vcd/`
- **CLI + Python API** — use from the command line or import in any Python project
- **Zero runtime dependencies** — pure Python 3.9+, stdlib only
- **Synthesis-verified** — all outputs pass Yosys (`yowasp-yosys`) across AMD/Xilinx, Altera/Intel,
  Lattice, Microchip, Efinix, and Gowin targets, and GHDL (`--synth`); pure behavioural RTL targets ASIC flows
- **Hardware-tested on silicon** — CRC-32/ISO-HDLC D=32 validated on Arty A7-100T (Artix-7 FPGA)
  via JTAG-AXI; 21/21 test vectors (1–1024 beats) confirmed correct on real hardware (see [`hw_test/`](hw_test/))

## How It Works

crcZero uses **GF(2) iterative symbolic unrolling** to derive, for each CRC output bit, the exact
set of `crc_in` and `data_in` bits that must be XORed together.

A state vector of N bitmasks (one per CRC register bit) is maintained. Each bitmask tracks which
input bits contribute to that state bit. Starting from `state[i] = (1 << i)`, D data bits are fed
one-by-one through the LFSR update rule symbolically. After D iterations, the state encodes the
complete parallel combinatorial equations as XOR trees, which the renderers emit directly as HDL assigns.

No matrix exponentiation — handles any CRC width and data width, including both reflected
(`ref_in == ref_out == True`) and normal modes.

## Installation

```bash
pip install crczero
```

Or install from source for development:

```bash
git clone https://github.com/bard0-design/crcZero
cd crcZero
pip install -e .
```

## Quick Start

### CLI

```bash
# List all 80+ built-in algorithms
crcZero --list-algorithms

# Generate Verilog for CRC-32 (Ethernet/ZIP)
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang verilog

# Generate all outputs to files (Verilog/SV/VHDL + C header/source)
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang all --output crc32

# Generate with testbench and simulate immediately (requires iverilog in PATH)
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang verilog \
        --output crc32 --testbench --simulate

# Generate AXI4-Stream wrapper alongside the CRC core
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang verilog \
        --output crc32 --axi-stream
# Produces: crc32.v  crc32_axis.v

# Generate a portable C reference implementation
crcZero --algorithm CRC-32/ISO-HDLC --lang c --output crc32_ref
# Produces: crc32_ref.h  crc32_ref.c

# Custom polynomial (Koopman notation)
crcZero --poly-koopman 0x82608EDB --width 32 --init 0xFFFFFFFF \
        --ref-in --ref-out --xor-out 0xFFFFFFFF --data-width 8 --lang sv
```

### Python API

```python
from crczero import CrcGenerator, catalog

gen = CrcGenerator(catalog["CRC-32/ISO-HDLC"], data_width=8)
assert gen.self_test()

print(gen.generate_verilog())
print(gen.generate_systemverilog())
print(gen.generate_vhdl())
header, source = gen.generate_c()
print(gen.generate_testbench_verilog())

# AXI4-Stream wrappers
print(gen.generate_axi_stream_verilog())
print(gen.generate_axi_stream_sv())
print(gen.generate_axi_stream_vhdl())

# Custom polynomial
from crczero import Algorithm, poly_from_koopman

alg = Algorithm(
    name="MY-CRC32", width=32, poly=0x04C11DB7,
    init=0xFFFFFFFF, ref_in=True, ref_out=True,
    xor_out=0xFFFFFFFF, check=0xCBF43926, residue=0xDEBB20E3,
)
gen = CrcGenerator(alg, data_width=32)
```

## Generated Output

The generated module has three ports:

| Port | Direction | Width | Description |
|---|---|---|---|
| `data_in` | input | D bits | Data word for this clock cycle |
| `crc_in` | input | N bits | CRC register input (chain from previous word) |
| `crc_out` | output | N bits | Updated CRC register output |

**Usage in hardware:**

1. Set `crc_in = INIT` for the first word
2. Connect `crc_out → crc_in` for subsequent words
3. After the last word: `final_crc = crc_out XOR XOR_OUT`

Example (CRC-32/ISO-HDLC, 8-bit data):

```verilog
// Purely combinatorial generated module
module crc_32_iso_hdlc_d8 (
    input  [7:0]  data_in,
    input  [31:0] crc_in,
    output [31:0] crc_out
);
    assign crc_out[0] = crc_in[1] ^ crc_in[2] ^ crc_in[8] ^ ...;
    // ...
endmodule

// Wire into a clocked parent design
module eth_tx (
    input  wire        clk, rst_n, valid,
    input  wire [7:0]  data,
    output reg  [31:0] fcs
);
    reg  [31:0] crc_reg;
    wire [31:0] crc_next;

    crc_32_iso_hdlc_d8 u_crc (.data_in(data), .crc_in(crc_reg), .crc_out(crc_next));

    always @(posedge clk or negedge rst_n)
        if (!rst_n) crc_reg <= 32'hFFFFFFFF;
        else if (valid) crc_reg <= crc_next;

    assign fcs = ~{crc_reg[7:0], crc_reg[15:8], crc_reg[23:16], crc_reg[31:24]};
endmodule
```

SystemVerilog and VHDL follow the same pattern. See [`sample_output/`](sample_output/) for complete generated files.

## AXI4-Stream Wrapper

The `--axi-stream` flag generates a clocked wrapper around the combinatorial CRC core.

### Interface

| Signal | Direction | Width | Description |
|---|---|---|---|
| `clk` | in | 1 | Clock |
| `rst_n` | in | 1 | Active-low synchronous reset |
| `s_axis_tdata` | in | D | Data input (slave) |
| `s_axis_tvalid` | in | 1 | Slave valid |
| `s_axis_tready` | out | 1 | Slave ready (de-asserted during WAIT_ACK) |
| `s_axis_tlast` | in | 1 | Last beat of packet |
| `m_axis_tdata` | out | N | Final CRC (XOR_OUT already applied) |
| `m_axis_tvalid` | out | 1 | Master valid |
| `m_axis_tready` | in | 1 | Master ready (backpressure from downstream) |
| `m_axis_tlast` | out | 1 | `1` when `m_axis_tvalid` is high |

### FSM

```
              TLAST accepted                 m_axis_tready
  ACCUM ─────────────────────► WAIT_ACK ──────────────────► ACCUM
    │  s_axis_tready = 1          │  s_axis_tready = 0        │
    │  accumulate crc_reg         │  hold m_axis_tdata         │
    └─────────────────────────────┴────────────────────────────┘
```

On `TLAST`: `m_axis_tdata = crc_result ^ XOR_OUT`, `m_axis_tvalid` asserted.
On handshake: `crc_reg` resets to `HW_INIT` for the next packet.

### Usage

```bash
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --output crc32 \
        --lang all --axi-stream
# Produces: crc32.v crc32_axis.v  crc32.sv crc32_axis.sv  crc32.vhd crc32_axis.vhd  crc32.h crc32.c
```

A self-checking AXI4-Stream testbench is available via
`gen.generate_testbench_axi_verilog()` / `gen.generate_testbench_axi_vhdl()`.
Runs 10 packets × 2 passes (LCG stall + no-stall) = 20 CRC checks per run.

## Custom Polynomials

| Notation | CRC-32 value |
|---|---|
| Normal (Williams) | `0x04C11DB7` |
| Koopman | `0x82608EDB` |

```bash
# Williams normal form
crcZero --poly 0x04C11DB7 --width 32 --init 0xFFFFFFFF \
        --ref-in --ref-out --xor-out 0xFFFFFFFF --data-width 8 --lang verilog

# Koopman notation
crcZero --poly-koopman 0x82608EDB --width 32 --init 0xFFFFFFFF \
        --ref-in --ref-out --xor-out 0xFFFFFFFF --data-width 8 --lang verilog
```

The check value is auto-computed when `--check` is not supplied.

```python
from crczero import poly_from_koopman, poly_to_koopman

normal  = poly_from_koopman(0x82608EDB, width=32)  # → 0x04C11DB7
koopman = poly_to_koopman(0x04C11DB7, width=32)    # → 0x82608EDB
```

## Testbench and Simulation

```bash
# Verilog (iverilog)
crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang verilog --testbench --simulate

# VHDL (ghdl)
crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang vhdl --testbench --simulate
```

Each testbench applies 25 test vectors (`b"123456789"` decomposed byte-by-byte + 16 deterministic
random words) and reports PASS/FAIL per vector. VCDs are saved to `tests/vcd/`.
Compatible with iverilog/vvp, ghdl, and Vivado xsim.

## Verification

### Python self-test

```python
from crczero import CrcGenerator, catalog

gen = CrcGenerator(catalog["CRC-32/ISO-HDLC"], data_width=8)
assert gen.self_test()  # verifies software oracle matches catalog check value
```

### Test suite

```bash
pip install -e ".[dev]"
pytest tests/
# 477 tests — catalog check values, equation derivation, renderer output,
# CLI flags, testbench renderers, AXI4-Stream wrapper, and full RTL simulation
```

### Synthesis (multi-vendor, Yosys)

```bash
pip install yowasp-yosys
python synth/run_synth.py                          # all six vendors
python synth/run_synth.py --vendor xilinx lattice  # subset
```

LUT counts for CRC-32/ISO-HDLC, D=8:

| Vendor | Family | LUTs |
|---|---|---:|
| AMD/Xilinx | 7-series (XC7), LUT6 | 62 |
| Altera/Intel | Cyclone V / Cyclone 10 GX (ALM) | 60 |
| Lattice | ECP5, LUT4 | 83 |

The generated RTL is purely combinatorial XOR logic with no vendor primitives — synthesises equally
well for ASIC flows.

### Resource usage

Minimum 2-input XOR operations per clock cycle (actual gate count after synthesis may be lower due
to sharing). Rule of thumb: `LUTs ≈ XOR_count / 5` on a 6-input-LUT FPGA.

| Algorithm | D=8 | D=16 | D=32 | D=64 |
|---|---:|---:|---:|---:|
| CRC-32/ISO-HDLC (Ethernet FCS) | 220 | 414 | 872 | 1390 |
| CRC-32/MPEG-2 / BZIP2 | 220 | 414 | 872 | 1390 |
| CRC-32C / ISCSI (Castagnoli) | 268 | 528 | 1036 | 1470 |
| CRC-8/SMBUS | 44 | — | — | — |
| CRC-16/ARC | 68 | 128 | — | — |
| CRC-64/GO-ISO | 56 | — | 224 | 468 |
| CRC-64/ECMA-182 | 524 | — | 2048 | 4004 |

## Algorithm Catalog

Use `crcZero --list-algorithms` to see all 80+ entries. A sample:

| Algorithm | Width | Polynomial | RefIn | RefOut | Check |
|---|---|---|---|---|---|
| CRC-8/SMBUS | 8 | 0x07 | No | No | 0xF4 |
| CRC-16/ARC | 16 | 0x8005 | Yes | Yes | 0xBB3D |
| CRC-16/MODBUS | 16 | 0x8005 | Yes | Yes | 0x4B37 |
| CRC-16/KERMIT | 16 | 0x1021 | Yes | Yes | 0x2189 |
| CRC-24/BLE | 24 | 0x00065B | Yes | Yes | 0xC25A56 |
| CRC-32/ISO-HDLC | 32 | 0x04C11DB7 | Yes | Yes | 0xCBF43926 |
| CRC-32/MPEG-2 | 32 | 0x04C11DB7 | No | No | 0x0376E6E7 |
| CRC-32C (Castagnoli) | 32 | 0x1EDC6F41 | Yes | Yes | 0xE3069283 |
| CRC-64/GO-ISO | 64 | 0x000000000000001B | Yes | Yes | 0xB90956C775A41001 |
| CRC-64/ECMA-182 | 64 | 0x42F0E1EBA9EA3693 | No | No | 0x6C40DF5F0B497347 |

## CLI Reference

```
crcZero [--list-algorithms]
        [--algorithm NAME | --poly HEX | --poly-koopman HEX]
        [--width INT] [--init HEX] [--ref-in] [--ref-out]
        [--xor-out HEX] [--check HEX] [--residue HEX] [--name STR]
        [--data-width INT] [--lang {verilog,sv,vhdl,c,all}]
        [--output PATH] [--module-name NAME]
        [--no-self-test] [--testbench] [--simulate] [--axi-stream]
```

| Flag | Default | Description |
|---|---|---|
| `--list-algorithms` | — | Print full algorithm catalog and exit |
| `--algorithm NAME` | — | Select named algorithm from catalog |
| `--poly HEX` | — | Custom polynomial (Williams normal form) |
| `--poly-koopman HEX` | — | Custom polynomial (Koopman notation) |
| `--width INT` | — | CRC width in bits (required for custom poly) |
| `--init HEX` | `0x0` | Initial register value |
| `--ref-in` | off | Reflect each input byte |
| `--ref-out` | off | Reflect final register |
| `--xor-out HEX` | `0x0` | Final XOR mask |
| `--check HEX` | auto | Check value (auto-computed if omitted) |
| `--data-width INT` | `8` | Data bits per clock cycle |
| `--lang` | `verilog` | Output language: `verilog`, `sv`, `vhdl`, `c`, `all` |
| `--output PATH` | stdout | Output file stem (extension added automatically) |
| `--module-name NAME` | auto | Override generated module/entity name |
| `--no-self-test` | off | Skip self-test |
| `--testbench` | off | Also generate self-checking testbench |
| `--simulate` | off | Auto-invoke iverilog+vvp or ghdl after generation |
| `--axi-stream` | off | Also generate AXI4-Stream wrapper (`<stem>_axis.*`) |

## Hardware Test (Arty A7-100T)

The [`hw_test/`](hw_test/) directory contains a complete Vivado flow that validates the generated
AXI4-Stream wrapper on a real Artix-7 FPGA using **JTAG-AXI** — no soft processor required.

### Requirements

- Vivado 2022.2+ (tested on 2025.2)
- Arty A7-100T connected via USB-JTAG
- `crczero` installed (`pip install -e .`)

### Steps

**1. Generate the RTL** (if not already in `sample_output/`):

```bash
crcZero --algorithm CRC-32/ISO-HDLC --data-width 32 --lang verilog \
        --output sample_output/crc_32_iso_hdlc_d32 --axi-stream
```

**2. Create the Vivado project** (Tcl console):

```tcl
source hw_test/tcl/create_project.tcl
```

**3. Synthesise, implement, generate bitstream** (Tcl console):

```tcl
source hw_test/tcl/run_impl.tcl
```

Typical runtime: ~5 min synthesis + ~4 min implementation.

**4. Program the FPGA and run the test** (Tcl console, Hardware Manager open):

```tcl
source hw_test/tcl/hw_test.tcl
```

The script programs the FPGA, resets the AXI FIFO, sends 21 test packets (including back-to-back
without FIFO reset) via JTAG-AXI, and compares each result against the software oracle:

```
=== CRC-32/ISO-HDLC D=32 Hardware Test ===
  Test                          Got           Expected      Result
------------------------------------------------------------------------
  b'1234'     1-word            0x9BE3E0A3    0x9BE3E0A3    PASS
  b'12345678' 2-word            0x9AE0DAAF    0x9AE0DAAF    PASS
  ...
  b'123456789012' 3-word        0x5D34EB96    0x5D34EB96    PASS
  back-to-back pkt A (1234)     0x9BE3E0A3    0x9BE3E0A3    PASS
  back-to-back pkt B (0000)     0x2144DF1C    0x2144DF1C    PASS
  long-1-beat                   0x1A5A601F    0x1A5A601F    PASS
  ...
  long-1024-beat                0x20C17E20    0x20C17E20    PASS
------------------------------------------------------------------------
  ALL 21/21 TESTS PASSED
```

A heartbeat LED (LD0) blinks at ~1.5 Hz on power-up to confirm the design is alive.
See [`hw_test/README.md`](hw_test/README.md) for full details.

## Roadmap

| Phase | Feature | Status |
|---|---|---|
| 3 | Registered / pipelined output (latency-1, configurable N-stage) | Planned |
| 4 | CRC checker module (`crc_ok` output, residue-based verification) | Planned |
| 5 | Byte-enable / TKEEP support (partial last word) | Planned |
| 6 | Wishbone B4 and APB3/APB4 memory-mapped wrappers | Planned |
| 7 | SVA formal verification assertions | Planned |
| 8 | PyPI publish (`pip install crczero`) | Completed |
| 9 | C reference implementation for MCU cross-validation | Completed |
| 10 | Web UI — browser-based online code generator | Planned |

## Contributing

Bug reports and pull requests welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Authors

**Leonardo Capossio** — bard0 design
[hello@bard0.com](mailto:hello@bard0.com)

## License

MIT — see [LICENSE](LICENSE).
