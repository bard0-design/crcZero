"""VHDL-1993 testbench renderer.

Generates a self-checking testbench that:
- Instantiates the generated CRC DUT entity
- Applies test vectors derived from the software CRC oracle
- Dumps a VCD waveform via GHDL's --vcd flag
- Reports PASS / FAIL per vector via assert / report

Compatible with ghdl:
    ghdl -a crc_dut.vhd crc_dut_tb.vhd
    ghdl -e <entity_name>_tb
    ghdl -r <entity_name>_tb --vcd=<entity_name>_tb.vcd
"""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations
from crczero.renderers.base import Renderer
from crczero.renderers.testbench_verilog import _build_test_vectors


class VhdlTestbenchRenderer(Renderer):
    """Generates a VHDL-1993 self-checking testbench."""

    def render(
        self,
        equations: CrcEquations,
        algorithm: Algorithm,
        data_width: int,
        name: str | None = None,
    ) -> str:
        dut_name = name or self.default_name(algorithm, data_width)
        tb_name = f"{dut_name}_tb"
        N = equations.width
        D = equations.data_width
        hex_w = (N + 3) // 4
        dhex_w = (D + 3) // 4

        vectors = _build_test_vectors(algorithm, data_width, num_random=16)
        num_vectors = len(vectors)

        lines: list[str] = []

        # ---- Header ----
        lines += self._header_comment(algorithm, data_width, dut_name)

        lines.append("library ieee;")
        lines.append("use ieee.std_logic_1164.all;")
        lines.append("use ieee.numeric_std.all;")
        lines.append("")

        # ---- Entity (empty ports for testbench) ----
        lines.append(f"entity {tb_name} is")
        lines.append("end entity;")
        lines.append("")

        # ---- Architecture ----
        lines.append(f"architecture sim of {tb_name} is")
        lines.append("")

        # Signals (no component declaration needed — using direct entity instantiation)
        lines.append(f"    signal data_in : std_logic_vector({D-1} downto 0) := (others => '0');")
        lines.append(f"    signal crc_in  : std_logic_vector({N-1} downto 0) := (others => '0');")
        lines.append(f"    signal crc_out : std_logic_vector({N-1} downto 0);")
        lines.append("")

        # Test vector arrays as constants
        lines.append(f"    type t_slv_n is array (0 to {num_vectors - 1}) of std_logic_vector({N-1} downto 0);")
        lines.append(f"    type t_slv_d is array (0 to {num_vectors - 1}) of std_logic_vector({D-1} downto 0);")
        lines.append("")

        # Build constant arrays
        crc_in_vals = ", ".join(
            f'x"{ci:0{hex_w}X}"' for (ci, _di, _co) in vectors
        )
        data_in_vals = ", ".join(
            f'x"{di:0{dhex_w}X}"' for (_ci, di, _co) in vectors
        )
        expected_vals = ", ".join(
            f'x"{co:0{hex_w}X}"' for (_ci, _di, co) in vectors
        )

        lines.append(f"    constant C_CRC_IN   : t_slv_n := ({crc_in_vals});")
        lines.append(f"    constant C_DATA_IN  : t_slv_d := ({data_in_vals});")
        lines.append(f"    constant C_EXPECTED : t_slv_n := ({expected_vals});")
        lines.append("")

        lines.append("begin")
        lines.append("")

        # DUT instantiation — direct entity instantiation avoids component binding issues
        lines.append(f"    dut : entity work.{dut_name}(rtl)")
        lines.append("        port map (")
        lines.append("            data_in => data_in,")
        lines.append("            crc_in  => crc_in,")
        lines.append("            crc_out => crc_out")
        lines.append("        );")
        lines.append("")

        # Stimulus process
        lines.append("    stim : process")
        lines.append("        variable fail_count : integer := 0;")
        lines.append("    begin")
        lines.append(f"        for i in 0 to {num_vectors - 1} loop")
        lines.append("            crc_in  <= C_CRC_IN(i);")
        lines.append("            data_in <= C_DATA_IN(i);")
        lines.append("            wait for 10 ns;  -- let combinatorial logic settle")
        lines.append("            if crc_out /= C_EXPECTED(i) then")
        lines.append('                report "FAIL vector " & integer\'image(i) severity error;')
        lines.append("                fail_count := fail_count + 1;")
        lines.append("            else")
        lines.append('                report "PASS vector " & integer\'image(i);')
        lines.append("            end if;")
        lines.append("        end loop;")
        lines.append("")
        lines.append("        if fail_count = 0 then")
        lines.append(f'            report "ALL {num_vectors} VECTORS PASSED ({algorithm.name})" severity note;')
        lines.append("        else")
        lines.append(f'            report "FAILURES DETECTED" severity failure;')
        lines.append("        end if;")
        lines.append("        wait;")
        lines.append("    end process;")
        lines.append("")
        lines.append(f"end sim;")
        lines.append("")

        return "\n".join(lines)

    def _header_comment(self, algorithm, data_width, dut_name):
        sep = "-- " + "=" * 62
        return [
            sep,
            "-- crcZero -- VHDL-1993 Testbench",
            "-- https://github.com/bard0-design/crcZero",
            "--",
            "-- Author     : Leonardo Capossio - bard0 design <hello@bard0.com>",
            "-- License    : MIT",
            "--",
            f"-- Algorithm  : {algorithm.name}",
            f"-- DUT entity : {dut_name}",
            f"-- Data width : {data_width} bits",
            f"-- Generated  : {self._timestamp()}",
            "--",
            "-- Simulate with ghdl:",
            f"--   ghdl -a {dut_name}.vhd {dut_name}_tb.vhd",
            f"--   ghdl -e {dut_name}_tb",
            f"--   ghdl -r {dut_name}_tb --vcd={dut_name}_tb.vcd",
            sep,
            "",
        ]
