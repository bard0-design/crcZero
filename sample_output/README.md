# Sample Output

Pre-generated RTL examples produced by crcZero.  These files are committed to
the repository so readers can inspect the generated HDL without installing the
tool.

## Combinatorial CRC cores

| File | Algorithm | Data width | Language |
|------|-----------|------------|----------|
| `crc_32_iso_hdlc_d8.v`   | CRC-32/ISO-HDLC (Ethernet FCS) | 8 bits  | Verilog-2001      |
| `crc_32_iso_hdlc_d8.sv`  | CRC-32/ISO-HDLC (Ethernet FCS) | 8 bits  | SystemVerilog     |
| `crc_32_iso_hdlc_d8.vhd` | CRC-32/ISO-HDLC (Ethernet FCS) | 8 bits  | VHDL-1993         |
| `crc_32_iso_hdlc_d32.v`  | CRC-32/ISO-HDLC (Ethernet FCS) | 32 bits | Verilog-2001      |
| `crc_32_iso_hdlc_d32.sv` | CRC-32/ISO-HDLC (Ethernet FCS) | 32 bits | SystemVerilog     |
| `crc_32_iso_hdlc_d32.vhd`| CRC-32/ISO-HDLC (Ethernet FCS) | 32 bits | VHDL-1993         |

## AXI4-Stream wrappers

| File | Algorithm | Data width | Language |
|------|-----------|------------|----------|
| `crc_32_iso_hdlc_d8_axis.v`   | CRC-32/ISO-HDLC (Ethernet FCS) | 8 bits  | Verilog-2001  |
| `crc_32_iso_hdlc_d8_axis.sv`  | CRC-32/ISO-HDLC (Ethernet FCS) | 8 bits  | SystemVerilog |
| `crc_32_iso_hdlc_d8_axis.vhd` | CRC-32/ISO-HDLC (Ethernet FCS) | 8 bits  | VHDL-1993     |
| `crc_32_iso_hdlc_d32_axis.v`  | CRC-32/ISO-HDLC (Ethernet FCS) | 32 bits | Verilog-2001  |
| `crc_32_iso_hdlc_d32_axis.sv` | CRC-32/ISO-HDLC (Ethernet FCS) | 32 bits | SystemVerilog |
| `crc_32_iso_hdlc_d32_axis.vhd`| CRC-32/ISO-HDLC (Ethernet FCS) | 32 bits | VHDL-1993     |

## AXI4-Stream testbenches

| File | Algorithm | Data width | Language |
|------|-----------|------------|----------|
| `crc_32_iso_hdlc_d8_axis_tb.v`  | CRC-32/ISO-HDLC | 8 bits  | Verilog-2001 |
| `crc_32_iso_hdlc_d32_axis_tb.v` | CRC-32/ISO-HDLC | 32 bits | Verilog-2001 |

Each AXI testbench runs 10 packets in two passes (LCG stall + no-stall) for
20 CRC checks total. All checks must report `PASS`.

## Regenerating

```sh
crcZero --algorithm CRC-32/ISO-HDLC --data-width  8 --lang all --output sample_output/crc_32_iso_hdlc_d8  --axi-stream
crcZero --algorithm CRC-32/ISO-HDLC --data-width 32 --lang all --output sample_output/crc_32_iso_hdlc_d32 --axi-stream
```

## Usage (Verilog-2001)

```verilog
// First word: set crc_in to the hardware reset value.
crc_in = 32'hFFFFFFFF;

// Feed each 8-bit (or 32-bit) word:
always @(posedge clk)
    crc_in <= crc_out;

// After the last word, the final CRC is:
final_crc = crc_out ^ 32'hFFFFFFFF;
```
