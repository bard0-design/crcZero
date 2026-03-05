#!/usr/bin/env python3
"""
Compute expected CRC-32/ISO-HDLC values for the hw_test hardware test vectors.

Byte ordering for D=32:
  hardware data_in = 0x34333231  ⟺  software bytes b"\x31\x32\x33\x34"
  (data_in[7:0] is the first byte; reflected input feeds from bit 0)

Run:
    python hw_test/sw/expected_crcs.py
"""

import sys
import struct
from pathlib import Path

# Add crcZero source to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from crczero.catalog import CATALOG
from crczero.software_crc import compute_crc

ALG = CATALOG["CRC-32/ISO-HDLC"]


def words_to_bytes(words: list[int]) -> bytes:
    """Convert a list of 32-bit LE words to the equivalent byte stream."""
    return b"".join(struct.pack("<I", w) for w in words)


# ── Test vectors (must match hw_test.tcl) ─────────────────────────────────────
TEST_VECTORS = [
    ("b'1234'     1-word",   [0x34333231]),
    ("b'12345678' 2-word",   [0x34333231, 0x38373635]),
    ("b'00000000' 1-word",   [0x00000000]),
    ("b'FFFFFFFF' 1-word",   [0xFFFFFFFF]),
    ("b'DEADBEEF' 1-word",   [0xEFBEADDE]),
    ("b'AABBCCDD'*2 2-word", [0xDDCCBBAA, 0xDDCCBBAA]),
]


def main():
    print("CRC-32/ISO-HDLC  (poly=0x04C11DB7, init=0xFFFFFFFF, ref, xor=0xFFFFFFFF)")
    print(f"  {'Description':<28}  {'Bytes (hex)':<20}  Expected CRC")
    print("-" * 72)

    for desc, words in TEST_VECTORS:
        data = words_to_bytes(words)
        crc = compute_crc(ALG, data)
        print(f"  {desc:<28}  {data.hex():<20}  0x{crc:08X}")

    print()
    print("Paste these expected values into hw_test/tcl/hw_test.tcl if they differ.")
    print()

    # Cross-check against known check value: CRC of b"123456789" = 0xCBF43926
    check_data = b"123456789"
    computed = compute_crc(ALG, check_data)
    ok = "OK" if computed == ALG.check else "MISMATCH"
    print(f"Self-check: CRC({check_data!r}) = 0x{computed:08X}  ({ok})")


if __name__ == "__main__":
    main()
