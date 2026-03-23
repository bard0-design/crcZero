# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Command-line interface for crcZero."""

from __future__ import annotations

import argparse
import difflib
import shutil
import subprocess
import sys
from pathlib import Path

from crczero.algorithm import Algorithm
from crczero.catalog import CATALOG
from crczero.generator import CrcGenerator


def _parse_hex(value: str, param_name: str) -> int:
    """Parse a hex or decimal integer string, raising ArgumentTypeError on failure."""
    try:
        return int(value, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid value for {param_name}: '{value}'. "
            "Use a hex literal (e.g. 0x04C11DB7) or a decimal integer."
        )


def _suggest(name: str) -> list[str]:
    """Return close matches to 'name' from the catalog."""
    return difflib.get_close_matches(name, CATALOG.keys(), n=3, cutoff=0.4)


def _list_algorithms() -> None:
    """Print the full algorithm catalog as a table."""
    header = f"{'Algorithm':<35} {'Width':>5}  {'Poly':<18}  {'RefIn':>5}  {'RefOut':>6}  {'Check'}"
    print(header)
    print("-" * len(header))
    for name, alg in sorted(CATALOG.items()):
        hex_w = (alg.width + 3) // 4
        print(
            f"{name:<35} {alg.width:>5}  "
            f"0x{alg.poly:0{hex_w}X}  "
            f"{'Yes' if alg.ref_in else 'No':>5}  "
            f"{'Yes' if alg.ref_out else 'No':>6}  "
            f"0x{alg.check:0{hex_w}X}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crcZero",
        description=(
            "crcZero — CRC HDL code generator.\n"
            "Generates synthesizable Verilog-2001, SystemVerilog, or VHDL-1993 "
            "parallel CRC modules, plus a portable C reference implementation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crcZero --algorithm CRC-32/ISO-HDLC --lang verilog\n"
            "  crcZero --algorithm CRC-32/ISO-HDLC --data-width 64 --lang all --output crc32\n"
            "  crcZero --poly 0x04C11DB7 --width 32 --init 0xFFFFFFFF \\\n"
            "          --ref-in --ref-out --xor-out 0xFFFFFFFF --lang sv\n"
            "  crcZero --list-algorithms\n"
        ),
    )

    # ---- Catalog listing ----
    parser.add_argument(
        "--list-algorithms",
        action="store_true",
        default=False,
        help="Print all available named CRC algorithms and exit.",
    )

    # ---- Algorithm selection (named catalog OR custom params) ----
    alg_group = parser.add_argument_group("Algorithm selection")
    source = alg_group.add_mutually_exclusive_group()
    source.add_argument(
        "--algorithm",
        metavar="NAME",
        help=(
            "Select a named algorithm from the built-in catalog "
            "(e.g. 'CRC-32/ISO-HDLC'). Use --list-algorithms to see all options."
        ),
    )

    # ---- Custom polynomial parameters ----
    custom = parser.add_argument_group(
        "Custom algorithm parameters",
        "Used when --algorithm is not specified.",
    )
    custom.add_argument(
        "--poly",
        metavar="HEX",
        help="Generator polynomial in Williams normal form (MSB implicit). E.g. 0x04C11DB7.",
    )
    custom.add_argument(
        "--poly-koopman",
        metavar="HEX",
        help=(
            "Generator polynomial in Koopman notation (LSB implicit). "
            "Mutually exclusive with --poly. "
            "E.g. 0x82608EDB for CRC-32/ISO-HDLC."
        ),
    )
    custom.add_argument("--width",   metavar="INT", type=int, help="CRC width in bits.")
    custom.add_argument("--init",    metavar="HEX", help="Initial register value. Default: 0x0.")
    custom.add_argument("--ref-in",  action="store_true", default=False, help="Reflect input bytes.")
    custom.add_argument("--ref-out", action="store_true", default=False, help="Reflect final register.")
    custom.add_argument("--xor-out", metavar="HEX", help="Final XOR mask. Default: 0x0.")
    custom.add_argument("--check",   metavar="HEX", help="Expected CRC of b'123456789' (optional, enables self-test).")
    custom.add_argument("--residue", metavar="HEX", help="Residue value (optional).", default=None)
    custom.add_argument("--name",    metavar="STR", help="Algorithm name label for the header comment.")

    # ---- Generation options ----
    gen = parser.add_argument_group("Generation options")
    gen.add_argument(
        "--data-width",
        metavar="INT",
        type=int,
        default=8,
        help="Number of data bits processed per clock cycle. Default: 8.",
    )
    gen.add_argument(
        "--lang",
        choices=["verilog", "sv", "vhdl", "c", "all"],
        default="verilog",
        help=(
            "Output language: verilog (Verilog-2001), sv (SystemVerilog), "
            "vhdl (VHDL-1993), c (portable reference), or all outputs. "
            "Default: verilog."
        ),
    )
    gen.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help=(
            "Output file path (without extension). "
            "If omitted, output goes to stdout. "
            "When --lang=all, extensions .v / .sv / .vhd / .h / .c are appended automatically."
        ),
    )
    gen.add_argument(
        "--module-name",
        metavar="NAME",
        default=None,
        help="Override the generated module/entity name.",
    )
    gen.add_argument(
        "--no-self-test",
        action="store_true",
        default=False,
        help="Skip the check-value self-test (useful for custom algorithms without a known check value).",
    )
    gen.add_argument(
        "--testbench",
        action="store_true",
        default=False,
        help=(
            "Also generate a self-checking testbench alongside the DUT. "
            "Verilog: <stem>_tb.v (iverilog-compatible, produces VCD). "
            "VHDL: <stem>_tb.vhd (ghdl-compatible). "
            "With --lang=all, generates testbenches for all languages."
        ),
    )
    gen.add_argument(
        "--simulate",
        action="store_true",
        default=False,
        help=(
            "Auto-invoke the simulator after generating testbench files. "
            "Requires --output and --testbench. "
            "Verilog: uses iverilog + vvp. VHDL: uses ghdl. "
            "Both produce a VCD file alongside the output."
        ),
    )
    gen.add_argument(
        "--axi-stream",
        action="store_true",
        default=False,
        help=(
            "Also generate an AXI4-Stream wrapper alongside the CRC core. "
            "Verilog: <stem>_axis.v  SV: <stem>_axis.sv  VHDL: <stem>_axis.vhd. "
            "The wrapper implements a 2-state FSM with backpressure support."
        ),
    )

    return parser


def _build_algorithm(args: argparse.Namespace) -> Algorithm:
    """Construct an Algorithm from parsed CLI arguments."""
    if args.algorithm:
        name = args.algorithm
        if name not in CATALOG:
            suggestions = _suggest(name)
            msg = f"Unknown algorithm '{name}'."
            if suggestions:
                msg += f" Did you mean: {', '.join(suggestions)}?"
            else:
                msg += " Use --list-algorithms to see available options."
            print(f"error: {msg}", file=sys.stderr)
            sys.exit(1)
        return CATALOG[name]

    # Custom algorithm — require at minimum (--poly or --poly-koopman) and --width
    has_poly = args.poly is not None or args.poly_koopman is not None
    if not has_poly or args.width is None:
        print(
            "error: either --algorithm or (--poly or --poly-koopman) + --width are required.",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.poly is not None and args.poly_koopman is not None:
        print("error: --poly and --poly-koopman are mutually exclusive.", file=sys.stderr)
        sys.exit(1)

    width = args.width
    mask = (1 << width) - 1

    if args.poly_koopman is not None:
        from crczero.algorithm import poly_from_koopman
        koopman = _parse_hex(args.poly_koopman, "--poly-koopman")
        poly = poly_from_koopman(koopman, width)
    else:
        poly = _parse_hex(args.poly, "--poly")

    init    = _parse_hex(args.init,    "--init")    if args.init    else 0
    xor_out = _parse_hex(args.xor_out, "--xor-out") if args.xor_out else 0
    residue = _parse_hex(args.residue, "--residue") if args.residue else 0
    name    = args.name or f"CUSTOM-{width}"

    alg = Algorithm(
        name=name,
        width=width,
        poly=poly & mask,
        init=init & mask,
        ref_in=args.ref_in,
        ref_out=args.ref_out,
        xor_out=xor_out & mask,
        check=0,
        residue=residue & mask,
    )

    # Auto-compute check value if not explicitly provided
    if args.check:
        from dataclasses import replace
        check = _parse_hex(args.check, "--check") & mask
        alg = replace(alg, check=check)
    else:
        from crczero.software_crc import compute_crc
        from dataclasses import replace
        alg = replace(alg, check=compute_crc(alg, b"123456789"))

    return alg


def _write_output(content: str, path: Path | None) -> None:
    if path is None:
        print(content, end="")
    else:
        path.write_text(content, encoding="utf-8")
        print(f"Written: {path}", file=sys.stderr)


def _simulate_verilog(dut_path: Path, tb_path: Path) -> None:
    """Compile and run a Verilog testbench with iverilog + vvp."""
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        print(
            "warning: iverilog/vvp not found in PATH — skipping Verilog simulation.\n"
            "  Install Icarus Verilog: https://steveicarus.github.io/iverilog/",
            file=sys.stderr,
        )
        return
    sim_bin = tb_path.with_suffix("")
    print(f"Compiling: {iverilog} -o {sim_bin} {dut_path} {tb_path}", file=sys.stderr)
    r = subprocess.run([iverilog, "-o", str(sim_bin), str(dut_path), str(tb_path)])
    if r.returncode != 0:
        print("error: iverilog compilation failed.", file=sys.stderr)
        sys.exit(r.returncode)
    print(f"Running:   vvp {sim_bin}", file=sys.stderr)
    r = subprocess.run([vvp, str(sim_bin)])
    if r.returncode != 0:
        print("error: vvp simulation failed.", file=sys.stderr)
        sys.exit(r.returncode)


def _simulate_vhdl(dut_path: Path, tb_path: Path, tb_name: str) -> None:
    """Analyse and run a VHDL testbench with ghdl."""
    ghdl = shutil.which("ghdl")
    if not ghdl:
        print(
            "warning: ghdl not found in PATH — skipping VHDL simulation.\n"
            "  Install GHDL: https://ghdl.github.io/ghdl/",
            file=sys.stderr,
        )
        return
    vcd_path = tb_path.parent / f"{tb_name}.vcd"
    workdir = tb_path.parent
    print(f"Analysing: ghdl -a {dut_path} {tb_path}", file=sys.stderr)
    r = subprocess.run([ghdl, "-a", str(dut_path), str(tb_path)], cwd=str(workdir))
    if r.returncode != 0:
        print("error: ghdl analysis failed.", file=sys.stderr)
        sys.exit(r.returncode)
    print(f"Elaborating: ghdl -e {tb_name}", file=sys.stderr)
    r = subprocess.run([ghdl, "-e", tb_name], cwd=str(workdir))
    if r.returncode != 0:
        print("error: ghdl elaboration failed.", file=sys.stderr)
        sys.exit(r.returncode)
    print(f"Running: ghdl -r {tb_name} --vcd={vcd_path}", file=sys.stderr)
    r = subprocess.run([ghdl, "-r", tb_name, f"--vcd={vcd_path}"], cwd=str(workdir))
    if r.returncode != 0:
        print("error: ghdl simulation failed.", file=sys.stderr)
        sys.exit(r.returncode)
    print(f"VCD written: {vcd_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_algorithms:
        _list_algorithms()
        sys.exit(0)

    algorithm = _build_algorithm(args)
    data_width = args.data_width

    if data_width < 1:
        print("error: --data-width must be >= 1.", file=sys.stderr)
        sys.exit(1)

    gen = CrcGenerator(algorithm, data_width)

    # Self-test (skip for custom algorithms without a known check value)
    if not args.no_self_test and algorithm.check != 0:
        if not gen.self_test():
            expected = algorithm.check
            from crczero.software_crc import compute_crc
            got = compute_crc(algorithm, b"123456789")
            print(
                f"warning: self-test FAILED for '{algorithm.name}': "
                f"expected check=0x{expected:X}, got 0x{got:X}",
                file=sys.stderr,
            )

    # Validate simulate requires output + testbench
    if args.simulate and not args.output:
        print("error: --simulate requires --output to be specified.", file=sys.stderr)
        sys.exit(1)
    if args.simulate and not args.testbench:
        print("error: --simulate requires --testbench.", file=sys.stderr)
        sys.exit(1)

    # Determine output paths
    lang = args.lang
    output_stem = args.output
    module_name = args.module_name

    langs_to_generate = (
        ["verilog", "sv", "vhdl", "c"] if lang == "all" else [lang]
    )
    ext_map     = {"verilog": ".v",     "sv": ".sv",      "vhdl": ".vhd"}
    tb_ext_map  = {"verilog": "_tb.v",                    "vhdl": "_tb.vhd"}
    ax_ext_map  = {"verilog": "_axis.v", "sv": "_axis.sv", "vhdl": "_axis.vhd"}

    for l in langs_to_generate:
        if l == "verilog":
            code = gen.generate_verilog(module_name)
        elif l == "sv":
            code = gen.generate_systemverilog(module_name)
        elif l == "vhdl":
            code = gen.generate_vhdl(module_name)

        if output_stem is None:
            if l == "c":
                header, source = gen.generate_c(module_name)
                _write_output("// ---- C header ----\n" + header, None)
                _write_output("// ---- C source ----\n" + source, None)
            else:
                _write_output(code, None)
                if args.testbench and l != "sv":
                    if l == "verilog":
                        tb_code = gen.generate_testbench_verilog(module_name)
                    else:
                        tb_code = gen.generate_testbench_vhdl(module_name)
                    _write_output(tb_code, None)
                if args.axi_stream:
                    if l == "verilog":
                        ax_code = gen.generate_axi_stream_verilog(module_name)
                    elif l == "sv":
                        ax_code = gen.generate_axi_stream_sv(module_name)
                    else:
                        ax_code = gen.generate_axi_stream_vhdl(module_name)
                    _write_output(ax_code, None)
        else:
            if l == "c":
                header_path = Path(output_stem).with_suffix(".h")
                source_path = Path(output_stem).with_suffix(".c")
                header, source = gen.generate_c(module_name, header_path.name)
                _write_output(header, header_path)
                _write_output(source, source_path)
            else:
                out_path = Path(output_stem).with_suffix(ext_map[l])
                _write_output(code, out_path)
                if args.testbench and l != "sv":
                    if l == "verilog":
                        tb_code = gen.generate_testbench_verilog(module_name)
                    else:
                        tb_code = gen.generate_testbench_vhdl(module_name)
                    tb_path = Path(output_stem + tb_ext_map[l])
                    _write_output(tb_code, tb_path)
                    if args.simulate:
                        if l == "verilog":
                            _simulate_verilog(out_path, tb_path)
                        else:
                            tb_name = tb_path.stem
                            _simulate_vhdl(out_path, tb_path, tb_name)
                if args.axi_stream:
                    if l == "verilog":
                        ax_code = gen.generate_axi_stream_verilog(module_name)
                    elif l == "sv":
                        ax_code = gen.generate_axi_stream_sv(module_name)
                    else:
                        ax_code = gen.generate_axi_stream_vhdl(module_name)
                    ax_path = Path(output_stem + ax_ext_map[l])
                    _write_output(ax_code, ax_path)


if __name__ == "__main__":
    main()
