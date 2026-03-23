# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""C reference implementation renderer.

Generates a portable C header/source pair for the selected CRC algorithm.
"""

from __future__ import annotations

from crczero.algorithm import Algorithm


class CRenderer:
    """Render a portable C reference implementation for a CRC algorithm."""

    @staticmethod
    def _sanitize_name(name: str) -> str:
        safe = name.lower()
        for ch in (".", "/", "-", " ", "(", ")", "+"):
            safe = safe.replace(ch, "_")
        while "__" in safe:
            safe = safe.replace("__", "_")
        safe = safe.strip("_")
        if not safe:
            safe = "crc"
        if safe[0].isdigit():
            safe = f"crc_{safe}"
        if not safe.startswith("crc_"):
            safe = f"crc_{safe}"
        return safe

    @staticmethod
    def _macro_prefix(base_name: str) -> str:
        return base_name.upper()

    def default_basename(self, algorithm: Algorithm) -> str:
        return self._sanitize_name(algorithm.name)

    def render(
        self,
        algorithm: Algorithm,
        base_name: str | None = None,
        header_filename: str | None = None,
    ) -> tuple[str, str]:
        """Render the C header and source strings.

        Args:
            algorithm: CRC parameters (Williams model).
            base_name: Override the base name for functions/macros.
            header_filename: Optional header filename for the C source include.
        Returns:
            (header_str, source_str)
        """
        base = self._sanitize_name(base_name or self.default_basename(algorithm))
        macro = self._macro_prefix(base)
        width = algorithm.width
        hex_w = (width + 3) // 4
        header_guard = f"{macro}_H_"

        poly = f"0x{algorithm.poly:0{hex_w}X}ULL"
        init = f"0x{algorithm.init:0{hex_w}X}ULL"
        xor_out = f"0x{algorithm.xor_out:0{hex_w}X}ULL"
        check = f"0x{algorithm.check:0{hex_w}X}ULL"
        residue = f"0x{algorithm.residue:0{hex_w}X}ULL"

        header_lines = [
            f"#ifndef {header_guard}",
            f"#define {header_guard}",
            "",
            "#include <stddef.h>",
            "#include <stdint.h>",
            "",
            f"#define {macro}_WIDTH   {width}u",
            f"#define {macro}_POLY    {poly}",
            f"#define {macro}_INIT    {init}",
            f"#define {macro}_XOR_OUT {xor_out}",
            f"#define {macro}_REF_IN  {1 if algorithm.ref_in else 0}u",
            f"#define {macro}_REF_OUT {1 if algorithm.ref_out else 0}u",
            f"#define {macro}_CHECK   {check}",
            f"#define {macro}_RESIDUE {residue}",
            "",
            f"uint64_t {base}_init(void);",
            f"uint64_t {base}_update(uint64_t crc, const uint8_t *data, size_t len);",
            f"uint64_t {base}_finalize(uint64_t crc);",
            f"uint64_t {base}(const uint8_t *data, size_t len);",
            f"void {base}_self_test(void);",
            "",
            f"#endif  // {header_guard}",
            "",
        ]

        header_name = header_filename or f"{base}.h"
        source_lines = [
            f'#include "{header_name}"',
            "#include <assert.h>",
            "",
            "static uint64_t crc_mask(unsigned width)",
            "{",
            "    if (width >= 64u) {",
            "        return UINT64_MAX;",
            "    }",
            "    return (1ULL << width) - 1ULL;",
            "}",
            "",
            "static uint64_t crc_reflect(uint64_t value, unsigned width)",
            "{",
            "    uint64_t result = 0;",
            "    for (unsigned i = 0; i < width; ++i) {",
            "        result = (result << 1) | (value & 1ULL);",
            "        value >>= 1U;",
            "    }",
            "    return result;",
            "}",
            "",
            f"uint64_t {base}_init(void)",
            "{",
            f"    return {macro}_INIT & crc_mask({macro}_WIDTH);",
            "}",
            "",
            f"uint64_t {base}_update(uint64_t crc, const uint8_t *data, size_t len)",
            "{",
            f"    const uint64_t poly = {macro}_POLY & crc_mask({macro}_WIDTH);",
            f"    uint64_t reg = crc & crc_mask({macro}_WIDTH);",
            "",
            "    for (size_t idx = 0; idx < len; ++idx) {",
            "        uint8_t byte = data[idx];",
            f"        if ({macro}_REF_IN) {{",
            "            byte = (uint8_t)crc_reflect(byte, 8);",
            "        }",
            "        for (int i = 7; i >= 0; --i) {",
            "            uint64_t bit = (uint64_t)((byte >> i) & 1U);",
            f"            uint64_t feedback = ((reg >> ({macro}_WIDTH - 1U)) ^ bit) & 1ULL;",
            "            if (feedback) {",
            "                reg = ((reg << 1) ^ poly) & crc_mask(" + f"{macro}_WIDTH" + ");",
            "            } else {",
            "                reg = (reg << 1) & crc_mask(" + f"{macro}_WIDTH" + ");",
            "            }",
            "        }",
            "    }",
            "",
            "    return reg;",
            "}",
            "",
            f"uint64_t {base}_finalize(uint64_t crc)",
            "{",
            f"    uint64_t reg = crc & crc_mask({macro}_WIDTH);",
            f"    if ({macro}_REF_OUT) {{",
            f"        reg = crc_reflect(reg, {macro}_WIDTH);",
            "    }",
            f"    reg ^= {macro}_XOR_OUT;",
            f"    return reg & crc_mask({macro}_WIDTH);",
            "}",
            "",
            f"uint64_t {base}(const uint8_t *data, size_t len)",
            "{",
            f"    uint64_t reg = {base}_init();",
            f"    reg = {base}_update(reg, data, len);",
            f"    return {base}_finalize(reg);",
            "}",
            "",
            f"void {base}_self_test(void)",
            "{",
            '    static const uint8_t test_data[] = "123456789";',
            f"    assert({base}(test_data, 9) == {macro}_CHECK);",
            "}",
            "",
        ]

        return "\n".join(header_lines), "\n".join(source_lines)
