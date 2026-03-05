"""Verilog-2001 renderer for parallel CRC modules."""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations
from crczero.renderers.base import Renderer


class VerilogRenderer(Renderer):
    """Generates synthesizable Verilog-2001 parallel CRC modules."""

    def render(
        self,
        equations: CrcEquations,
        algorithm: Algorithm,
        data_width: int,
        name: str | None = None,
    ) -> str:
        module_name = name or self.default_name(algorithm, data_width)
        N = equations.width
        D = equations.data_width
        hex_w = (N + 3) // 4  # nibbles for formatting

        lines: list[str] = []

        # ---- Header comment ----
        lines += self._header_comment(algorithm, data_width, module_name, "//")

        # ---- Module declaration ----
        lines.append(f"module {module_name} (")
        lines.append(f"    input  [{D-1}:0]  data_in,")
        lines.append(f"    input  [{N-1}:0] crc_in,")
        lines.append(f"    output [{N-1}:0] crc_out")
        lines.append(");")
        lines.append("")

        # ---- Combinatorial equations ----
        for i in range(N):
            terms = self._equation_terms(i, equations)
            if not terms:
                lines.append(f"    assign crc_out[{i}] = 1'b0;")
            elif len(terms) == 1:
                lines.append(f"    assign crc_out[{i}] = {terms[0]};")
            else:
                lines.append(f"    assign crc_out[{i}] = {' ^ '.join(terms)};")

        lines.append("")
        lines.append(f"endmodule  // {module_name}")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _hw_init(algorithm: Algorithm) -> int:
        """Hardware reset value for crc_in.

        For reflected algorithms (ref_in=True) the DUT operates in LFSR-register
        space, which is the bit-reversal of the Williams register.  The first
        word must therefore be driven with bit_reverse(Williams_init).
        For normal algorithms the Williams init is used directly.
        """
        if algorithm.ref_in:
            N = algorithm.width
            v = algorithm.init
            r = 0
            for _ in range(N):
                r = (r << 1) | (v & 1)
                v >>= 1
            return r
        return algorithm.init

    def _header_comment(
        self,
        algorithm: Algorithm,
        data_width: int,
        module_name: str,
        prefix: str,
    ) -> list[str]:
        N = algorithm.width
        hex_w = (N + 3) // 4
        hw_init = self._hw_init(algorithm)
        xor_hex = f"0x{algorithm.xor_out:0{hex_w}X}"
        check_hex = f"0x{algorithm.check:0{hex_w}X}"

        sep = f"{prefix} " + "=" * 62
        lines = [
            sep,
            f"{prefix} crcZero -- CRC HDL Generator",
            f"{prefix} https://github.com/bard0-design/crcZero",
            f"{prefix}",
            f"{prefix} Author     : Leonardo Capossio - bard0 design <hello@bard0.com>",
            f"{prefix} License    : MIT",
            f"{prefix}",
            f"{prefix} Algorithm  : {algorithm.name}",
            f"{prefix} CRC width  : {N} bits",
            f"{prefix} Polynomial : 0x{algorithm.poly:0{hex_w}X}",
            f"{prefix} Init       : 0x{algorithm.init:0{hex_w}X}",
            f"{prefix} RefIn      : {algorithm.ref_in}",
            f"{prefix} RefOut     : {algorithm.ref_out}",
            f"{prefix} XorOut     : {xor_hex}",
            f"{prefix} Check      : {check_hex}",
            f"{prefix} Data width : {data_width} bits",
            f"{prefix} Generated  : {self._timestamp()}",
            f"{prefix}",
            f"{prefix} Usage:",
            f"{prefix}   - Set crc_in = {N}'h{hw_init:0{hex_w}X} for the first word.",
            f"{prefix}   - Chain crc_out -> crc_in for subsequent words.",
        ]
        if hw_init != algorithm.init:
            lines.append(
                f"{prefix}     (hardware reset = bit_reverse(init) for reflected algorithms)"
            )
        if algorithm.xor_out:
            lines.append(
                f"{prefix}   - Final CRC = crc_out ^ {N}'h{algorithm.xor_out:0{hex_w}X}."
            )
        else:
            lines.append(f"{prefix}   - Final CRC = crc_out (no XOR needed).")
        lines.append(sep)
        lines.append("")
        return lines
