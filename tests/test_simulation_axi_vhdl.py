# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Integration test: AXI4-Stream VHDL wrapper simulated with ghdl.

Each test sends multiple packets through the generated wrapper, applies
backpressure on m_axis_tready, and checks the CRC output against the
software golden model (compute_crc).

Skipped automatically when ghdl is not found in PATH.
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


GHDL  = _find_tool("ghdl")
XVHDL = _find_tool("xvhdl")
XELAB = _find_tool("xelab")
XSIM  = _find_tool("xsim")

_HAS_GHDL = bool(GHDL)
_HAS_XSIM = bool(XVHDL and XELAB and XSIM)

requires_ghdl = pytest.mark.skipif(
    not _HAS_GHDL and not _HAS_XSIM,
    reason="no VHDL simulator found (need ghdl or xvhdl/xelab/xsim)",
)

VCD_DIR = Path(__file__).parent / "vcd"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lcg_seq(seed: int, count: int, modulo: int) -> list[int]:
    """Deterministic pseudo-random sequence via LCG (Numerical Recipes constants)."""
    vals, x = [], seed & 0xFFFFFFFF
    for _ in range(count):
        x = (x * 1664525 + 1013904223) & 0xFFFFFFFF
        vals.append(x % modulo)
    return vals


# ---------------------------------------------------------------------------
# Testbench generator
# ---------------------------------------------------------------------------

def _build_axis_tb_vhdl(
    alg_name: str,
    core_name: str,
    wrapper_name: str,
    data_width: int,
    packets: list[bytes],
    bp_cycles_per_packet: list[int],
) -> str:
    """Generate a VHDL-1993 self-checking testbench for the AXI-S wrapper.

    Each beat is sent with independent pseudo-random back-pressure on both sides:
    - m_stall: downstream stalls m_axis_tready='0' for N cycles so DUT holds output.
    - s_delay: upstream pauses s_axis_tvalid='0' for N cycles before the beat.
    After the last beat, collect_crc applies end-of-packet back-pressure (bp_cycles).
    """
    from crczero.catalog import CATALOG
    alg   = CATALOG[alg_name]
    N     = alg.width
    D     = data_width
    hex_w = (N + 3) // 4
    dhex_w = (D + 3) // 4
    bpw   = D // 8

    assert bpw >= 1 and D % 8 == 0

    expected = [compute_crc(alg, pkt) for pkt in packets]
    tb_name  = f"{wrapper_name}_sim_tb"

    lines: list[str] = []
    lines.append("library ieee;")
    lines.append("use ieee.std_logic_1164.all;")
    lines.append("library std;")
    lines.append("use std.env.all;  -- stop/finish for clean simulation exit")
    lines.append("")
    lines.append(f"entity {tb_name} is")
    lines.append("end entity;")
    lines.append("")
    lines.append(f"architecture sim of {tb_name} is")
    lines.append("")
    lines.append("  signal clk           : std_logic := '0';")
    lines.append("  signal rst_n         : std_logic := '0';")
    lines.append(f"  signal s_axis_tdata  : std_logic_vector({D-1} downto 0) := (others => '0');")
    lines.append("  signal s_axis_tvalid : std_logic := '0';")
    lines.append("  signal s_axis_tready : std_logic;")
    lines.append("  signal s_axis_tlast  : std_logic := '0';")
    lines.append(f"  signal m_axis_tdata  : std_logic_vector({N-1} downto 0);")
    lines.append("  signal m_axis_tvalid : std_logic;")
    lines.append("  signal m_axis_tlast  : std_logic;")
    lines.append("  signal m_axis_tready : std_logic := '0';")
    lines.append("")
    lines.append("begin")
    lines.append("")
    lines.append("  clk <= not clk after 5 ns;")
    lines.append("")

    # DUT instantiation (wrapper)
    lines.append(f"  dut : entity work.{wrapper_name}(rtl)")
    lines.append("    port map (")
    lines.append("      clk           => clk,")
    lines.append("      rst_n         => rst_n,")
    lines.append("      s_axis_tdata  => s_axis_tdata,")
    lines.append("      s_axis_tvalid => s_axis_tvalid,")
    lines.append("      s_axis_tready => s_axis_tready,")
    lines.append("      s_axis_tlast  => s_axis_tlast,")
    lines.append("      m_axis_tdata  => m_axis_tdata,")
    lines.append("      m_axis_tvalid => m_axis_tvalid,")
    lines.append("      m_axis_tlast  => m_axis_tlast,")
    lines.append("      m_axis_tready => m_axis_tready")
    lines.append("    );")
    lines.append("")

    # Stimulus process
    lines.append("  stim : process")
    lines.append(f"    variable fail_count : integer := 0;")
    lines.append(f"    variable got_crc    : std_logic_vector({N-1} downto 0);")
    lines.append("")

    # send_beat procedure with independent upstream/downstream back-pressure.
    # m_stall > 0: hold m_axis_tready='0' so DUT keeps output register full.
    # s_delay > 0: pause s_axis_tvalid='0' before presenting the beat.
    lines.append(f"    procedure send_beat(")
    lines.append(f"      data    : in std_logic_vector({D-1} downto 0);")
    lines.append( "      last    : in std_logic;")
    lines.append( "      m_stall : in integer := 0;")
    lines.append( "      s_delay : in integer := 0")
    lines.append( "    ) is")
    lines.append( "    begin")
    lines.append( "      -- Downstream stall: freeze DUT output register.")
    lines.append( "      if m_stall > 0 then")
    lines.append( "        m_axis_tready <= '0';")
    lines.append( "        for i in 1 to m_stall loop")
    lines.append( "          wait until rising_edge(clk);")
    lines.append( "        end loop;")
    lines.append( "        m_axis_tready <= '1';")
    lines.append( "      end if;")
    lines.append( "      -- Upstream idle: sender pauses before presenting beat.")
    lines.append( "      for i in 1 to s_delay loop")
    lines.append( "        wait until rising_edge(clk);")
    lines.append( "      end loop;")
    lines.append( "      -- Drive and hold until handshake (s_axis_tready='1' at rising edge).")
    lines.append( "      s_axis_tdata  <= data;")
    lines.append( "      s_axis_tvalid <= '1';")
    lines.append( "      s_axis_tlast  <= last;")
    lines.append( "      loop")
    lines.append( "        wait until rising_edge(clk);")
    lines.append( "        exit when s_axis_tready = '1';")
    lines.append( "      end loop;")
    lines.append( "      s_axis_tvalid <= '0';")
    lines.append( "      s_axis_tlast  <= '0';")
    lines.append( "    end procedure;")
    lines.append("")

    # collect_crc procedure — applies real back-pressure.
    # Called right after last send_beat; immediately lowers m_tready so the DUT
    # holds its output register.  Waits bp_cycles extra clocks, then accepts.
    lines.append( "    procedure collect_crc(")
    lines.append( "      bp_cycles : in integer;")
    lines.append(f"      crc_out   : out std_logic_vector({N-1} downto 0)")
    lines.append( "    ) is")
    lines.append( "    begin")
    lines.append( "      -- Assert back-pressure: DUT holds output because s_tready goes low.")
    lines.append( "      m_axis_tready <= '0';")
    lines.append( "      -- Wait for the final beat (tvalid AND tlast).")
    lines.append( "      loop")
    lines.append( "        wait until rising_edge(clk);")
    lines.append( "        exit when m_axis_tvalid = '1' and m_axis_tlast = '1';")
    lines.append( "      end loop;")
    lines.append( "      -- Stall bp_cycles clocks — DUT must hold output unchanged.")
    lines.append( "      for i in 1 to bp_cycles loop")
    lines.append( "        wait until rising_edge(clk);")
    lines.append( "      end loop;")
    lines.append( "      -- Release back-pressure and accept the final beat.")
    lines.append( "      m_axis_tready <= '1';")
    lines.append( "      wait until rising_edge(clk);")
    lines.append( "      crc_out := m_axis_tdata;")
    lines.append( "      m_axis_tready <= '0';")
    lines.append( "    end procedure;")
    lines.append("")

    lines.append( "  begin")
    lines.append( "    -- Reset")
    lines.append( "    rst_n <= '0';")
    lines.append( "    wait until rising_edge(clk);")
    lines.append( "    wait until rising_edge(clk);")
    lines.append( "    wait until rising_edge(clk);")
    lines.append( "    wait until rising_edge(clk);")
    lines.append( "    rst_n <= '1';")
    lines.append( "    wait until rising_edge(clk);")
    lines.append("")

    # --- Pass 1: pseudo-random stall patterns on both sides ---
    for pkt_idx, (pkt, bp, exp) in enumerate(zip(packets, bp_cycles_per_packet, expected)):
        if len(pkt) % bpw:
            pkt = pkt + b"\x00" * (bpw - len(pkt) % bpw)
        words = [pkt[i:i+bpw] for i in range(0, len(pkt), bpw)]

        # Per-beat pseudo-random stall patterns (LCG, max 3 cycles each).
        seed_m = (pkt_idx * 31337 + data_width * 1337) & 0xFFFFFFFF
        seed_s = seed_m ^ 0xDEADBEEF
        m_stalls = _lcg_seq(seed_m, len(words), 4)
        m_stalls[0] = 0  # no downstream stall before the first beat
        s_delays = _lcg_seq(seed_s, len(words), 4)

        lines.append(f"    -- Packet {pkt_idx} (stall): {len(words)} beat(s), end-bp={bp}")
        lines.append(f"    -- m_stalls={m_stalls}  s_delays={s_delays}")
        lines.append( "    m_axis_tready <= '1';  -- ensure downstream open before first beat")
        for widx, word_bytes in enumerate(words):
            is_last = widx == len(words) - 1
            # Little-endian: first byte → data_in(7 downto 0), matching the CRC equations.
            word_val = int.from_bytes(word_bytes, 'little')
            last_char = "'1'" if is_last else "'0'"
            lines.append(
                f'    send_beat(x"{word_val:0{dhex_w}X}", {last_char},'
                f' {m_stalls[widx]}, {s_delays[widx]});'
            )

        lines.append(f"    collect_crc({bp}, got_crc);")
        lines.append(f'    if got_crc /= x"{exp:0{hex_w}X}" then')
        lines.append(f'      report "FAIL pkt {pkt_idx} (stall)" severity error;')
        lines.append( "      fail_count := fail_count + 1;")
        lines.append( "    else")
        lines.append(f'      report "PASS pkt {pkt_idx} (stall)";')
        lines.append( "    end if;")
        lines.append("")

    # --- Pass 2: no stalls — verify basic throughput at full rate ---
    for pkt_idx, (pkt, exp) in enumerate(zip(packets, expected)):
        if len(pkt) % bpw:
            pkt = pkt + b"\x00" * (bpw - len(pkt) % bpw)
        words = [pkt[i:i+bpw] for i in range(0, len(pkt), bpw)]

        lines.append(f"    -- Packet {pkt_idx} (no-stall): {len(words)} beat(s)")
        lines.append( "    m_axis_tready <= '1';")
        for widx, word_bytes in enumerate(words):
            is_last = widx == len(words) - 1
            word_val = int.from_bytes(word_bytes, 'little')
            last_char = "'1'" if is_last else "'0'"
            lines.append(f'    send_beat(x"{word_val:0{dhex_w}X}", {last_char}, 0, 0);')

        lines.append(f"    collect_crc(0, got_crc);")
        lines.append(f'    if got_crc /= x"{exp:0{hex_w}X}" then')
        lines.append(f'      report "FAIL pkt {pkt_idx} (no-stall)" severity error;')
        lines.append( "      fail_count := fail_count + 1;")
        lines.append( "    else")
        lines.append(f'      report "PASS pkt {pkt_idx} (no-stall)";')
        lines.append( "    end if;")
        lines.append("")

    total = len(packets) * 2
    lines.append( "    if fail_count = 0 then")
    lines.append(f'      report "ALL {total} CHECKS PASSED ({alg_name})" severity note;')
    lines.append( "    else")
    lines.append( '      report "FAILURES DETECTED" severity failure;')
    lines.append( "    end if;")
    lines.append( "    stop;  -- std.env.stop: clean simulation exit (VHDL-2008)")
    lines.append( "  end process;")
    lines.append("")
    lines.append("end sim;")
    lines.append("")

    return "\n".join(lines)


def _run_axis_sim(
    tmp_path: Path,
    core_code: str,
    wrapper_code: str,
    tb_code: str,
    tb_entity: str,
) -> str:
    """Analyse + elaborate + simulate; copy VCD to tests/vcd/; return output."""
    core_path    = tmp_path / "core.vhd"
    wrapper_path = tmp_path / "wrapper.vhd"
    tb_path      = tmp_path / "tb.vhd"

    core_path.write_text(core_code,    encoding="utf-8")
    wrapper_path.write_text(wrapper_code, encoding="utf-8")
    tb_path.write_text(tb_code,        encoding="utf-8")

    if _HAS_GHDL:
        output = _run_ghdl(tmp_path, core_path, wrapper_path, tb_path, tb_entity)
    else:
        output = _run_xsim_vhdl(tmp_path, core_path, wrapper_path, tb_path, tb_entity)

    _save_vcd(tmp_path, tb_entity)
    return output


def _run_ghdl(
    tmp_path: Path,
    core_path: Path,
    wrapper_path: Path,
    tb_path: Path,
    tb_entity: str,
) -> str:
    vcd_path = tmp_path / f"{tb_entity}.vcd"

    analyse = subprocess.run(
        [GHDL, "-a", "--std=08", str(core_path), str(wrapper_path), str(tb_path)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert analyse.returncode == 0, f"ghdl -a failed:\n{analyse.stdout}\n{analyse.stderr}"

    elab = subprocess.run(
        [GHDL, "-e", "--std=08", tb_entity],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert elab.returncode == 0, f"ghdl -e failed:\n{elab.stdout}\n{elab.stderr}"

    run = subprocess.run(
        [GHDL, "-r", "--std=08", tb_entity, f"--vcd={vcd_path}"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    output = run.stdout + run.stderr
    assert run.returncode == 0, f"ghdl -r exited {run.returncode}:\n{output}"
    return output


def _run_xsim_vhdl(
    tmp_path: Path,
    core_path: Path,
    wrapper_path: Path,
    tb_path: Path,
    tb_entity: str,
) -> str:
    """Compile + elaborate + simulate with Vivado xvhdl/xelab/xsim."""
    vcd_path = tmp_path / f"{tb_entity}.vcd"

    r = subprocess.run(
        [XVHDL, str(core_path), str(wrapper_path), str(tb_path)],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xvhdl failed:\n{r.stdout}\n{r.stderr}"

    r = subprocess.run(
        [XELAB, tb_entity, "-debug", "typical"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xelab failed:\n{r.stdout}\n{r.stderr}"

    # Use a Tcl batch script to open/log VCD and run the simulation.
    # Use a bare filename and run with cwd=tmp_path to avoid backslash path issues.
    vcd_name = f"{tb_entity}.vcd"
    tcl_path = tmp_path / "sim.tcl"
    tcl_path.write_text(
        f"open_vcd {vcd_name}\n"
        "log_vcd /*\n"
        "run all\n"
        "close_vcd\n"
        "quit\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [XSIM, f"work.{tb_entity}", "--nolog", "--tclbatch", "sim.tcl"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"xsim failed:\n{r.stdout}\n{r.stderr}"
    return r.stdout + r.stderr


def _save_vcd(tmp_path: Path, tb_entity: str) -> None:
    """Copy the VCD generated in tmp_path to tests/vcd/*.vhd.vcd for inspection."""
    vcd_src = tmp_path / f"{tb_entity}.vcd"
    if not vcd_src.exists():
        return
    VCD_DIR.mkdir(exist_ok=True)
    import shutil as _shutil
    _shutil.copy2(vcd_src, VCD_DIR / f"{tb_entity}.vhd.vcd")


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

_BP = [0, 1, 3, 5, 0, 2, 4, 1, 0, 3]


@requires_ghdl
@pytest.mark.parametrize("alg_name,data_width", AXIS_CASES)
def test_axis_vhdl_all_pass(alg_name, data_width, tmp_path):
    """All packets must report PASS; backpressure must not corrupt the CRC."""
    alg = CATALOG[alg_name]
    gen = CrcGenerator(alg, data_width=data_width)

    core_code    = gen.generate_vhdl()
    wrapper_code = gen.generate_axi_stream_vhdl()

    from crczero.renderers.vhdl import VhdlRenderer
    core_name    = VhdlRenderer().default_name(alg, data_width)
    wrapper_name = f"{core_name}_axis"

    bpw = data_width // 8
    packets = []
    for pkt in _PACKETS:
        if len(pkt) % bpw:
            pkt = pkt + b"\x00" * (bpw - len(pkt) % bpw)
        packets.append(pkt)

    tb_entity = f"{wrapper_name}_sim_tb"
    tb_code = _build_axis_tb_vhdl(
        alg_name, core_name, wrapper_name, data_width, packets, _BP
    )

    output = _run_axis_sim(tmp_path, core_code, wrapper_code, tb_code, tb_entity)

    assert "FAIL pkt" not in output, (
        f"{alg_name} D={data_width}: simulator reported failures:\n{output}"
    )
    assert "ALL" in output and "PASSED" in output, (
        f"{alg_name} D={data_width}: expected 'ALL ... PASSED' in output:\n{output}"
    )
