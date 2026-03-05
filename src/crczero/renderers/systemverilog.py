"""SystemVerilog renderer for parallel CRC modules."""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations
from crczero.renderers.verilog import VerilogRenderer


class SystemVerilogRenderer(VerilogRenderer):
    """Generates synthesizable SystemVerilog parallel CRC modules.

    Differences from Verilog-2001:
    - Uses 'logic' type instead of implicit wire
    - Named endmodule: endmodule : <name>
    - assign statements are identical (valid in both SV and V)
    """

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

        lines: list[str] = []

        # ---- Header comment ----
        lines += self._header_comment(algorithm, data_width, module_name, "//")

        # ---- Module declaration (SV style) ----
        lines.append(f"module {module_name} (")
        lines.append(f"    input  logic [{D-1}:0]  data_in,")
        lines.append(f"    input  logic [{N-1}:0] crc_in,")
        lines.append(f"    output logic [{N-1}:0] crc_out")
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
        lines.append(f"endmodule : {module_name}")
        lines.append("")

        return "\n".join(lines)
