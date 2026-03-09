# Hardware Test — CRC-32/ISO-HDLC D=32 on Arty A7-100T

Tests the generated CRC AXI4-Stream wrapper on real silicon via JTAG-AXI.
No soft processor required — the Vivado Hardware Manager TCL console drives
all data transfers over the built-in JTAG port.

## Architecture

```
JTAG-AXI ──► SmartConnect ──► axi_fifo_mm_s (TX+RX, base 0x44A00000)
                                    │  AXI_STR_TXD (stream master)
                                    ▼
                       crc_32_iso_hdlc_d32_axis  (generated RTL)
                                    │  m_axis (stream master)
                                    ▼
                       axi_fifo_mm_s  AXI_STR_RXD (stream slave)

                       heartbeat  ──►  LD0 (blinks at ~1.5 Hz)
```

- **Write** data words to TDFD (one per transaction), then write the total
  byte length to TLR — the FIFO sends the packet with TLAST on the final beat.
- **Poll** RDFO until non-zero, drain all words, return the last.  The AXI-S
  wrapper emits one output beat per input beat; only the TLAST beat carries
  the final XOR'd CRC result.
- **Heartbeat LED** (LD0, pin H5) blinks at ~1.5 Hz from the 100 MHz clock
  to confirm the design is alive immediately after programming.

## Requirements

- Vivado 2022.2+ (tested on 2025.2)
- Arty A7-100T connected via USB-JTAG
- Python 3.9+ with `crczero` installed (`pip install -e .` from project root)

## Step 1 — Verify expected CRC values

```bash
python hw_test/sw/expected_crcs.py
```

This runs the software oracle and prints expected CRC values for each test
vector. The values are already hardcoded in `tcl/hw_test.tcl`; re-run this
if you modify the test vectors.

## Step 2 — Create the Vivado project

Open Vivado (GUI or batch) and source the project creation script:

```tcl
# In Vivado Tcl console:
source hw_test/tcl/create_project.tcl
```

This creates `hw_test/vivado/crc_hw_test.xpr` with:
- Clock wizard + proc_sys_reset
- JTAG-AXI master
- SmartConnect (AXI4 → AXI4-Lite)
- `axi_fifo_mm_s` at 0x44A00000 (TX + RX paths, 32-bit wide)
- `crc_32_iso_hdlc_d32_axis` module reference
- `heartbeat` module reference → LD0 (pin H5)

> **If the interface-level AXI-Stream connections fail** (Vivado cannot infer
> `s_axis`/`m_axis` from the module reference), open the block design, delete
> the two failing `connect_bd_intf_net` calls, uncomment the individual
> `connect_bd_net` block directly below them, and re-run `validate_bd_design`.

> **Vivado 2025.2 API notes** (handled automatically by the scripts):
> - `program_hw_devices` no longer accepts `-bitfile`; use `set_property PROGRAM.FILE`
> - `get_property DATA` on a read transaction returns `"0xDEADBEEF"` (with `0x` prefix)
> - `create_hw_axi_txn` `-size` flag is deprecated; omit it

## Step 3 — Synthesise, implement, generate bitstream

```tcl
source hw_test/tcl/run_impl.tcl
```

Typical runtime: ~5 min synthesis + ~4 min implementation on a modern PC.
Output: `hw_test/vivado/crc_hw_test.runs/impl_1/crc_test_wrapper.bit`

## Step 4 — Run hardware test

Connect the Arty board.  In Vivado Tcl console with **Hardware Manager** open:

```tcl
source hw_test/tcl/hw_test.tcl
```

The script:
1. Programs the FPGA with the bitstream
2. Resets the FIFO
3. Sends 8 known packets and reads back the CRC result for each
4. Sends 2 back-to-back packets (no FIFO reset between) to verify wrapper auto-reset
5. Compares against software oracle values and prints PASS/FAIL

Expected output:

```
=== CRC-32/ISO-HDLC D=32 Hardware Test ===
  Test                          Got             Expected        Result
------------------------------------------------------------------------
  b'1234'     1-word            0x9BE3E0A3      0x9BE3E0A3      PASS
  b'12345678' 2-word            0x9AE0DAAF      0x9AE0DAAF      PASS
  b'00000000' 1-word            0x2144DF1C      0x2144DF1C      PASS
  b'FFFFFFFF' 1-word            0xFFFFFFFF      0xFFFFFFFF      PASS
  b'DEADBEEF' 1-word            0x7C9CA35A      0x7C9CA35A      PASS
  b'AABBCCDD'*2 2-word          0x1F6284EB      0x1F6284EB      PASS
  b'01000000' 1-word            0x99F8B879      0x99F8B879      PASS
  b'123456789012' 3-word        0x5D34EB96      0x5D34EB96      PASS
  back-to-back pkt A (1234)     0x9BE3E0A3      0x9BE3E0A3      PASS
  back-to-back pkt B (0000)     0x2144DF1C      0x2144DF1C      PASS
------------------------------------------------------------------------
  ALL 10/10 TESTS PASSED
```

## Data word byte ordering

The AXI-Stream data port is 32 bits wide with reflected input (CRC-32/ISO-HDLC
has `ref_in=True`).  `data_in[7:0]` is the first byte fed into the LFSR:

```
hardware word 0x34333231  ≡  software bytes b"\x31\x32\x33\x34"  (="1234")
```

Packets must be a multiple of 4 bytes (no partial-word support without TKEEP).

## File layout

```
hw_test/
├── README.md
├── xdc/
│   └── arty_a7_100t.xdc       Constraints (clock E3, reset C2, LED H5)
├── rtl/
│   └── heartbeat.v            27-bit counter → LD0 blink at ~1.5 Hz
├── tcl/
│   ├── create_project.tcl     Create Vivado project + block design
│   ├── run_impl.tcl           Synthesis + implementation + bitgen
│   └── hw_test.tcl            JTAG-AXI test script
└── sw/
    └── expected_crcs.py       Software oracle — verify expected values
```
