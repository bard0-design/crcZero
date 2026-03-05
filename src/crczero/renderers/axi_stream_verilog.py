"""Verilog-2001 AXI4-Stream CRC wrapper renderer.

Wraps the existing combinatorial CRC core with a clocked AXI4-Stream interface.

Interface summary
-----------------
  Slave  (input):  s_axis_tdata / tvalid / tready / tlast
  Master (output): m_axis_tdata / tvalid / tready / tlast

Pipeline register design
------------------------
  m_axis_tvalid is high for every accepted slave beat (running/partial CRC).
  m_axis_tlast mirrors s_axis_tlast — marks the final beat of each packet.
  m_axis_tdata carries the partial CRC on every beat; the XOR-out adjusted
  final CRC appears on the tlast beat.

  s_axis_tready = !m_axis_tvalid || m_axis_tready
  (slave stalls only when the output register is occupied and the downstream
   is not consuming it).

  crc_reg resets to HW_INIT on the tlast beat so the next packet starts fresh.

hw_init and xor_out are embedded as localparams.  No generic parameters.

Compatible with iverilog, yosys, Quartus, Vivado.
"""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations
from crczero.renderers.base import Renderer


def _hw_init(algorithm: Algorithm) -> int:
    """Hardware CRC reset value (bit-reversed init for reflected algorithms)."""
    N = algorithm.width
    v = algorithm.init
    if algorithm.ref_in:
        r = 0
        for _ in range(N):
            r = (r << 1) | (v & 1)
            v >>= 1
        return r
    return v


class AxiStreamVerilogRenderer(Renderer):
    """Generates a Verilog-2001 AXI4-Stream wrapper for the CRC core."""

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

        # ---- Module declaration ----
        lines.append(f"module {wrapper_name} (")
        lines.append( "    input  wire        clk,")
        lines.append( "    input  wire        rst_n,       // active-low synchronous reset")
        lines.append( "    // AXI4-Stream slave (data in)")
        lines.append(f"    input  wire [{D-1}:0]  s_axis_tdata,")
        lines.append( "    input  wire        s_axis_tvalid,")
        lines.append( "    output wire        s_axis_tready,")
        lines.append( "    input  wire        s_axis_tlast,")
        lines.append( "    // AXI4-Stream master (running CRC out, one beat per input beat)")
        lines.append(f"    output reg  [{N-1}:0] m_axis_tdata,")
        lines.append( "    output reg         m_axis_tvalid,")
        lines.append( "    output reg         m_axis_tlast,")
        lines.append( "    input  wire        m_axis_tready")
        lines.append( ");")
        lines.append( "")

        # ---- Constants ----
        lines.append(f"    localparam [{N-1}:0] HW_INIT = {N}'h{hw_init:0{hex_w}X};")
        if algorithm.xor_out:
            lines.append(f"    localparam [{N-1}:0] XOR_OUT = {N}'h{algorithm.xor_out:0{hex_w}X};")
        lines.append( "")

        # ---- CRC register ----
        lines.append(f"    reg [{N-1}:0] crc_reg;")
        lines.append(f"    wire [{N-1}:0] crc_next;")
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

        # ---- Pipeline register ----
        lines.append( "    always @(posedge clk) begin")
        lines.append( "        if (!rst_n) begin")
        lines.append( "            crc_reg       <= HW_INIT;")
        lines.append( "            m_axis_tvalid <= 1'b0;")
        lines.append( "            m_axis_tlast  <= 1'b0;")
        lines.append(f"            m_axis_tdata  <= {{{N}{{1'b0}}}};")
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
        lines.append(f"endmodule  // {wrapper_name}")
        lines.append( "")

        return "\n".join(lines)

    def _axis_header(
        self,
        algorithm: Algorithm,
        data_width: int,
        core_name: str,
        wrapper_name: str,
        prefix: str,
    ) -> list[str]:
        sep = f"{prefix} " + "=" * 62
        return [
            sep,
            f"{prefix} crcZero -- AXI4-Stream CRC Wrapper (Verilog-2001)",
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
            f"{prefix}   iverilog {core_name}.v {wrapper_name}.v ...",
            sep,
            "",
        ]
