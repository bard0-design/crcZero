# crcZero

[![CI](https://github.com/bard0-design/crcZero/actions/workflows/ci.yml/badge.svg)](https://github.com/bard0-design/crcZero/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Hardware Tested](https://img.shields.io/badge/hardware%20tested-Arty%20A7--100T-brightgreen)](hw_test/)

**Parallel CRC HDL code generator** — Verilog-2001, SystemVerilog, and VHDL-1993.

Generates synthesizable, parallel CRC modules from a built-in catalog
of 80+ named algorithms (reveng-verified), or from user-supplied polynomial parameters.
Includes self-checking testbenches, AXI4-Stream wrappers, and multi-vendor synthesis checks. Hardware tested on Arty A7-100T board.

Licensed under the **MIT License**.

---

## Features

- **Three output languages** — Verilog-2001, SystemVerilog, VHDL-1993
- **80+ named algorithms** — CRC-8 through CRC-64, parameters sourced from the
  [reveng CRC catalogue](https://reveng.sourceforge.io/crc-catalogue/), all
  check values verified
- **Custom polynomials** — normal (Williams) or Koopman notation; check value
  auto-computed when not provided
- **Any data width** — 8, 16, 32, 64, or any positive integer bits per clock
- **AXI4-Stream wrappers** — clocked wrapper with slave (data in) and master
  (CRC out) AXI-S interfaces, 2-state FSM, full backpressure support
- **Self-checking testbenches** — Verilog and VHDL (compatible with iverilog/vvp,
  ghdl, and Vivado xsim), 25 test vectors each, VCD waveform output saved to `tests/vcd/`
- **CLI + Python API** — use from the command line or import in any Python project
- **Zero runtime dependencies** — pure Python 3.9+, stdlib only
- **Synthesis-verified** — all outputs pass Yosys (`yowasp-yosys`) across
  AMD/Xilinx, Altera/Intel, Lattice, Microchip, Efinix, and Gowin targets,
  and GHDL (`--synth`); pure behavioural RTL also targets ASIC flows
- **Hardware-tested on silicon** — CRC-32/ISO-HDLC D=32 validated on Arty
  A7-100T (Artix-7 FPGA) via JTAG-AXI; 6/6 test vectors confirmed correct
  on real hardware (see [`hw_test/`](hw_test/))

---

## Installation

From source:

```bash
git clone https://github.com/bard0-design/crcZero
cd crcZero
pip install -e .
```

---

## Quick Start

### CLI

```bash
# List all 80+ built-in algorithms
crcZero --list-algorithms

# Generate Verilog for CRC-32 (Ethernet/ZIP)
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang verilog

# Generate all three languages to files
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang all --output crc32

# Generate with testbench
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang verilog \
        --output crc32 --testbench

# Generate and simulate immediately (requires iverilog in PATH)
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang verilog \
        --output crc32 --testbench --simulate

# Generate AXI4-Stream wrapper alongside the CRC core
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --lang verilog \
        --output crc32 --axi-stream
# Produces: crc32.v  crc32_axis.v

# Custom polynomial (normal form)
crcZero --poly 0x04C11DB7 --width 32 --init 0xFFFFFFFF \
        --ref-in --ref-out --xor-out 0xFFFFFFFF \
        --data-width 8 --lang verilog

# Custom polynomial (Koopman notation)
crcZero --poly-koopman 0x82608EDB --width 32 --init 0xFFFFFFFF \
        --ref-in --ref-out --xor-out 0xFFFFFFFF \
        --data-width 8 --lang sv
```

### Python API

```python
from crczero import CrcGenerator, catalog

# Named algorithm
gen = CrcGenerator(catalog["CRC-32/ISO-HDLC"], data_width=8)
assert gen.self_test()

print(gen.generate_verilog())
print(gen.generate_systemverilog())
print(gen.generate_vhdl())
print(gen.generate_testbench_verilog())
print(gen.generate_testbench_vhdl())

# AXI4-Stream wrappers
print(gen.generate_axi_stream_verilog())   # crc_32_iso_hdlc_d8_axis module
print(gen.generate_axi_stream_sv())        # SystemVerilog variant
print(gen.generate_axi_stream_vhdl())      # VHDL-1993 variant

# Custom polynomial
from crczero import Algorithm, poly_from_koopman

alg = Algorithm(
    name="MY-CRC32",
    width=32,
    poly=0x04C11DB7,
    init=0xFFFFFFFF,
    ref_in=True,
    ref_out=True,
    xor_out=0xFFFFFFFF,
    check=0xCBF43926,
    residue=0xDEBB20E3,
)
gen = CrcGenerator(alg, data_width=32)
print(gen.generate_verilog())

# From Koopman notation
poly = poly_from_koopman(0x82608EDB, width=32)  # → 0x04C11DB7
```

---

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

Example Verilog output (CRC-32/ISO-HDLC, 8-bit data):

```verilog
// ==============================================================
// crcZero -- CRC HDL Generator
// https://github.com/bard0-design/crcZero
//
// Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
// License    : MIT
//
// Algorithm  : CRC-32/ISO-HDLC
// CRC width  : 32 bits
// Polynomial : 0x04C11DB7
// Init       : 0xFFFFFFFF
// RefIn      : True
// RefOut     : True
// XorOut     : 0xFFFFFFFF
// Check      : 0xCBF43926
// Data width : 8 bits
// Generated  : 2026-03-05T08:00:00Z
//
// Usage:
//   - Set crc_in = 32'hFFFFFFFF for the first word.
//   - Chain crc_out -> crc_in for subsequent words.
//   - Final CRC = crc_out ^ 32'hFFFFFFFF.
// ==============================================================
module crc_32_iso_hdlc_d8 (
    input  [7:0]  data_in,
    input  [31:0] crc_in,
    output [31:0] crc_out
);
    assign crc_out[0] = crc_in[1] ^ crc_in[2] ^ crc_in[8] ^ ...;
    // ...
endmodule
```

---

## Instantiation Examples

These examples show how to wire the generated CRC module into a larger RTL design.
All examples use CRC-32/ISO-HDLC with 8-bit data (`crc_32_iso_hdlc_d8`).

### Verilog-2001

```verilog
module eth_tx (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid,
    input  wire [7:0]  data,
    output reg  [31:0] fcs
);
    reg  [31:0] crc_reg;
    wire [31:0] crc_next;

    // Instantiate the generated CRC module
    crc_32_iso_hdlc_d8 u_crc (
        .data_in (data),
        .crc_in  (crc_reg),
        .crc_out (crc_next)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            crc_reg <= 32'hFFFFFFFF;   // INIT
        else if (valid)
            crc_reg <= crc_next;
    end

    // Final CRC appended to frame: XOR with 0xFFFFFFFF, byte-reverse for wire order
    assign fcs = ~{crc_reg[7:0], crc_reg[15:8], crc_reg[23:16], crc_reg[31:24]};
endmodule
```

### SystemVerilog

```systemverilog
module eth_tx (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        valid,
    input  logic [7:0]  data,
    output logic [31:0] fcs
);
    logic [31:0] crc_reg, crc_next;

    crc_32_iso_hdlc_d8 u_crc (
        .data_in (data),
        .crc_in  (crc_reg),
        .crc_out (crc_next)
    );

    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) crc_reg <= 32'hFFFF_FFFF;
        else if (valid) crc_reg <= crc_next;

    assign fcs = ~{crc_reg[7:0], crc_reg[15:8], crc_reg[23:16], crc_reg[31:24]};
endmodule
```

### VHDL-1993

```vhdl
library ieee;
use ieee.std_logic_1164.all;

entity eth_tx is
    port (
        clk   : in  std_logic;
        rst_n : in  std_logic;
        valid : in  std_logic;
        data  : in  std_logic_vector(7 downto 0);
        fcs   : out std_logic_vector(31 downto 0)
    );
end eth_tx;

architecture rtl of eth_tx is

    component crc_32_iso_hdlc_d8
        port (
            data_in : in  std_logic_vector(7 downto 0);
            crc_in  : in  std_logic_vector(31 downto 0);
            crc_out : out std_logic_vector(31 downto 0)
        );
    end component;

    signal crc_reg  : std_logic_vector(31 downto 0) := (others => '1');
    signal crc_next : std_logic_vector(31 downto 0);

begin

    u_crc : crc_32_iso_hdlc_d8
        port map (
            data_in => data,
            crc_in  => crc_reg,
            crc_out => crc_next
        );

    process (clk, rst_n)
    begin
        if rst_n = '0' then
            crc_reg <= x"FFFFFFFF";      -- INIT
        elsif rising_edge(clk) then
            if valid = '1' then
                crc_reg <= crc_next;
            end if;
        end if;
    end process;

    -- Final FCS: XOR_OUT applied, byte-reversed for wire order
    fcs <= not (crc_reg(7 downto 0) & crc_reg(15 downto 8)
              & crc_reg(23 downto 16) & crc_reg(31 downto 24));

end rtl;
```

### Multi-word chaining (any language)

The module is stateless (purely combinatorial). The accumulation register lives
in the parent design. For a stream of N words:

```
clock 0:  crc_in = INIT,     data_in = word[0]  →  crc_out = state_1
clock 1:  crc_in = state_1,  data_in = word[1]  →  crc_out = state_2
...
clock N-1: crc_in = state_N-1, data_in = word[N-1] → crc_out = state_N
final CRC = state_N XOR XOR_OUT
```

For CRC-32/ISO-HDLC specifically: `INIT = 0xFFFFFFFF`, `XOR_OUT = 0xFFFFFFFF`,
so the final CRC is `~crc_reg`. Byte order on the wire follows the protocol
specification (Ethernet sends LSB-first).

---

## AXI4-Stream Wrapper

The `--axi-stream` flag generates a clocked wrapper around the combinatorial
CRC core that speaks AXI4-Stream on both sides.

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
| `m_axis_tlast` | out | 1 | `1` when `m_axis_tvalid` is high (single-beat CRC result) |

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
# Verilog core + wrapper
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --output crc32 \
        --lang verilog --axi-stream
# Produces: crc32.v  crc32_axis.v

# All three languages
crcZero --algorithm CRC-32/ISO-HDLC --data-width 8 --output crc32 \
        --lang all --axi-stream
# Produces: crc32.v crc32_axis.v  crc32.sv crc32_axis.sv  crc32.vhd crc32_axis.vhd
```

```python
gen = CrcGenerator(catalog["CRC-32/ISO-HDLC"], data_width=8)
wrapper_v   = gen.generate_axi_stream_verilog()
wrapper_sv  = gen.generate_axi_stream_sv()
wrapper_vhd = gen.generate_axi_stream_vhdl()
```

The wrapper instantiates the CRC core by name — compile or analyse both files together:

```bash
# Verilog (iverilog)
iverilog crc32.v crc32_axis.v your_design.v ...

# VHDL (ghdl)
ghdl -a --std=93 crc32.vhd crc32_axis.vhd ...
```

A self-checking AXI4-Stream testbench is also generated by the API
(`gen.generate_testbench_axi_verilog()`, `gen.generate_testbench_axi_vhdl()`).
The testbench runs 10 packets through the wrapper in two passes: one with LCG
pseudorandom backpressure stalls and one with no stalls (20 CRC checks total).
All VCDs are saved to `tests/vcd/` for waveform inspection.

---

## Custom Polynomials

### Normal (Williams) notation

The `poly` parameter follows the Williams model: the generator polynomial
with the leading `x^N` term omitted (MSB implicit). For example, the standard
CRC-32 polynomial `x^32 + x^26 + x^23 + ... + 1` is represented as `0x04C11DB7`.

```bash
crcZero --poly 0x04C11DB7 --width 32 --init 0xFFFFFFFF \
        --ref-in --ref-out --xor-out 0xFFFFFFFF \
        --data-width 8 --lang verilog
```

### Koopman notation

Koopman notation omits the implicit trailing `+1` term and keeps the leading
coefficient:

| Notation | CRC-32 value |
|---|---|
| Normal (Williams) | `0x04C11DB7` |
| Koopman | `0x82608EDB` |

```bash
crcZero --poly-koopman 0x82608EDB --width 32 --init 0xFFFFFFFF \
        --ref-in --ref-out --xor-out 0xFFFFFFFF \
        --data-width 8 --lang verilog
```

The check value is auto-computed when `--check` is not supplied.

### Python helpers

```python
from crczero import poly_from_koopman, poly_to_koopman

normal  = poly_from_koopman(0x82608EDB, width=32)  # → 0x04C11DB7
koopman = poly_to_koopman(0x04C11DB7, width=32)    # → 0x82608EDB
```

---

## Testbench and Simulation

### Verilog testbench (iverilog + vvp)

```bash
# Generate DUT + testbench
crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang verilog --testbench
# Produces: crc32.v  crc32_tb.v

# Simulate manually
iverilog -o crc32_tb crc32.v crc32_tb.v
vvp crc32_tb
# Produces: crc32_tb.vcd  (open with GTKWave)

# Or let crcZero do it
crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang verilog \
        --testbench --simulate
```

Alternatively, compile with Vivado's `xvlog`/`xelab`/`xsim` — the testbench is
compatible with all three simulators.

### VHDL testbench (ghdl)

```bash
# Generate DUT + testbench
crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang vhdl --testbench
# Produces: crc32.vhd  crc32_tb.vhd

# Simulate manually
ghdl -a --std=93 crc32.vhd crc32_tb.vhd
ghdl -e --std=93 crc32_iso_hdlc_d8_tb
ghdl -r --std=93 crc32_iso_hdlc_d8_tb --vcd=crc32_tb.vcd
# Produces: crc32_tb.vcd  (open with GTKWave)

# Or let crcZero do it
crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang vhdl \
        --testbench --simulate
```

Alternatively, compile with Vivado's `xvhdl`/`xelab`/`xsim`.

The testbench applies 25 test vectors (byte-by-byte decomposition of
`b"123456789"` + 16 deterministic random words) and reports PASS/FAIL per vector.
It exits with a non-zero status if any vector fails.

---

## Verification

### Python self-test (check value)

Every algorithm in the catalog has a known `check` value — the CRC of the
ASCII string `b"123456789"`. The generator verifies this on construction:

```python
from crczero import CrcGenerator, catalog

gen = CrcGenerator(catalog["CRC-32/ISO-HDLC"], data_width=8)
assert gen.self_test()  # True = software oracle matches catalog check value
```

### Run the unit tests

```bash
pip install -e ".[dev]"
pytest tests/
# 447 tests — covers catalog check values, equation derivation,
# renderer output structure, CLI flags, testbench renderers,
# AXI4-Stream wrapper structure, and full RTL simulation
```

### Synthesis check — multi-vendor (Yosys)

The `synth/` directory contains a synthesis runner that tests the generated RTL
against AMD/Xilinx, Altera/Intel, Lattice, Microchip, Efinix, and Gowin in one
command using `yowasp-yosys` (no native tool installation required):

```bash
pip install yowasp-yosys

python synth/run_synth.py                          # all six vendors
python synth/run_synth.py --vendor xilinx lattice  # subset
python synth/run_synth.py --algorithm CRC-32/ISCSI --data-width 32
python synth/run_synth.py --list-vendors           # show available targets
```

Example results for CRC-32/ISO-HDLC, D=8 (via `yowasp-yosys`):

| Vendor | Family | LUTs |
|---|---|---:|
| AMD/Xilinx | 7-series (XC7), LUT6 | 62 |
| Altera/Intel | Cyclone V / Cyclone 10 GX (ALM) | 60 |
| Lattice | ECP5, LUT4 | 83 |

Vendors whose synth target is not compiled into the `yowasp-yosys`
WebAssembly build are reported as `SKIP`; they pass with a native Yosys build.

The generated RTL is **purely combinatorial XOR logic** and is not
FPGA-specific.  The same Verilog / VHDL files synthesise equally well for
**ASIC flows** (standard-cell, gate-array) — the output is standard
behavioural RTL with no vendor primitives, no DSP blocks, no I/O buffers,
and no clock resources.

```bash
# Manual check with generic technology-independent synthesis
pip install yowasp-yosys

crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang verilog

yowasp-yosys -p "read_verilog crc32.v; synth -top crc_32_iso_hdlc_d8; stat"
# Cells will be $_XOR_, $_XNOR_, $_NOT_ only (pure combinatorial logic)
```

### Synthesis check — VHDL (GHDL)

```bash
# Install GHDL: https://ghdl.github.io/ghdl/

crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang vhdl

ghdl --synth crc32.vhd -e crc_32_iso_hdlc_d8
# Outputs a gate-level VHDL netlist — zero errors means synthesizable
```

### Parse/elaborate check — Verilog (iverilog)

```bash
# Install Icarus Verilog: https://steveicarus.github.io/iverilog/

crcZero --algorithm CRC-32/ISO-HDLC --output crc32 --lang verilog

iverilog -t null -g2001 crc32.v
# Exit code 0 = clean parse and elaboration
```

---

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

---

## CLI Reference

```
usage: crcZero [--list-algorithms]
               [--algorithm NAME | --poly HEX | --poly-koopman HEX]
               [--width INT] [--init HEX] [--ref-in] [--ref-out]
               [--xor-out HEX] [--check HEX] [--residue HEX] [--name STR]
               [--data-width INT] [--lang {verilog,sv,vhdl,all}]
               [--output PATH] [--module-name NAME]
               [--no-self-test] [--testbench] [--simulate] [--axi-stream]
```

| Flag | Default | Description |
|---|---|---|
| `--list-algorithms` | — | Print full algorithm catalog and exit |
| `--algorithm NAME` | — | Select named algorithm from catalog |
| `--poly HEX` | — | Custom polynomial (Williams normal form) |
| `--poly-koopman HEX` | — | Custom polynomial (Koopman notation) |
| `--width INT` | — | CRC width in bits (required for custom) |
| `--init HEX` | `0x0` | Initial register value |
| `--ref-in` | off | Reflect each input byte |
| `--ref-out` | off | Reflect final register |
| `--xor-out HEX` | `0x0` | Final XOR mask |
| `--check HEX` | auto | Check value (auto-computed if omitted) |
| `--data-width INT` | `8` | Data bits per clock cycle |
| `--lang` | `verilog` | Output language: `verilog`, `sv`, `vhdl`, `all` |
| `--output PATH` | stdout | Output file stem (extension added automatically) |
| `--module-name NAME` | auto | Override generated module/entity name |
| `--no-self-test` | off | Skip self-test |
| `--testbench` | off | Also generate self-checking testbench |
| `--simulate` | off | Auto-invoke iverilog+vvp or ghdl after generation |
| `--axi-stream` | off | Also generate AXI4-Stream wrapper (`<stem>_axis.*`) |

---

## How It Works

crcZero uses **GF(2) iterative symbolic unrolling** to derive, for each
CRC output bit, the exact set of `crc_in` and `data_in` bits that must be
XORed together.

A state vector of N bitmasks (one per CRC register bit) is maintained.
Each bitmask tracks which input bits contribute to that state bit. Starting
from `state[i] = (1 << i)` (identity: `crc_out[i] = crc_in[i]`), D data
bits are fed one-by-one through the LFSR update rule symbolically.

After D iterations, the state encodes the complete parallel combinatorial
equations as XOR trees, which the renderers emit directly as HDL assigns.

This approach:
- Requires no matrix exponentiation
- Handles any CRC width and data width
- Correctly handles both reflected (`ref_in == ref_out == True`) and
  normal (`ref_in == ref_out == False`) LFSR modes

---

## Resource Usage

All generated logic is **purely combinatorial** — a tree of 2-input XOR gates,
one assign statement per output bit.  No registers, no LUT RAM, no carry chains.
Synthesis maps directly to XOR primitives on any technology.

The table below shows the minimum number of 2-input XOR operations required
per clock cycle (computed analytically from the GF(2) equations; actual gate
count after synthesis may be lower due to sharing):

### 32-bit CRC algorithms

| Algorithm | D=8 | D=16 | D=32 | D=64 |
|---|---:|---:|---:|---:|
| CRC-32/ISO-HDLC (Ethernet FCS) | 220 | 414 | 872 | 1390 |
| CRC-32/MPEG-2 (DVB, MPEG)      | 220 | 414 | 872 | 1390 |
| CRC-32/BZIP2                   | 220 | 414 | 872 | 1390 |
| CRC-32C / ISCSI (Castagnoli)   | 268 | 528 | 1036 | 1470 |

CRC-32/ISO-HDLC, CRC-32/MPEG-2, and CRC-32/BZIP2 share the same polynomial
(`0x04C11DB7`) and therefore produce identical XOR counts; they differ only in
`init`, `ref_in`/`ref_out`, and `xor_out`.  CRC-32C uses a denser polynomial
(`0x1EDC6F41`) with ~20% more XOR gates.

### Other widths

| Algorithm | D=8 | D=16 | D=32 | D=64 |
|---|---:|---:|---:|---:|
| CRC-8/SMBUS   | 44  | —   | —    | —    |
| CRC-16/ARC    | 68  | 128 | —    | —    |
| CRC-16/IBM-3740 | 56 | 160 | —   | —    |
| CRC-64/GO-ISO  | 56  | —  | 224  | 468  |
| CRC-64/ECMA-182| 524 | —  | 2048 | 4004 |

> **Rule of thumb:** doubling the data width roughly doubles the XOR count.
> On a typical AMD/Xilinx 7-series or Altera/Intel Cyclone V FPGA each 6-input LUT can absorb a 6-input XOR,
> so the LUT count is approximately `total_xors / 5`.

---

## Hardware Test (Arty A7-100T)

The [`hw_test/`](hw_test/) directory contains a complete Vivado flow that
validates the generated AXI4-Stream wrapper on a real Artix-7 FPGA using
**JTAG-AXI** — no soft processor required.

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

The script programs the FPGA, resets the AXI FIFO, sends 6 known packets
via JTAG-AXI, and compares each result against the software oracle:

```
=== CRC-32/ISO-HDLC D=32 Hardware Test ===
  Test                          Got           Expected      Result
------------------------------------------------------------------------
  b'1234'     1-word            0x9BE3E0A3    0x9BE3E0A3    PASS
  b'12345678' 2-word            0x9AE0DAAF    0x9AE0DAAF    PASS
  b'00000000' 1-word            0x2144DF1C    0x2144DF1C    PASS
  b'FFFFFFFF' 1-word            0xFFFFFFFF    0xFFFFFFFF    PASS
  b'DEADBEEF' 1-word            0x7C9CA35A    0x7C9CA35A    PASS
  b'AABBCCDD'*2 2-word          0x1F6284EB    0x1F6284EB    PASS
------------------------------------------------------------------------
  ALL 6/6 TESTS PASSED
```

A heartbeat LED (LD0) blinks at ~1.5 Hz on power-up to confirm the design
is alive. See [`hw_test/README.md`](hw_test/README.md) for full details.

---

## Roadmap

The current release covers combinatorial CRC cores, AXI4-Stream wrappers,
and self-checking testbenches. Planned additions, in priority order:

### 1. Registered / pipelined output

Two optional architecture variants:

- **Registered (latency 1):** adds a single flip-flop stage on `crc_out`,
  breaking the long XOR chain and improving timing closure at high clock rates.
- **Pipelined (latency N):** configurable pipeline depth with automatic
  retiming; valid/ready handshake preserved throughout.

Useful when `total_xors / 5` LUTs in series exceeds the target Fmax budget.

### 2. Byte-enable / partial-word support (AXI-S TKEEP)

A `byte_en[D/8-1:0]` strobe input (and AXI4-Stream `tkeep` support) that
masks inactive bytes in the last word of a frame.  Eliminates the need to
pad short messages to a full word boundary before feeding the CRC engine.

---

## Authors

**Leonardo Capossio** — bard0 design
[hello@bard0.com](mailto:hello@bard0.com)

---

## License

MIT — see [LICENSE](LICENSE).
