# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Abstract base class for HDL renderers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations


class Renderer(ABC):
    """Base class for Verilog / SystemVerilog / VHDL renderers."""

    @abstractmethod
    def render(
        self,
        equations: CrcEquations,
        algorithm: Algorithm,
        data_width: int,
        name: str | None = None,
    ) -> str:
        """Render the CRC module as a string of HDL source code."""
        ...

    def default_name(self, algorithm: Algorithm, data_width: int) -> str:
        """Generate a safe HDL identifier from the algorithm name and data width."""
        safe = algorithm.name.lower()
        for ch in (".", "/", "-", " ", "(", ")"):
            safe = safe.replace(ch, "_")
        # Collapse consecutive underscores
        while "__" in safe:
            safe = safe.replace("__", "_")
        safe = safe.strip("_")
        return f"{safe}_d{data_width}"

    def _xor_chain(self, terms: list[str]) -> str:
        """Build an XOR expression string from a list of signal name strings."""
        if not terms:
            return None  # caller decides how to represent constant 0
        return " ^ ".join(terms)

    def _equation_terms(
        self,
        bit: int,
        equations: CrcEquations,
        crc_signal: str = "crc_in",
        data_signal: str = "data_in",
        index_fmt: str = "[{i}]",
    ) -> list[str]:
        """Return the list of signal reference strings for crc_out[bit]."""
        terms: list[str] = []
        for j in sorted(equations.crc_terms[bit]):
            terms.append(f"{crc_signal}{index_fmt.format(i=j)}")
        for k in sorted(equations.data_terms[bit]):
            terms.append(f"{data_signal}{index_fmt.format(i=k)}")
        return terms

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
