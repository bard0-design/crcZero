"""Pure-Python Williams model CRC calculator.

This is the golden reference implementation used for:
- Validating catalog entries against their 'check' values
- Cross-checking the parallel equation derivation in equations.py
- Generating test vectors for testbench generation

The algorithm follows the model described in:
  Ross Williams, "A Painless Guide to CRC Error Detection Algorithms"
  https://zlib.net/crc_v3.txt
"""

from crczero.algorithm import Algorithm


def _reflect(value: int, width: int) -> int:
    """Reflect (reverse) the bits of 'value' within 'width' bits."""
    result = 0
    for _ in range(width):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def compute_crc(algorithm: Algorithm, data: bytes) -> int:
    """Compute CRC over 'data' using the Williams model algorithm parameters.

    Uses a bit-serial LFSR that is correct for all CRC widths (1 to 64+).
    Returns the final CRC value (after xor_out is applied).
    """
    width = algorithm.width
    poly = algorithm.poly
    mask = (1 << width) - 1

    reg = algorithm.init & mask

    for byte in data:
        if algorithm.ref_in:
            byte = _reflect(byte, 8)

        # Process each bit MSB-first.
        # For reflected algorithms the byte is already reflected above,
        # so this is equivalent to feeding the original byte LSB-first.
        for i in range(7, -1, -1):
            bit = (byte >> i) & 1
            # feedback = MSB of register XOR incoming data bit
            feedback = ((reg >> (width - 1)) ^ bit) & 1
            if feedback:
                reg = ((reg << 1) ^ poly) & mask
            else:
                reg = (reg << 1) & mask

    if algorithm.ref_out:
        reg = _reflect(reg, width)

    return (reg ^ algorithm.xor_out) & mask


def verify_check_value(algorithm: Algorithm) -> bool:
    """Verify the algorithm's 'check' field against computing CRC of b'123456789'."""
    result = compute_crc(algorithm, b"123456789")
    return result == algorithm.check
