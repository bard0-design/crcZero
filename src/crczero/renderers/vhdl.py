# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""VHDL-1993 renderer for parallel CRC modules."""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations
from crczero.renderers.base import Renderer


class VhdlRenderer(Renderer):
    """Generates synthesizable VHDL-1993 parallel CRC entities.

    Output is compatible with VHDL-1993 (IEEE Std 1076-1993):
    - 'end <name>;' form (no 'entity'/'architecture' keyword after end)
    - std_logic_vector for all ports
    - Concurrent signal assignments with the 'xor' operator
    """

    def render(
        self,
        equations: CrcEquations,
        algorithm: Algorithm,
        data_width: int,
        name: str | None = None,
    ) -> str:
        entity_name = name or self.default_name(algorithm, data_width)
        N = equations.width
        D = equations.data_width

        lines: list[str] = []

        # ---- Header comment ----
        lines += self._header_comment(algorithm, data_width, entity_name)

        # ---- Library / use ----
        lines.append("library ieee;")
        lines.append("use ieee.std_logic_1164.all;")
        lines.append("")

        # ---- Entity (VHDL-1993: 'end <name>;') ----
        lines.append(f"entity {entity_name} is")
        lines.append("  port (")
        lines.append(f"    data_in : in  std_logic_vector({D-1} downto 0);")
        lines.append(f"    crc_in  : in  std_logic_vector({N-1} downto 0);")
        lines.append(f"    crc_out : out std_logic_vector({N-1} downto 0)")
        lines.append("  );")
        lines.append(f"end {entity_name};")
        lines.append("")

        # ---- Architecture (VHDL-1993: 'end rtl;') ----
        lines.append(f"architecture rtl of {entity_name} is")
        lines.append("begin")
        lines.append("")

        for i in range(N):
            terms = self._equation_terms(
                i,
                equations,
                crc_signal="crc_in",
                data_signal="data_in",
                index_fmt="({i})",  # VHDL uses parentheses for array indexing
            )
            if not terms:
                lines.append(f"  crc_out({i}) <= '0';")
            elif len(terms) == 1:
                lines.append(f"  crc_out({i}) <= {terms[0]};")
            else:
                lines.append(f"  crc_out({i}) <= {' xor '.join(terms)};")

        lines.append("")
        lines.append("end rtl;")
        lines.append("")

        return "\n".join(lines)

    def _header_comment(
        self,
        algorithm: Algorithm,
        data_width: int,
        entity_name: str,
    ) -> list[str]:
        N = algorithm.width
        hex_w = (N + 3) // 4
        sep = "-- " + "=" * 62

        lines = [
            sep,
            "-- crcZero -- CRC HDL Generator",
            "-- https://github.com/bard0-design/crcZero",
            "--",
            "-- Author     : Leonardo Capossio - bard0 design <hello@bard0.com>",
            "-- License    : MIT",
            "--",
            f"-- Algorithm  : {algorithm.name}",
            f"-- CRC width  : {N} bits",
            f"-- Polynomial : 0x{algorithm.poly:0{hex_w}X}",
            f"-- Init       : 0x{algorithm.init:0{hex_w}X}",
            f"-- RefIn      : {algorithm.ref_in}",
            f"-- RefOut     : {algorithm.ref_out}",
            f"-- XorOut     : 0x{algorithm.xor_out:0{hex_w}X}",
            f"-- Check      : 0x{algorithm.check:0{hex_w}X}",
            f"-- Data width : {data_width} bits",
            f"-- Generated  : {self._timestamp()}",
            "--",
            "-- Usage:",
            f'--   Set crc_in = x"{algorithm.init:0{hex_w}X}" for the first word.',
            "--   Chain crc_out -> crc_in for subsequent words.",
        ]
        if algorithm.xor_out:
            lines.append(
                f'--   Final CRC = crc_out xor x"{algorithm.xor_out:0{hex_w}X}".'
            )
        else:
            lines.append("--   Final CRC = crc_out (no XOR needed).")
        lines.append(sep)
        lines.append("")
        return lines
