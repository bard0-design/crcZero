# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
from crczero.algorithm import Algorithm, poly_from_koopman, poly_to_koopman
from crczero.catalog import CATALOG as catalog
from crczero.generator import CrcGenerator

__all__ = ["Algorithm", "CrcGenerator", "catalog", "poly_from_koopman", "poly_to_koopman"]
__version__ = "1.2.0"
