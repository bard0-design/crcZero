"""CrcGenerator: public-facing API that ties algorithm, equations, and renderers together."""

from __future__ import annotations

from crczero.algorithm import Algorithm
from crczero.equations import CrcEquations, derive_equations
from crczero.software_crc import compute_crc


class CrcGenerator:
    """Generate parallel CRC HDL code in Verilog-2001, SystemVerilog, or VHDL-1993.

    Example usage::

        from crczero import CrcGenerator, catalog

        gen = CrcGenerator(catalog["CRC-32/ISO-HDLC"], data_width=8)
        assert gen.self_test()
        print(gen.generate_verilog())
        print(gen.generate_systemverilog())
        print(gen.generate_vhdl())
    """

    def __init__(self, algorithm: Algorithm, data_width: int = 8) -> None:
        """
        Args:
            algorithm:  Williams model CRC parameters (from catalog or custom).
            data_width: Number of data bits processed in parallel per clock cycle.
                        Must be a positive integer. Common values: 8, 16, 32, 64.
        """
        if data_width < 1:
            raise ValueError(f"data_width must be >= 1, got {data_width}")
        self.algorithm = algorithm
        self.data_width = data_width
        self._equations: CrcEquations | None = None

    # ------------------------------------------------------------------
    # Equation derivation (lazily computed and cached)
    # ------------------------------------------------------------------

    def _get_equations(self) -> CrcEquations:
        if self._equations is None:
            self._equations = derive_equations(self.algorithm, self.data_width)
        return self._equations

    # ------------------------------------------------------------------
    # Self-test
    # ------------------------------------------------------------------

    def self_test(self) -> bool:
        """Verify the algorithm's check value by computing CRC of b'123456789'.

        Returns True if the software CRC matches algorithm.check, False otherwise.
        """
        result = compute_crc(self.algorithm, b"123456789")
        return result == self.algorithm.check

    # ------------------------------------------------------------------
    # HDL generation
    # ------------------------------------------------------------------

    def generate_verilog(self, module_name: str | None = None) -> str:
        """Generate a Verilog-2001 combinatorial CRC module.

        Args:
            module_name: Override the default module name.
                         Default: derived from algorithm name and data width,
                         e.g. 'crc_32_iso_hdlc_d8'.
        Returns:
            String containing the complete Verilog source.
        """
        from crczero.renderers.verilog import VerilogRenderer
        return VerilogRenderer().render(
            self._get_equations(), self.algorithm, self.data_width, module_name
        )

    def generate_systemverilog(self, module_name: str | None = None) -> str:
        """Generate a SystemVerilog combinatorial CRC module.

        Uses 'logic' types and 'endmodule : name' syntax.

        Args:
            module_name: Override the default module name.
        Returns:
            String containing the complete SystemVerilog source.
        """
        from crczero.renderers.systemverilog import SystemVerilogRenderer
        return SystemVerilogRenderer().render(
            self._get_equations(), self.algorithm, self.data_width, module_name
        )

    def generate_vhdl(self, entity_name: str | None = None) -> str:
        """Generate a VHDL-1993 combinatorial CRC entity.

        Args:
            entity_name: Override the default entity name.
        Returns:
            String containing the complete VHDL source (library clause +
            entity + architecture).
        """
        from crczero.renderers.vhdl import VhdlRenderer
        return VhdlRenderer().render(
            self._get_equations(), self.algorithm, self.data_width, entity_name
        )

    def generate_testbench_verilog(self, module_name: str | None = None) -> str:
        """Generate a self-checking Verilog-2001 testbench for iverilog+vvp.

        Args:
            module_name: Override the DUT module name (testbench name is <module>_tb).
        Returns:
            String containing the complete Verilog testbench source.
        """
        from crczero.renderers.testbench_verilog import VerilogTestbenchRenderer
        return VerilogTestbenchRenderer().render(
            self._get_equations(), self.algorithm, self.data_width, module_name
        )

    def generate_testbench_vhdl(self, entity_name: str | None = None) -> str:
        """Generate a self-checking VHDL-1993 testbench for ghdl.

        Args:
            entity_name: Override the DUT entity name (testbench name is <entity>_tb).
        Returns:
            String containing the complete VHDL testbench source.
        """
        from crczero.renderers.testbench_vhdl import VhdlTestbenchRenderer
        return VhdlTestbenchRenderer().render(
            self._get_equations(), self.algorithm, self.data_width, entity_name
        )

    def generate_axi_stream_verilog(self, module_name: str | None = None) -> str:
        """Generate a Verilog-2001 AXI4-Stream wrapper for the CRC core.

        The wrapper instantiates the combinatorial CRC core by name.
        Compile both files together: iverilog <core>.v <wrapper>.v ...

        Args:
            module_name: Override the CRC core name (wrapper is <name>_axis).
        Returns:
            String containing the complete Verilog wrapper source.
        """
        from crczero.renderers.axi_stream_verilog import AxiStreamVerilogRenderer
        return AxiStreamVerilogRenderer().render(
            self._get_equations(), self.algorithm, self.data_width, module_name
        )

    def generate_axi_stream_sv(self, module_name: str | None = None) -> str:
        """Generate a SystemVerilog AXI4-Stream wrapper for the CRC core.

        Args:
            module_name: Override the CRC core name (wrapper is <name>_axis).
        Returns:
            String containing the complete SystemVerilog wrapper source.
        """
        from crczero.renderers.axi_stream_sv import AxiStreamSVRenderer
        return AxiStreamSVRenderer().render(
            self._get_equations(), self.algorithm, self.data_width, module_name
        )

    def generate_axi_stream_vhdl(self, entity_name: str | None = None) -> str:
        """Generate a VHDL-1993 AXI4-Stream wrapper for the CRC core.

        Uses direct entity instantiation. Analyse both files together:
            ghdl -a --std=93 <core>.vhd <wrapper>.vhd

        Args:
            entity_name: Override the CRC core entity name (wrapper is <name>_axis).
        Returns:
            String containing the complete VHDL wrapper source.
        """
        from crczero.renderers.axi_stream_vhdl import AxiStreamVhdlRenderer
        return AxiStreamVhdlRenderer().render(
            self._get_equations(), self.algorithm, self.data_width, entity_name
        )
