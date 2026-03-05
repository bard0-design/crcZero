from __future__ import annotations

from dataclasses import dataclass


def poly_from_koopman(koopman: int, width: int) -> int:
    """Convert a Koopman-notation polynomial to Williams normal-form.

    Koopman notation omits the implicit trailing +1 term and keeps the
    leading (degree-n) coefficient:
        Koopman:  0x82608EDB  (CRC-32)
        Normal:   0x04C11DB7  (CRC-32)

    Conversion:  normal = ((koopman << 1) | 1) & ((1 << width) - 1)
    """
    return ((koopman << 1) | 1) & ((1 << width) - 1)


def poly_to_koopman(poly: int, width: int) -> int:
    """Convert a Williams normal-form polynomial to Koopman notation.

    Conversion:  koopman = (poly | (1 << width)) >> 1
    """
    return (poly | (1 << width)) >> 1


@dataclass(frozen=True)
class Algorithm:
    """CRC algorithm parameters using the Williams model.

    All parameter values follow the convention from:
    Ross Williams, "A Painless Guide to CRC Error Detection Algorithms"
    and the reveng CRC catalogue (https://reveng.sourceforge.io/crc-catalogue/).
    """

    name: str
    width: int      # CRC register width in bits
    poly: int       # Generator polynomial (normal/explicit+1 form, MSB implicit)
    init: int       # Initial register value
    ref_in: bool    # Reflect each input byte before processing
    ref_out: bool   # Reflect the final register before applying xor_out
    xor_out: int    # XOR mask applied to the final register value
    check: int      # Expected CRC of ASCII b"123456789" (self-test value)
    residue: int    # Expected register value after feeding a valid message + its CRC
