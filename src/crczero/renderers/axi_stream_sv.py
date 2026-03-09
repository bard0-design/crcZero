# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""SystemVerilog AXI4-Stream CRC wrapper renderer.

Same logic as the Verilog-2001 wrapper but uses SystemVerilog idioms:
  - 'logic' type for all signals
  - 'always_ff' for the registered pipeline stage
  - Named endmodule: endmodule : <name>
"""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations
from crczero.renderers.axi_stream_verilog import AxiStreamVerilogRenderer, _hw_init


class AxiStreamSVRenderer(AxiStreamVerilogRenderer):
    """Generates a SystemVerilog AXI4-Stream wrapper for the CRC core."""

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
        lines += self._axis_header(algorithm, data_width, core_name, wrapper_name, "//")

        # ---- Module declaration (SV style) ----
        lines.append(f"module {wrapper_name} (")
        lines.append( "    input  logic        clk,")
        lines.append( "    input  logic        rst_n,       // active-low synchronous reset")
        lines.append( "    // AXI4-Stream slave (data in)")
        lines.append(f"    input  logic [{D-1}:0]  s_axis_tdata,")
        lines.append( "    input  logic        s_axis_tvalid,")
        lines.append( "    output logic        s_axis_tready,")
        lines.append( "    input  logic        s_axis_tlast,")
        lines.append( "    // AXI4-Stream master (running CRC out, one beat per input beat)")
        lines.append(f"    output logic [{N-1}:0] m_axis_tdata,")
        lines.append( "    output logic        m_axis_tvalid,")
        lines.append( "    output logic        m_axis_tlast,")
        lines.append( "    input  logic        m_axis_tready")
        lines.append( ");")
        lines.append( "")

        # ---- Constants ----
        lines.append(f"    localparam logic [{N-1}:0] HW_INIT = {N}'h{hw_init:0{hex_w}X};")
        if algorithm.xor_out:
            lines.append(f"    localparam logic [{N-1}:0] XOR_OUT = {N}'h{algorithm.xor_out:0{hex_w}X};")
        lines.append( "")

        # ---- CRC register ----
        lines.append(f"    logic [{N-1}:0] crc_reg;")
        lines.append(f"    logic [{N-1}:0] crc_next;")
        lines.append( "")

        # ---- CRC core instantiation ----
        lines.append( "    // Combinatorial CRC core (generated separately)")
        lines.append(f"    {core_name} u_crc_core (")
        lines.append( "        .data_in (s_axis_tdata),")
        lines.append( "        .crc_in  (crc_reg),")
        lines.append( "        .crc_out (crc_next)")
        lines.append( "    );")
        lines.append( "")

        # ---- s_tready: pipeline stage ready when output is free or downstream consuming ----
        lines.append( "    assign s_axis_tready = !m_axis_tvalid || m_axis_tready;")
        lines.append( "")

        # ---- Pipeline register (always_ff for SV) ----
        lines.append( "    always_ff @(posedge clk) begin")
        lines.append( "        if (!rst_n) begin")
        lines.append( "            crc_reg       <= HW_INIT;")
        lines.append( "            m_axis_tvalid <= 1'b0;")
        lines.append( "            m_axis_tlast  <= 1'b0;")
        lines.append(f"            m_axis_tdata  <= {N}'h0;")
        lines.append( "        end else begin")
        lines.append( "            if (s_axis_tready) begin")
        lines.append( "                if (s_axis_tvalid) begin")
        lines.append( "                    m_axis_tvalid <= 1'b1;")
        lines.append( "                    m_axis_tlast  <= s_axis_tlast;")
        if algorithm.xor_out:
            lines.append( "                    m_axis_tdata  <= s_axis_tlast ? crc_next ^ XOR_OUT : crc_next;")
        else:
            lines.append( "                    m_axis_tdata  <= crc_next;")
        lines.append( "                    crc_reg       <= s_axis_tlast ? HW_INIT : crc_next;")
        lines.append( "                end else begin")
        lines.append( "                    m_axis_tvalid <= 1'b0;")
        lines.append( "                    m_axis_tlast  <= 1'b0;")
        lines.append( "                end")
        lines.append( "            end")
        lines.append( "        end")
        lines.append( "    end")
        lines.append( "")
        lines.append(f"endmodule : {wrapper_name}")
        lines.append( "")

        return "\n".join(lines)

    def _axis_header(self, algorithm, data_width, core_name, wrapper_name, prefix):
        sep = f"{prefix} " + "=" * 62
        return [
            sep,
            f"{prefix} crcZero -- AXI4-Stream CRC Wrapper (SystemVerilog)",
            f"{prefix} https://github.com/bard0-design/crcZero",
            f"{prefix}",
            f"{prefix} Author     : Leonardo Capossio - bard0 design <hello@bard0.com>",
            f"{prefix} License    : MIT",
            f"{prefix}",
            f"{prefix} Algorithm  : {algorithm.name}",
            f"{prefix} Wrapper    : {wrapper_name}",
            f"{prefix} CRC core   : {core_name}",
            f"{prefix} Data width : {data_width} bits",
            f"{prefix} Generated  : {self._timestamp()}",
            f"{prefix}",
            f"{prefix} Compile both files together:",
            f"{prefix}   iverilog -g2012 {core_name}.sv {wrapper_name}.sv ...",
            sep,
            "",
        ]
