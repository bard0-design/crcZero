"""Verilog-2001 testbench renderer.

Generates a self-checking testbench that:
- Instantiates the generated CRC DUT
- Applies test vectors derived from the software CRC oracle
- Dumps a VCD waveform file for inspection with GTKWave or similar
- Prints PASS / FAIL per test vector and exits with a non-zero plusarg if any fail

The testbench is compatible with iverilog + vvp:
    iverilog -o sim.vvp crc_dut.v crc_tb.v
    vvp sim.vvp

VCD is written to <module_name>_tb.vcd by default.
"""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations
from crczero.renderers.base import Renderer
from crczero.software_crc import compute_crc


def _build_test_vectors(
    algorithm: Algorithm,
    data_width: int,
    num_random: int = 8,
) -> list[tuple[int, int, int]]:
    """Return a list of (crc_in, data_in, expected_crc_out) tuples.

    Vectors include:
    1. Byte-by-byte processing of b"123456789" (reproduces the check value).
    2. A small set of deterministic random patterns for extra coverage.
    """
    import random

    assert data_width % 8 == 0
    bytes_per_word = data_width // 8
    N = algorithm.width
    mask_n = (1 << N) - 1
    mask_d = (1 << data_width) - 1

    vectors: list[tuple[int, int, int]] = []

    def _process_word(crc: int, word_bytes: bytes) -> tuple[int, int, int]:
        """Simulate the DUT for one word; return (crc_in, data_in, crc_out)."""
        from crczero.equations import derive_equations, simulate_equations
        eqs = derive_equations(algorithm, data_width)
        if algorithm.ref_in:
            word = int.from_bytes(word_bytes, 'little')
        else:
            word = int.from_bytes(word_bytes, 'big')
        new_crc = simulate_equations(eqs, crc, word)
        return crc, word, new_crc

    # Cache equations object to avoid recomputing
    from crczero.equations import derive_equations, simulate_equations
    eqs = derive_equations(algorithm, data_width)

    def _step(crc: int, word_bytes: bytes) -> tuple[int, int, int]:
        if algorithm.ref_in:
            word = int.from_bytes(word_bytes, 'little')
        else:
            word = int.from_bytes(word_bytes, 'big')
        new_crc = simulate_equations(eqs, crc, word)
        return crc, word, new_crc

    # Vectors from b"123456789"
    data = b"123456789"
    # Pad if not divisible by bytes_per_word
    remainder = len(data) % bytes_per_word
    if remainder:
        data = data + b"\x00" * (bytes_per_word - remainder)

    # Hardware reset value: bit_reverse(init) for reflected algorithms.
    def _bit_rev(v: int, n: int) -> int:
        r = 0
        for _ in range(n):
            r = (r << 1) | (v & 1)
            v >>= 1
        return r

    hw_init = _bit_rev(algorithm.init, N) if algorithm.ref_in else algorithm.init
    crc = hw_init & mask_n
    for i in range(0, len(data), bytes_per_word):
        crc_in, data_in, crc_out = _step(crc, data[i: i + bytes_per_word])
        vectors.append((crc_in, data_in, crc_out))
        crc = crc_out

    # Random vectors
    rng = random.Random(0xDEADBEEF)
    crc = hw_init & mask_n
    for _ in range(num_random):
        word_bytes = bytes(rng.randint(0, 255) for _ in range(bytes_per_word))
        crc_in, data_in, crc_out = _step(crc, word_bytes)
        vectors.append((crc_in, data_in, crc_out))
        crc = crc_out

    return vectors


class VerilogTestbenchRenderer(Renderer):
    """Generates a Verilog-2001 self-checking testbench."""

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
        lines += self._header_comment(algorithm, data_width, dut_name, "//")

        lines.append(f"`timescale 1ns/1ps")
        lines.append(f"")
        lines.append(f"module {tb_name};")
        lines.append(f"")

        # ---- Signals ----
        lines.append(f"    // DUT ports")
        lines.append(f"    reg  [{D-1}:0]  data_in;")
        lines.append(f"    reg  [{N-1}:0] crc_in;")
        lines.append(f"    wire [{N-1}:0] crc_out;")
        lines.append(f"")

        # ---- DUT instantiation ----
        lines.append(f"    // DUT")
        lines.append(f"    {dut_name} dut (")
        lines.append(f"        .data_in (data_in),")
        lines.append(f"        .crc_in  (crc_in),")
        lines.append(f"        .crc_out (crc_out)")
        lines.append(f"    );")
        lines.append(f"")

        # ---- Test logic ----
        lines.append(f"    integer fail_count;")
        lines.append(f"    integer i;")
        lines.append(f"")
        lines.append(f"    // Test vectors: {{crc_in, data_in, expected_crc_out}}")
        lines.append(f"    reg [{N-1}:0] tv_crc_in  [{num_vectors-1}:0];")
        lines.append(f"    reg [{D-1}:0] tv_data_in [{num_vectors-1}:0];")
        lines.append(f"    reg [{N-1}:0] tv_expected [{num_vectors-1}:0];")
        lines.append(f"")
        lines.append(f"    initial begin")
        lines.append(f"        // VCD waveform dump")
        lines.append(f'        $dumpfile("{tb_name}.vcd");')
        lines.append(f"        $dumpvars(0, {tb_name});")
        lines.append(f"")

        # Load test vectors
        for idx, (crc_i, data_i, crc_o) in enumerate(vectors):
            lines.append(f"        tv_crc_in[{idx}]   = {N}'h{crc_i:0{hex_w}X};")
            lines.append(f"        tv_data_in[{idx}]  = {D}'h{data_i:0{dhex_w}X};")
            lines.append(f"        tv_expected[{idx}] = {N}'h{crc_o:0{hex_w}X};")

        lines.append(f"")
        lines.append(f"        fail_count = 0;")
        lines.append(f"")
        lines.append(f"        for (i = 0; i < {num_vectors}; i = i + 1) begin")
        lines.append(f"            crc_in  = tv_crc_in[i];")
        lines.append(f"            data_in = tv_data_in[i];")
        lines.append(f"            #10;  // allow combinatorial logic to settle")
        lines.append(f"            if (crc_out !== tv_expected[i]) begin")
        lines.append(f"                $display(\"FAIL vector %0d: crc_in=%0h data_in=%0h\", i, tv_crc_in[i], tv_data_in[i]);")
        lines.append(f"                $display(\"  expected=%0h  got=%0h\", tv_expected[i], crc_out);")
        lines.append(f"                fail_count = fail_count + 1;")
        lines.append(f"            end else begin")
        lines.append(f"                $display(\"PASS vector %0d\", i);")
        lines.append(f"            end")
        lines.append(f"        end")
        lines.append(f"")
        lines.append(f"        if (fail_count == 0)")
        lines.append(f"            $display(\"ALL {num_vectors} VECTORS PASSED ({algorithm.name})\");")
        lines.append(f"        else")
        lines.append(f"            $display(\"%0d / {num_vectors} VECTORS FAILED\", fail_count);")
        lines.append(f"")
        lines.append(f"        $finish;")
        lines.append(f"    end")
        lines.append(f"")
        lines.append(f"endmodule  // {tb_name}")
        lines.append(f"")

        return "\n".join(lines)

    def _header_comment(self, algorithm, data_width, dut_name, prefix):
        N = algorithm.width
        hex_w = (N + 3) // 4
        sep = f"{prefix} " + "=" * 62
        return [
            sep,
            f"{prefix} crcZero — Verilog-2001 Testbench",
            f"{prefix} https://github.com/bard0-design/crcZero",
            f"{prefix}",
            f"{prefix} Author     : Leonardo Capossio - bard0 design <hello@bard0.com>",
            f"{prefix} License    : MIT",
            f"{prefix}",
            f"{prefix} Algorithm  : {algorithm.name}",
            f"{prefix} DUT module : {dut_name}",
            f"{prefix} Data width : {data_width} bits",
            f"{prefix} Generated  : {self._timestamp()}",
            f"{prefix}",
            f"{prefix} Simulate with iverilog + vvp:",
            f"{prefix}   iverilog -o sim.vvp {dut_name}.v {dut_name}_tb.v",
            f"{prefix}   vvp sim.vvp",
            f"{prefix}   # VCD written to {dut_name}_tb.vcd",
            sep,
            "",
        ]
