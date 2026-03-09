# Changelog

All notable changes to crcZero are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [1.1.0] — 2026-03-09

### Added

- **Long packet hardware tests** — 11 new test vectors (1, 2, 3, 4, 8, 16, 32,
  64, 128, 512, 1024 beats) with deterministic data patterns; all 21/21 tests
  pass on Arty A7-100T hardware
- **Sub-byte CRC equation tests** — 30 new tests covering all 15 sub-byte CRC
  algorithms (CRC-3 through CRC-7) against software oracle and catalog check
  values
- **SystemVerilog compilation tests** — `test_compilation_sv.py` verifies
  `iverilog -g2012` compilation for 7 algorithm/width combinations
- **Author and license headers** — all 38 source files now carry author
  attribution and MIT license headers

### Fixed

- **`recv_crc` partial read race** — now uses RLR (receive length register)
  to wait for complete packets instead of polling RDFO occupancy
- **`send_packet` silent overflow** — checks TDFV vacancy before writing to
  prevent TX FIFO overflow
- **`run_impl.tcl` timing check** — reports WNS/WHS after implementation and
  warns on timing violations
- **`run_impl.tcl` Windows compatibility** — `exec nproc` replaced with
  cross-platform CPU count detection (`NUMBER_OF_PROCESSORS` fallback)

### Changed

- **FIFO depth** — TX and RX FIFO depth increased to 2048 words to support
  1024-beat packet tests
- **CI hardening** — zero-skip policy enforced; SystemVerilog compilation
  checks added to CI workflow
- **README** — condensed from ~790 to ~380 lines; improved structure
- **Test count**: 477 passing (was 447)

---

## [1.0.0] — 2026-03-07

### Added

- **AXI4-Stream wrappers** — clocked FSM-based wrappers in Verilog-2001,
  SystemVerilog, and VHDL-1993; 2-state FSM (ACCUM / WAIT_ACK) with full
  backpressure support (`generate_axi_stream_verilog/sv/vhdl()` API,
  `--axi-stream` CLI flag)
- **AXI4-Stream testbenches** — self-checking Verilog and VHDL testbenches
  (`generate_testbench_axi_verilog/vhdl()`); 10 packets × 2 passes
  (LCG stall + no-stall) = 20 CRC checks per run; VCDs saved to `tests/vcd/`
- **xsim support** — all four simulation integration tests (combinatorial
  Verilog/VHDL, AXI Verilog/VHDL) now fall back to Vivado
  `xvlog`/`xvhdl`/`xelab`/`xsim` when iverilog/ghdl are absent
- **VCD output for all tests** — combinatorial simulation tests save VCDs to
  `tests/vcd/` alongside AXI tests (22 VCDs total)
- **Expanded combinatorial testbenches** — 25 test vectors per run (9 from
  `b"123456789"` + 16 deterministic random), up from 17

- **Hardware test (`hw_test/`)** — Arty A7-100T validation via JTAG-AXI;
  no soft processor required; 6 CRC-32/ISO-HDLC D=32 test vectors verified
  on real silicon (6/6 PASS confirmed); heartbeat LED (LD0) on LD0 pin H5;
  Vivado 2025.2 compatible (`create_project.tcl`, `run_impl.tcl`, `hw_test.tcl`)

### Fixed

- **`m_axis_tlast` correctness** — all three AXI wrappers now clear
  `m_axis_tlast` (`m_tlast_r` in VHDL) in the same clock cycle that
  `m_axis_tvalid` is de-asserted, maintaining the AXI4-Stream invariant that
  `tlast` is only meaningful when `tvalid` is high

### Changed

- **Test count**: 447 passing (was 414); 0 skipped, 0 failed

---

## [0.1.0-alpha] — 2026-03-05

### Added

- **Verilog-2001 renderer** — synthesizable parallel CRC modules (`assign` statements)
- **SystemVerilog renderer** — `logic`-based equivalent
- **VHDL-1993 renderer** — pure combinatorial `signal` assignments
- **Verilog testbench renderer** — self-checking, iverilog-compatible, VCD waveform output
- **VHDL testbench renderer** — self-checking, ghdl-compatible, VCD waveform output
- **Algorithm catalog** — 80+ named CRC algorithms (CRC-8 through CRC-64), parameters sourced and verified against the [RevEng CRC catalogue](https://reveng.sourceforge.io/crc-catalogue/)
- **Custom polynomial support** — Williams normal form (`--poly`) and Koopman notation (`--poly-koopman`); check value auto-computed when not provided
- **Any data width** — 8, 16, 32, 64, or any positive integer bits per clock cycle
- **CLI** — `crcZero` entry point with `--algorithm`, `--poly`, `--lang`, `--data-width`, `--output`, `--testbench`, `--simulate`, `--list-algorithms` flags
- **Python API** — `CrcGenerator`, `Algorithm`, `catalog` importable from `crczero`
- **`--simulate` flag** — auto-invokes iverilog+vvp (Verilog) or ghdl (VHDL) after testbench generation
- **Test suite** — 365+ tests covering: software oracle, GF(2) equation derivation (full catalog), per-word random vectors, mixed ref modes, renderer structural correctness, CLI, testbench renderers, optional crcmod cross-validation, optional iverilog simulation
- **Zero runtime dependencies** — pure Python 3.9+, stdlib only

[1.1.0]: https://github.com/bard0-design/crcZero/releases/tag/v1.1.0
[1.0.0]: https://github.com/bard0-design/crcZero/releases/tag/v1.0.0
[0.1.0-alpha]: https://github.com/bard0-design/crcZero/releases/tag/v0.1.0
