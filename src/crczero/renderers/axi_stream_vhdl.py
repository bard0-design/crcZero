# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""VHDL-1993 AXI4-Stream CRC wrapper renderer.

Wraps the existing combinatorial CRC core with a clocked AXI4-Stream interface.

Pipeline register design: m_axis_tvalid is asserted for every accepted slave
beat (running/partial CRC). m_axis_tlast mirrors s_axis_tlast. The XOR-out
adjusted final CRC appears on the tlast beat; crc_reg resets to HW_INIT on
that same clock so the next packet starts fresh.

s_axis_tready = '1' when m_tvalid_r = '0' or m_axis_tready = '1'

Uses direct entity instantiation (entity work.<core>(rtl)) to avoid binding issues.

Compatible with ghdl --std=93 and standard VHDL-1993 synthesis tools.
"""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations
from crczero.renderers.axi_stream_verilog import _hw_init
from crczero.renderers.base import Renderer


class AxiStreamVhdlRenderer(Renderer):
    """Generates a VHDL-1993 AXI4-Stream wrapper for the CRC core."""

    def render(
        self,
        equations: CrcEquations,
        algorithm: Algorithm,
        data_width: int,
        name: str | None = None,
    ) -> str:
        core_name    = name or self.default_name(algorithm, data_width)
        wrapper_name = f"{core_name}_axis"
        N     = equations.width
        D     = equations.data_width
        hex_w = (N + 3) // 4
        hw_init = _hw_init(algorithm)

        lines: list[str] = []
        lines += self._axis_header(algorithm, data_width, core_name, wrapper_name)

        # ---- Library / use ----
        lines.append("library ieee;")
        lines.append("use ieee.std_logic_1164.all;")
        lines.append("")

        # ---- Entity ----
        lines.append(f"entity {wrapper_name} is")
        lines.append("  port (")
        lines.append("    clk           : in  std_logic;")
        lines.append("    rst_n         : in  std_logic;  -- active-low synchronous reset")
        lines.append("    -- AXI4-Stream slave (data in)")
        lines.append(f"    s_axis_tdata  : in  std_logic_vector({D-1} downto 0);")
        lines.append("    s_axis_tvalid : in  std_logic;")
        lines.append("    s_axis_tready : out std_logic;")
        lines.append("    s_axis_tlast  : in  std_logic;")
        lines.append("    -- AXI4-Stream master (running CRC out, one beat per input beat)")
        lines.append(f"    m_axis_tdata  : out std_logic_vector({N-1} downto 0);")
        lines.append("    m_axis_tvalid : out std_logic;")
        lines.append("    m_axis_tlast  : out std_logic;")
        lines.append("    m_axis_tready : in  std_logic")
        lines.append("  );")
        lines.append(f"end {wrapper_name};")
        lines.append("")

        # ---- Architecture ----
        lines.append(f"architecture rtl of {wrapper_name} is")
        lines.append("")
        lines.append(f"  constant HW_INIT : std_logic_vector({N-1} downto 0) := x\"{hw_init:0{hex_w}X}\";")
        if algorithm.xor_out:
            lines.append(f"  constant XOR_OUT : std_logic_vector({N-1} downto 0) := x\"{algorithm.xor_out:0{hex_w}X}\";")
        lines.append("")
        lines.append(f"  signal crc_reg    : std_logic_vector({N-1} downto 0) := HW_INIT;")
        lines.append(f"  signal crc_next   : std_logic_vector({N-1} downto 0);")
        lines.append(f"  signal m_tdata_r  : std_logic_vector({N-1} downto 0) := (others => '0');")
        lines.append("  signal m_tvalid_r : std_logic := '0';")
        lines.append("  signal m_tlast_r  : std_logic := '0';")
        lines.append("  -- Internal readable copy of s_axis_tready (VHDL-2008: out ports are not readable)")
        lines.append("  signal s_tready_i : std_logic;")
        lines.append("")
        lines.append("begin")
        lines.append("")

        # ---- CRC core instantiation ----
        lines.append("  -- Combinatorial CRC core (generated separately)")
        lines.append(f"  u_crc_core : entity work.{core_name}(rtl)")
        lines.append("    port map (")
        lines.append("      data_in => s_axis_tdata,")
        lines.append("      crc_in  => crc_reg,")
        lines.append("      crc_out => crc_next")
        lines.append("    );")
        lines.append("")

        # ---- Concurrent output assignments ----
        lines.append("  -- s_tready: pipeline stage ready when output is free or downstream consuming")
        lines.append("  s_tready_i    <= '1' when m_tvalid_r = '0' or m_axis_tready = '1' else '0';")
        lines.append("  s_axis_tready <= s_tready_i;")
        lines.append("  m_axis_tlast  <= m_tlast_r;")
        lines.append("  m_axis_tdata  <= m_tdata_r;")
        lines.append("  m_axis_tvalid <= m_tvalid_r;")
        lines.append("")

        # ---- Clocked pipeline register process ----
        lines.append("  reg_p : process(clk)")
        lines.append("  begin")
        lines.append("    if rising_edge(clk) then")
        lines.append("      if rst_n = '0' then")
        lines.append("        crc_reg    <= HW_INIT;")
        lines.append("        m_tvalid_r <= '0';")
        lines.append("        m_tlast_r  <= '0';")
        lines.append("        m_tdata_r  <= (others => '0');")
        lines.append("      else")
        lines.append("        if s_tready_i = '1' then")
        lines.append("          if s_axis_tvalid = '1' then")
        lines.append("            m_tvalid_r <= '1';")
        lines.append("            m_tlast_r  <= s_axis_tlast;")
        if algorithm.xor_out:
            lines.append("            if s_axis_tlast = '1' then")
            lines.append("              m_tdata_r <= crc_next xor XOR_OUT;")
            lines.append("              crc_reg   <= HW_INIT;")
            lines.append("            else")
            lines.append("              m_tdata_r <= crc_next;")
            lines.append("              crc_reg   <= crc_next;")
            lines.append("            end if;")
        else:
            lines.append("            m_tdata_r <= crc_next;")
            lines.append("            if s_axis_tlast = '1' then")
            lines.append("              crc_reg <= HW_INIT;")
            lines.append("            else")
            lines.append("              crc_reg <= crc_next;")
            lines.append("            end if;")
        lines.append("          else")
        lines.append("            m_tvalid_r <= '0';")
        lines.append("            m_tlast_r  <= '0';")
        lines.append("          end if;")
        lines.append("        end if;")
        lines.append("      end if;")
        lines.append("    end if;")
        lines.append("  end process;")
        lines.append("")
        lines.append("end rtl;")
        lines.append("")

        return "\n".join(lines)

    def _axis_header(
        self,
        algorithm: Algorithm,
        data_width: int,
        core_name: str,
        wrapper_name: str,
    ) -> list[str]:
        sep = "-- " + "=" * 62
        return [
            sep,
            "-- crcZero -- AXI4-Stream CRC Wrapper (VHDL-1993)",
            "-- https://github.com/bard0-design/crcZero",
            "--",
            "-- Author     : Leonardo Capossio - bard0 design <hello@bard0.com>",
            "-- License    : MIT",
            "--",
            f"-- Algorithm  : {algorithm.name}",
            f"-- Wrapper    : {wrapper_name}",
            f"-- CRC core   : {core_name}",
            f"-- Data width : {data_width} bits",
            f"-- Generated  : {self._timestamp()}",
            "--",
            "-- Analyse both files together:",
            f"--   ghdl -a --std=93 {core_name}.vhd {wrapper_name}.vhd",
            sep,
            "",
        ]
