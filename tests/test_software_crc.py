# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Validate software CRC oracle against all catalog check values."""

import pytest
from crczero.catalog import CATALOG
from crczero.software_crc import compute_crc, verify_check_value


@pytest.mark.parametrize("name", list(CATALOG.keys()))
def test_check_value(name):
    """Every catalog algorithm must produce its stated check value for b'123456789'."""
    alg = CATALOG[name]
    assert verify_check_value(alg), (
        f"{name}: expected check=0x{alg.check:0{(alg.width+3)//4}X}, "
        f"got 0x{compute_crc(alg, b'123456789'):0{(alg.width+3)//4}X}"
    )


def test_crc16_modbus_known_vector():
    """CRC-16/MODBUS against a standard Modbus frame vector."""
    alg = CATALOG["CRC-16/MODBUS"]
    # Read-holding-registers request: func 0x03, address 0x0000, count 0x0002
    # CRC = 0xC40B (well-known Modbus reference value)
    # The 16-bit integer is 0x0BC4. In a Modbus frame bytes are transmitted
    # low-byte first (C4 then 0B), but the actual CRC integer value is 0x0BC4.
    assert compute_crc(alg, b"\x01\x03\x00\x00\x00\x02") == 0x0BC4


def test_crc8_smbus_zero_byte():
    """CRC-8/SMBUS: single zero byte with init=0 gives 0."""
    alg = CATALOG["CRC-8/SMBUS"]
    assert compute_crc(alg, b"\x00") == 0x00


def test_empty_data_mpeg2():
    """Empty input returns init for MPEG-2 (no ref_out, xor_out=0)."""
    alg = CATALOG["CRC-32/MPEG-2"]  # ref_in=False, ref_out=False, xor_out=0
    assert compute_crc(alg, b"") == 0xFFFFFFFF


def test_empty_data_crc32_iso_hdlc():
    """CRC-32/ISO-HDLC: empty input = init XOR xor_out after reflect = 0."""
    alg = CATALOG["CRC-32/ISO-HDLC"]
    # No bytes: reg = init = 0xFFFFFFFF; reflect → 0xFFFFFFFF; XOR 0xFFFFFFFF = 0
    assert compute_crc(alg, b"") == 0x00000000
