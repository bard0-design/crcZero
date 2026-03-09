#!/usr/bin/env python3
# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Synthesis runner — test crcZero RTL against multiple FPGA vendor targets.

Uses yowasp-yosys (Yosys compiled to WebAssembly) for all vendors.
No native tool installation required:

    pip install yowasp-yosys

Usage:
    python synth/run_synth.py                                # all vendors
    python synth/run_synth.py --vendor xilinx                # single
    python synth/run_synth.py --vendor xilinx intel lattice  # multiple
    python synth/run_synth.py --list-vendors
    python synth/run_synth.py --algorithm CRC-32/ISCSI --data-width 32
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Vendor definitions
# ---------------------------------------------------------------------------

@dataclass
class VendorConfig:
    display_name: str       # e.g. "AMD/Xilinx"
    family: str             # e.g. "7-series (XC7)"
    synth_cmd: str          # Yosys synthesis command + flags
    lut_cells: list[str]    # cell names counted as LUTs in stat output


VENDORS: dict[str, VendorConfig] = {
    "xilinx": VendorConfig(
        display_name="AMD/Xilinx",
        family="7-series (XC7)",
        # -family xc7 explicitly selects Artix-7 / Kintex-7 / Virtex-7 cells
        synth_cmd="synth_xilinx -flatten -nosrl -noclkbuf -noiopad -family xc7",
        lut_cells=["LUT6", "LUT5", "LUT4", "LUT3", "LUT2", "LUT1"],
    ),
    "intel": VendorConfig(
        display_name="Altera/Intel",
        family="Cyclone V / Cyclone 10 GX (ALM)",
        # synth_intel_alm targets Cyclone V / Cyclone 10 GX adaptive logic modules
        # using the Mistral backend; synth_intel (LE-based) lacks techlib in yowasp
        synth_cmd="synth_intel_alm",
        lut_cells=["MISTRAL_ALUT2", "MISTRAL_ALUT3", "MISTRAL_ALUT4", "MISTRAL_ALUT5", "MISTRAL_ALUT6"],
    ),
    "lattice": VendorConfig(
        display_name="Lattice",
        family="ECP5",
        # synth_lattice is the generic Lattice command; -family ecp5 selects ECP5
        synth_cmd="synth_lattice -flatten -family ecp5",
        lut_cells=["LUT4"],
    ),
    "microchip": VendorConfig(
        display_name="Microchip",
        family="PolarFire",
        synth_cmd="synth_microchip -flatten",
        lut_cells=["CFG4", "CFG3", "CFG2", "CFG1"],
    ),
    "efinix": VendorConfig(
        display_name="Efinix",
        family="Trion/Titanium",
        synth_cmd="synth_efinix -flatten",
        lut_cells=["EFX_LUT4"],
    ),
    "gowin": VendorConfig(
        display_name="Gowin",
        family="GW1N",
        synth_cmd="synth_gowin -flatten -noalu",
        lut_cells=["LUT4"],
    ),
}

VENDOR_ORDER = ["xilinx", "intel", "lattice", "microchip", "efinix", "gowin"]

# ---------------------------------------------------------------------------
# Synthesis helpers
# ---------------------------------------------------------------------------

def _find_yosys() -> str | None:
    """Find yowasp-yosys or yosys executable, including Python Scripts directories."""
    found = shutil.which("yowasp-yosys") or shutil.which("yosys")
    if found:
        return found
    # Check alongside the running Python interpreter (common on Windows)
    import sysconfig
    scripts = sysconfig.get_path("scripts")
    if scripts:
        for name in ("yowasp-yosys", "yowasp-yosys.exe", "yosys", "yosys.exe"):
            candidate = Path(scripts) / name
            if candidate.exists():
                return str(candidate)
    return None


def _run_yosys(yosys: str, verilog_file: str, synth_cmd: str) -> tuple[bool, str]:
    """Run yosys with the given synth command. Returns (success, stdout+stderr)."""
    # Yosys requires forward slashes even on Windows
    verilog_file = verilog_file.replace("\\", "/")
    script = f"read_verilog {verilog_file}; {synth_cmd}; stat"
    result = subprocess.run(
        [yosys, "-p", script],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def _parse_cells(output: str, lut_cells: list[str]) -> dict:
    """Parse yosys stat output into cell counts.

    Handles two formats emitted by yosys stat:

    Standard (generic stat):
        Number of cells:    221
          LUT6              185
          LUT5               18

    Tech-mapped (stat after vendor synth):
          62 cells
          18   LUT2
           8   LUT3
    """
    cells: dict[str, int] = {}
    in_cells = False
    tech_mode = False  # True when count precedes name

    # Use only the last stat block (most refined, after full mapping)
    last_stat_start = output.rfind("Printing statistics.")
    if last_stat_start != -1:
        output = output[last_stat_start:]

    for line in output.splitlines():
        # Standard format: "Number of cells: N"
        if "Number of cells:" in line:
            in_cells = True
            tech_mode = False
            m = re.search(r"Number of cells:\s+(\d+)", line)
            if m:
                cells["__total__"] = int(m.group(1))
            continue

        # Tech-mapped format: "   N cells"
        m_tech = re.match(r"^\s+(\d+) cells\s*$", line)
        if m_tech:
            in_cells = True
            tech_mode = True
            cells["__total__"] = int(m_tech.group(1))
            continue

        if in_cells:
            if tech_mode:
                # "   N   CELL_NAME"
                m = re.match(r"^\s+(\d+)\s{3,}(\S+)\s*$", line)
                if m:
                    cells[m.group(2)] = int(m.group(1))
                elif line.strip() == "":
                    in_cells = False
            else:
                # "   CELL_NAME   N"
                m = re.match(r"^\s{4,}(\S+)\s+(\d+)\s*$", line)
                if m:
                    cells[m.group(1)] = int(m.group(2))
                elif line.strip() == "" or (line and not line[0].isspace()):
                    in_cells = False

    lut_count = sum(cells.get(c, 0) for c in lut_cells)
    total = cells.get("__total__", sum(v for k, v in cells.items() if not k.startswith("__")))
    return {
        "cells": {k: v for k, v in cells.items() if not k.startswith("__")},
        "total": total,
        "luts": lut_count,
    }


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SynthResult:
    vendor_key: str
    vendor: VendorConfig
    status: str          # "PASS", "FAIL", "SKIP", "ERROR"
    luts: int = 0
    total_cells: int = 0
    cell_detail: dict[str, int] = field(default_factory=dict)
    note: str = ""


# ---------------------------------------------------------------------------
# Main synthesis runner
# ---------------------------------------------------------------------------

def run_vendor(
    vendor_key: str,
    vendor: VendorConfig,
    verilog_file: str,
    yosys: str,
    verbose: bool,
) -> SynthResult:
    success, output = _run_yosys(yosys, verilog_file, vendor.synth_cmd)

    # Detect unknown command (synth target not compiled into this yosys build)
    if not success and re.search(
        r"No such command|unknown command|ERROR.*synth_", output, re.IGNORECASE
    ):
        return SynthResult(
            vendor_key, vendor, "SKIP",
            note="synth target not available in this Yosys build",
        )

    if not success:
        return SynthResult(vendor_key, vendor, "FAIL", note="yosys non-zero exit")

    parsed = _parse_cells(output, vendor.lut_cells)

    if verbose:
        print(f"\n{'-' * 60}")
        print(f"  {vendor.display_name} — {vendor.family}")
        print(f"{'-' * 60}")
        # Print cell detail lines from stat
        in_stat = False
        for line in output.splitlines():
            if "=== " in line and "===" in line:
                in_stat = True
            if in_stat:
                print(" ", line)
            if in_stat and line.strip() == "" and "===" not in line:
                pass  # keep printing

    return SynthResult(
        vendor_key=vendor_key,
        vendor=vendor,
        status="PASS",
        luts=parsed["luts"],
        total_cells=parsed["total"],
        cell_detail=parsed["cells"],
    )


def run_synth(
    vendor_keys: list[str],
    algorithm: str,
    data_width: int,
    verbose: bool,
) -> int:
    """Run synthesis for all requested vendors. Returns exit code."""

    # Generate Verilog
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from crczero.catalog import CATALOG
        from crczero.equations import derive_equations
        from crczero.renderers.verilog import VerilogRenderer

        if algorithm not in CATALOG:
            print(f"error: unknown algorithm '{algorithm}'", file=sys.stderr)
            print(f"  Run: python synth/run_synth.py --list-vendors", file=sys.stderr)
            return 1

        alg = CATALOG[algorithm]
        eqs = derive_equations(alg, data_width)
        module_name = VerilogRenderer().default_name(alg, data_width)
        verilog_code = VerilogRenderer().render(eqs, alg, data_width)

    except ImportError as e:
        print(f"error: could not import crczero — run from project root: {e}", file=sys.stderr)
        return 1

    yosys = _find_yosys()
    if not yosys:
        print("error: yowasp-yosys not found in PATH.", file=sys.stderr)
        print("  Install with: pip install yowasp-yosys", file=sys.stderr)
        return 1

    print(f"crcZero Synthesis Report")
    print(f"{'=' * 62}")
    print(f"  Algorithm  : {algorithm}")
    print(f"  Data width : {data_width} bits")
    print(f"  Module     : {module_name}")
    print(f"  Yosys      : {yosys}")
    print()

    results: list[SynthResult] = []

    # yowasp-yosys (WASM sandbox) only mounts the CWD; /tmp is invisible to it.
    # Create the temp dir inside CWD so Yosys can always find the file.
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmpdir:
        verilog_file = str(Path(tmpdir) / f"{module_name}.v")
        Path(verilog_file).write_text(verilog_code)

        for key in vendor_keys:
            vendor = VENDORS[key]
            print(f"  [{key:10s}] {vendor.display_name} / {vendor.family} ...", end="", flush=True)
            result = run_vendor(key, vendor, verilog_file, yosys, verbose)
            results.append(result)

            if result.status == "PASS":
                lut_str = str(result.luts) if result.luts > 0 else "n/a"
                print(f" PASS  LUTs={lut_str:>5}  cells={result.total_cells}")
            elif result.status == "SKIP":
                print(f" SKIP  ({result.note})")
            else:
                print(f" {result.status}  ({result.note})")

    # Summary table
    print()
    print(f"{'-' * 62}")
    col = f"  {'Vendor':<14}  {'Family':<26}  {'LUTs':>5}  {'Cells':>6}  Status"
    print(col)
    print(f"{'-' * 62}")
    for r in results:
        if r.status == "PASS":
            lut_str = str(r.luts) if r.luts > 0 else "  n/a"
            print(
                f"  {r.vendor.display_name:<14}  {r.vendor.family:<26}  "
                f"{lut_str:>5}  {r.total_cells:>6}  PASS"
            )
        else:
            print(
                f"  {r.vendor.display_name:<14}  {r.vendor.family:<26}  "
                f"{'':>5}  {'':>6}  {r.status}"
            )
    print(f"{'-' * 62}")

    if verbose:
        print()
        for r in results:
            if r.status == "PASS" and r.cell_detail:
                print(f"  {r.vendor.display_name} / {r.vendor.family} cells:")
                for cell, count in sorted(r.cell_detail.items(), key=lambda x: -x[1]):
                    print(f"    {cell:<20} {count}")
                print()

    failed = [r for r in results if r.status == "FAIL"]
    passed = [r for r in results if r.status == "PASS"]
    skipped = [r for r in results if r.status == "SKIP"]

    print(f"\n  {len(passed)} passed  {len(skipped)} skipped  {len(failed)} failed")
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run crcZero RTL through multiple FPGA vendor synthesis flows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.strip(),
    )
    parser.add_argument(
        "--vendor",
        nargs="+",
        metavar="VENDOR",
        help="Vendor(s) to target, or 'all'. Default: all.",
    )
    parser.add_argument(
        "--algorithm",
        default="CRC-32/ISO-HDLC",
        metavar="NAME",
        help="Algorithm name from catalog (default: CRC-32/ISO-HDLC).",
    )
    parser.add_argument(
        "--data-width",
        type=int,
        default=8,
        metavar="N",
        help="Data width in bits (default: 8).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print full yosys stat output and cell-type breakdown.",
    )
    parser.add_argument(
        "--list-vendors",
        action="store_true",
        help="List available vendor targets and exit.",
    )

    args = parser.parse_args()

    if args.list_vendors:
        print(f"{'Key':<12}  {'Display name':<16}  {'Family':<30}  Yosys command")
        print("-" * 90)
        for key in VENDOR_ORDER:
            v = VENDORS[key]
            print(f"{key:<12}  {v.display_name:<16}  {v.family:<30}  {v.synth_cmd}")
        sys.exit(0)

    # Resolve vendor list
    if not args.vendor or args.vendor == ["all"]:
        vendor_keys = VENDOR_ORDER
    else:
        unknown = [v for v in args.vendor if v not in VENDORS]
        if unknown:
            print(f"error: unknown vendor(s): {', '.join(unknown)}", file=sys.stderr)
            print(f"  Available: {', '.join(VENDOR_ORDER)}", file=sys.stderr)
            sys.exit(1)
        vendor_keys = args.vendor

    sys.exit(run_synth(vendor_keys, args.algorithm, args.data_width, args.verbose))


if __name__ == "__main__":
    main()
