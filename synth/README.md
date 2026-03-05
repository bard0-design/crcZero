# Synthesis Tests

Runs the generated RTL through Yosys synthesis for multiple FPGA vendor targets.
No commercial tool installation required — uses `yowasp-yosys` (Yosys compiled
to WebAssembly).

## Install

```bash
pip install yowasp-yosys
```

## Usage

```bash
# All vendors (default: CRC-32/ISO-HDLC, D=8)
python synth/run_synth.py

# Single vendor
python synth/run_synth.py --vendor xilinx

# Multiple vendors
python synth/run_synth.py --vendor xilinx intel lattice

# Different algorithm / data width
python synth/run_synth.py --algorithm CRC-32/ISCSI --data-width 32

# Verbose: full stat output + cell-type breakdown
python synth/run_synth.py --verbose

# List all vendor targets
python synth/run_synth.py --list-vendors
```

## Vendor Targets

| Key | Display name | Family | Yosys command |
|---|---|---|---|
| `xilinx` | AMD/Xilinx | 7-series (XC7) | `synth_xilinx -family xc7` |
| `intel` | Altera/Intel | Cyclone V / Cyclone 10 GX (ALM) | `synth_intel_alm` |
| `lattice` | Lattice | ECP5 | `synth_lattice -family ecp5` |
| `microchip` | Microchip | PolarFire | `synth_microchip` |
| `efinix` | Efinix | Trion/Titanium | `synth_efinix` |
| `gowin` | Gowin | GW1N | `synth_gowin` |

Vendors whose Yosys synth target is not compiled into the installed
`yowasp-yosys` build are reported as `SKIP` rather than `FAIL`.

## Example Output

```
crcZero Synthesis Report
==============================================================
  Algorithm  : CRC-32/ISO-HDLC
  Data width : 8 bits
  Module     : crc_32_iso_hdlc_d8
  Yosys      : yowasp-yosys

  [xilinx    ] AMD/Xilinx / 7-series (XC7) ... PASS  LUTs=   62  cells=62
  [intel     ] Altera/Intel / Cyclone V / Cyclone 10 GX (ALM) ... PASS  LUTs=   60  cells=132
  [lattice   ] Lattice / ECP5 ... PASS  LUTs=   83  cells=93
  [microchip ] Microchip / PolarFire ... SKIP  (synth target not available in this Yosys build)
  [efinix    ] Efinix / Trion/Titanium ... SKIP  (synth target not available in this Yosys build)
  [gowin     ] Gowin / GW1N ... SKIP  (synth target not available in this Yosys build)

--------------------------------------------------------------
  Vendor          Family                       LUTs   Cells  Status
--------------------------------------------------------------
  AMD/Xilinx      7-series (XC7)                 62      62  PASS
  Altera/Intel    Cyclone V / Cyclone 10 GX (ALM)   60     132  PASS
  Lattice         ECP5                           83      93  PASS
  Microchip       PolarFire                                  SKIP
  Efinix          Trion/Titanium                             SKIP
  Gowin           GW1N                                       SKIP
--------------------------------------------------------------

  3 passed  3 skipped  0 failed
```

> LUT counts differ by vendor because each technology has a different native
> LUT input width (XC7 uses LUT6; ECP5/iCE40/Gowin use LUT4; Altera ALMs
> map differently).
>
> Vendors reported as `SKIP` have synth targets not compiled into the
> `yowasp-yosys` WebAssembly build. They would pass with a native Yosys build
> that includes those techlibs.
