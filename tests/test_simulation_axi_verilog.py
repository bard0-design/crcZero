# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Integration test: AXI4-Stream Verilog wrapper simulated with iverilog/vvp.

Each test sends multiple packets through the generated wrapper, applies
backpressure on m_axis_tready, and checks the CRC output against the
software golden model (compute_crc).

Skipped automatically when iverilog/vvp are not found in PATH.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from crczero.catalog import CATALOG
from crczero.generator import CrcGenerator
from crczero.software_crc import compute_crc


def _find_tool(name: str) -> str | None:
    return shutil.which(name)


IVERILOG = _find_tool("iverilog")
VVP      = _find_tool("vvp")
XVLOG    = _find_tool("xvlog")
XELAB    = _find_tool("xelab")
XSIM     = _find_tool("xsim")

_HAS_IVERILOG = bool(IVERILOG and VVP)
_HAS_XSIM     = bool(XVLOG and XELAB and XSIM)

requires_iverilog = pytest.mark.skipif(
    not _HAS_IVERILOG and not _HAS_XSIM,
    reason="no Verilog simulator found (need iverilog/vvp or xvlog/xelab/xsim)",
)

# Where to persist VCDs across test runs
VCD_DIR = Path(__file__).parent / "vcd"


# ---------------------------------------------------------------------------
# Testbench generator
# ---------------------------------------------------------------------------

def _lcg_seq(seed: int, count: int, modulo: int) -> list[int]:
    """Deterministic pseudo-random sequence via LCG (Numerical Recipes constants)."""
    vals, x = [], seed & 0xFFFFFFFF
    for _ in range(count):
        x = (x * 1664525 + 1013904223) & 0xFFFFFFFF
        vals.append(x % modulo)
    return vals


def _build_axis_tb_verilog(
    alg_name: str,
    wrapper_name: str,
    data_width: int,
    packets: list[bytes],
    bp_cycles_per_packet: list[int],
) -> str:
    """Generate a Verilog-2001 self-checking testbench for the AXI-S wrapper.

    Each beat is sent with independent pseudo-random back-pressure on both sides:
    - m_stall: downstream stalls m_tready=0 for N cycles so DUT holds its output reg.
    - s_delay: upstream pauses s_tvalid=0 for N cycles before presenting the beat.
    After the last beat, collect_crc applies end-of-packet back-pressure (bp_cycles).
    Checks m_axis_tdata against the software oracle.
    """
    from crczero.catalog import CATALOG
    alg      = CATALOG[alg_name]
    N        = alg.width
    D        = data_width
    hex_w    = (N + 3) // 4
    dhex_w   = (D + 3) // 4
    bpw      = D // 8   # bytes per word

    assert bpw >= 1 and D % 8 == 0

    # Compute expected CRC for every packet using the software oracle.
    expected = [compute_crc(alg, pkt) for pkt in packets]

    lines: list[str] = []
    lines.append("`timescale 1ns/1ps")
    lines.append(f"module {wrapper_name}_axis_sim_tb;")
    lines.append("")
    lines.append("    reg         clk = 0;")
    lines.append("    always #5 clk = ~clk;")
    lines.append("")
    lines.append("    reg         rst_n;")
    lines.append(f"    reg  [{D-1}:0] s_tdata;")
    lines.append("    reg         s_tvalid;")
    lines.append("    wire        s_tready;")
    lines.append("    reg         s_tlast;")
    lines.append(f"    wire [{N-1}:0] m_tdata;")
    lines.append("    wire        m_tvalid;")
    lines.append("    wire        m_tlast;")
    lines.append("    reg         m_tready;")
    lines.append("    integer     fail_count;")
    lines.append(f"    reg [{N-1}:0] got_crc;")
    lines.append("")

    # DUT instantiation
    lines.append(f"    {wrapper_name}_axis dut (")
    lines.append("        .clk          (clk),")
    lines.append("        .rst_n        (rst_n),")
    lines.append("        .s_axis_tdata (s_tdata),")
    lines.append("        .s_axis_tvalid(s_tvalid),")
    lines.append("        .s_axis_tready(s_tready),")
    lines.append("        .s_axis_tlast (s_tlast),")
    lines.append("        .m_axis_tdata (m_tdata),")
    lines.append("        .m_axis_tvalid(m_tvalid),")
    lines.append("        .m_axis_tlast (m_tlast),")
    lines.append("        .m_axis_tready(m_tready)")
    lines.append("    );")
    lines.append("")

    # Task: send one AXI-S beat with independent upstream/downstream back-pressure.
    #
    # m_stall > 0: lower m_tready for N cycles so the DUT's output register stays
    #   full (m_tvalid=1, m_tready=0 → s_tready=0).  The send_beat call for THIS
    #   beat applies the stall BEFORE driving, stressing the DUT's hold logic.
    #
    # s_delay > 0: pause N cycles with s_tvalid=0 before presenting the beat,
    #   simulating an upstream source that is occasionally not ready.
    #
    # Both stalls are applied in the same task so the testbench looks like a real
    # AXI-S master that can stall on either side independently.
    #
    # Signals are driven AFTER a posedge (#1) so the DUT always sees stable data
    # at the NEXT posedge — eliminates the xsim/iverilog active-region race.
    lines.append("    task send_beat;")
    lines.append(f"        input [{D-1}:0] data;")
    lines.append("        input         last;")
    lines.append("        input integer m_stall;  // downstream: hold m_tready=0 N cycles")
    lines.append("        input integer s_delay;  // upstream: pause s_tvalid=0 N cycles")
    lines.append("        begin")
    lines.append("            // Downstream stall: freeze DUT output register.")
    lines.append("            if (m_stall > 0) begin")
    lines.append("                m_tready = 0;")
    lines.append("                repeat(m_stall) @(posedge clk);")
    lines.append("                #1; m_tready = 1;")
    lines.append("            end")
    lines.append("            // Upstream idle: sender pauses before presenting beat.")
    lines.append("            repeat(s_delay) @(posedge clk);")
    lines.append("            // Drive after posedge — no race with DUT's always @(posedge clk).")
    lines.append("            @(posedge clk); #1;")
    lines.append("            s_tdata  = data;")
    lines.append("            s_tvalid = 1;")
    lines.append("            s_tlast  = last;")
    lines.append("            // Handshake: keep valid until s_tready=1 at a posedge.")
    lines.append("            // Checked at posedge (pre-NBA update) — same value DUT sees.")
    lines.append("            @(posedge clk);")
    lines.append("            while (!s_tready) @(posedge clk);")
    lines.append("            #1;")
    lines.append("            s_tvalid = 0;")
    lines.append("            s_tlast  = 0;")
    lines.append("        end")
    lines.append("    endtask")
    lines.append("")

    # Task: collect final CRC with real back-pressure.
    # Called right after last send_beat; immediately lowers m_tready so the DUT
    # holds its output register.  Waits bp_cycles extra clocks before accepting,
    # verifying that the DUT does not corrupt or lose the result under stall.
    lines.append("    task collect_crc;")
    lines.append("        input integer bp_cycles;")
    lines.append(f"        output [{N-1}:0] crc_out;")
    lines.append("        integer i;")
    lines.append("        begin")
    lines.append("            // Assert back-pressure immediately after last beat sent.")
    lines.append("            // DUT will hold its output register because s_tready goes low.")
    lines.append("            m_tready = 0;")
    lines.append("            // Wait for DUT to present the final beat (tvalid && tlast).")
    lines.append("            // Already true one delta after send_beat returns, but the")
    lines.append("            // while guards against any pipeline latency.")
    lines.append("            while (!(m_tvalid && m_tlast)) begin @(posedge clk); #1; end")
    lines.append("            // Stall bp_cycles clocks — DUT must hold output unchanged.")
    lines.append("            for (i = 0; i < bp_cycles; i = i + 1) @(posedge clk);")
    lines.append("            // Release back-pressure and accept the final beat.")
    lines.append("            m_tready = 1;")
    lines.append("            @(posedge clk);")
    lines.append("            #1; crc_out = m_tdata;  // sample while register still holds")
    lines.append("            m_tready = 0;           // re-apply back-pressure for next packet")
    lines.append("        end")
    lines.append("    endtask")
    lines.append("")

    # Main stimulus
    lines.append("    initial begin")
    lines.append(f'        $dumpfile("{wrapper_name}_axis_sim_tb.vcd");')
    lines.append(f"        $dumpvars(0, {wrapper_name}_axis_sim_tb);")
    lines.append("")
    lines.append("        // Reset")
    lines.append("        s_tvalid = 0; s_tlast = 0; m_tready = 1;")
    lines.append("        rst_n = 0;")
    lines.append("        repeat(4) @(posedge clk);")
    lines.append("        #1; rst_n = 1;")
    lines.append("        @(posedge clk);")
    lines.append("")
    lines.append("        fail_count = 0;")
    lines.append("")

    # --- Pass 1: pseudo-random stall patterns on both sides ---
    for pkt_idx, (pkt, bp, exp) in enumerate(zip(packets, bp_cycles_per_packet, expected)):
        # Pad to word boundary
        if len(pkt) % bpw:
            pkt = pkt + b"\x00" * (bpw - len(pkt) % bpw)
        words = [pkt[i:i+bpw] for i in range(0, len(pkt), bpw)]

        # Per-beat pseudo-random stall patterns (LCG, max 3 cycles each).
        # m_stalls: downstream stall (m_tready=0) before each beat.
        # s_delays: upstream idle (s_tvalid=0) before each beat.
        # Beat 0 never has a downstream stall (no previous output register to hold).
        seed_m = (pkt_idx * 31337 + data_width * 1337) & 0xFFFFFFFF
        seed_s = seed_m ^ 0xDEADBEEF
        m_stalls = _lcg_seq(seed_m, len(words), 4)
        m_stalls[0] = 0  # no downstream stall before the first beat
        s_delays = _lcg_seq(seed_s, len(words), 4)

        lines.append(f"        // --- Packet {pkt_idx} (stall): {len(words)} beat(s), end-bp={bp} ---")
        lines.append(f"        // m_stalls={m_stalls}  s_delays={s_delays}")
        lines.append("        m_tready = 1;  // ensure downstream is open before first beat")
        for widx, word_bytes in enumerate(words):
            is_last = (widx == len(words) - 1)
            # little-endian: first byte → data_in[7:0], next → data_in[15:8] …
            word_val = int.from_bytes(word_bytes, 'little')
            last_str = "1" if is_last else "0"
            lines.append(
                f"        send_beat({D}'h{word_val:0{dhex_w}X}, {last_str},"
                f" {m_stalls[widx]}, {s_delays[widx]});"
            )

        lines.append(f"        collect_crc({bp}, got_crc);")
        lines.append(f"        if (got_crc !== {N}'h{exp:0{hex_w}X}) begin")
        lines.append(f'            $display("FAIL pkt {pkt_idx} (stall): expected {N}\'h{exp:0{hex_w}X} got %h", got_crc);')
        lines.append("            fail_count = fail_count + 1;")
        lines.append("        end else begin")
        lines.append(f'            $display("PASS pkt {pkt_idx} (stall)");')
        lines.append("        end")
        lines.append("")

    # --- Pass 2: no stalls — verify basic throughput at full rate ---
    for pkt_idx, (pkt, exp) in enumerate(zip(packets, expected)):
        if len(pkt) % bpw:
            pkt = pkt + b"\x00" * (bpw - len(pkt) % bpw)
        words = [pkt[i:i+bpw] for i in range(0, len(pkt), bpw)]

        lines.append(f"        // --- Packet {pkt_idx} (no-stall): {len(words)} beat(s) ---")
        lines.append("        m_tready = 1;")
        for widx, word_bytes in enumerate(words):
            is_last = (widx == len(words) - 1)
            word_val = int.from_bytes(word_bytes, 'little')
            last_str = "1" if is_last else "0"
            lines.append(f"        send_beat({D}'h{word_val:0{dhex_w}X}, {last_str}, 0, 0);")

        lines.append(f"        collect_crc(0, got_crc);")
        lines.append(f"        if (got_crc !== {N}'h{exp:0{hex_w}X}) begin")
        lines.append(f'            $display("FAIL pkt {pkt_idx} (no-stall): expected {N}\'h{exp:0{hex_w}X} got %h", got_crc);')
        lines.append("            fail_count = fail_count + 1;")
        lines.append("        end else begin")
        lines.append(f'            $display("PASS pkt {pkt_idx} (no-stall)");')
        lines.append("        end")
        lines.append("")

    total = len(packets) * 2
    lines.append(f'        if (fail_count == 0)')
    lines.append(f'            $display("ALL {total} CHECKS PASSED ({alg_name})");')
    lines.append(f'        else')
    lines.append(f'            $display("%0d / {total} CHECKS FAILED", fail_count);')
    lines.append("")
    lines.append("        $finish;")
    lines.append("    end")
    lines.append("")
    lines.append(f"endmodule  // {wrapper_name}_axis_sim_tb")
    lines.append("")

    return "\n".join(lines)


def _run_axis_sim(
    tmp_path: Path,
    core_code: str,
    wrapper_code: str,
    tb_code: str,
    tb_module: str,
) -> str:
    """Compile + simulate; copy the VCD to tests/vcd/; return combined output."""
    core_path    = tmp_path / "core.v"
    wrapper_path = tmp_path / "wrapper.v"
    tb_path      = tmp_path / "tb.v"

    core_path.write_text(core_code,    encoding="utf-8")
    wrapper_path.write_text(wrapper_code, encoding="utf-8")
    tb_path.write_text(tb_code,        encoding="utf-8")

    if _HAS_IVERILOG:
        output = _run_iverilog(tmp_path, core_path, wrapper_path, tb_path)
    else:
        output = _run_xsim_verilog(tmp_path, core_path, wrapper_path, tb_path, tb_module)

    _save_vcd(tmp_path, tb_module)
    return output


def _run_iverilog(
    tmp_path: Path,
    core_path: Path,
    wrapper_path: Path,
    tb_path: Path,
) -> str:
    sim_bin = tmp_path / "sim.vvp"
    r = subprocess.run(
        [IVERILOG, "-o", str(sim_bin), str(core_path), str(wrapper_path), str(tb_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"iverilog failed:\n{r.stdout}\n{r.stderr}"
    r = subprocess.run(
        [VVP, str(sim_bin)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"vvp failed:\n{r.stdout}\n{r.stderr}"
    return r.stdout + r.stderr


def _run_xsim_verilog(
    tmp_path: Path,
    core_path: Path,
    wrapper_path: Path,
    tb_path: Path,
    tb_module: str,
) -> str:
    """Compile + elaborate + simulate with Vivado xvlog/xelab/xsim."""
    r = subprocess.run(
        [XVLOG, str(core_path), str(wrapper_path), str(tb_path)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xvlog failed:\n{r.stdout}\n{r.stderr}"

    r = subprocess.run(
        [XELAB, tb_module, "-debug", "typical", "-timescale", "1ns/1ps"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xelab failed:\n{r.stdout}\n{r.stderr}"

    r = subprocess.run(
        [XSIM, f"work.{tb_module}", "--runall", "--nolog"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xsim failed:\n{r.stdout}\n{r.stderr}"
    return r.stdout + r.stderr


def _save_vcd(tmp_path: Path, tb_module: str) -> None:
    """Copy the VCD generated in tmp_path to tests/vcd/*.v.vcd for inspection."""
    vcd_src = tmp_path / f"{tb_module}.vcd"
    if not vcd_src.exists():
        return
    VCD_DIR.mkdir(exist_ok=True)
    import shutil as _shutil
    _shutil.copy2(vcd_src, VCD_DIR / f"{tb_module}.v.vcd")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

AXIS_CASES = [
    ("CRC-8/SMBUS",     8),
    ("CRC-16/ARC",      8),
    ("CRC-32/ISO-HDLC", 8),
    ("CRC-32/MPEG-2",   8),
    ("CRC-32/ISO-HDLC", 32),
]

# Packets shared across all algorithms
_PACKETS = [
    b"123456789",                          # 9 bytes — reproduces check value
    b"\x00" * 8,                           # all-zero
    b"\xff" * 4,                           # all-ones
    b"\x01\x02\x03\x04",                   # sequential ascending
    b"\xde\xad\xbe\xef",                   # classic pattern
    b"\xaa" * 8,                           # alternating 10101010
    b"\x55" * 4,                           # alternating 01010101
    b"Hello",                              # ASCII text
    b"\x80\x40\x20\x10",                   # descending powers of 2
    b"\x01\x23\x45\x67\x89\xab\xcd\xef",  # hex ramp
]

# Backpressure cycles per packet: mix of no-bp and varying delays
_BP = [0, 1, 3, 5, 0, 2, 4, 1, 0, 3]


@requires_iverilog
@pytest.mark.parametrize("alg_name,data_width", AXIS_CASES)
def test_axis_verilog_all_pass(alg_name, data_width, tmp_path):
    """All packets must report PASS; backpressure must not corrupt the CRC."""
    alg = CATALOG[alg_name]
    gen = CrcGenerator(alg, data_width=data_width)

    core_code    = gen.generate_verilog()
    wrapper_code = gen.generate_axi_stream_verilog()

    from crczero.renderers.verilog import VerilogRenderer
    core_name    = VerilogRenderer().default_name(alg, data_width)
    wrapper_name = core_name  # tb helper appends _axis itself

    # Pad packets to word boundary for this data_width
    bpw = data_width // 8
    packets = []
    for pkt in _PACKETS:
        if len(pkt) % bpw:
            pkt = pkt + b"\x00" * (bpw - len(pkt) % bpw)
        packets.append(pkt)

    tb_code = _build_axis_tb_verilog(alg_name, core_name, data_width, packets, _BP)

    output = _run_axis_sim(tmp_path, core_code, wrapper_code, tb_code, f"{core_name}_axis_sim_tb")

    assert "FAIL" not in output, (
        f"{alg_name} D={data_width}: simulator reported failures:\n{output}"
    )
    assert "ALL" in output and "PASSED" in output, (
        f"{alg_name} D={data_width}: expected 'ALL ... PASSED' in output:\n{output}"
    )
