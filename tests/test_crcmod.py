"""Cross-validate our software_crc oracle against crcmod (independent implementation).

crcmod is a well-established Python CRC library used in production systems.
Matching it for all catalog algorithms gives high confidence that our software
oracle is correct independently of the reveng catalogue check values.

Skipped automatically when crcmod is not installed.
"""

import pytest

crcmod = pytest.importorskip("crcmod", reason="crcmod not installed — pip install crcmod")

from crczero.catalog import CATALOG
from crczero.software_crc import compute_crc


def _bit_reverse(value: int, width: int) -> int:
    result = 0
    for _ in range(width):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def _make_crcmod_fn(alg):
    """Build a crcmod function from a Williams-model Algorithm.

    Parameter mapping (empirically verified):
    crcmod stores the register pre-XOR'd with xorOut, so:
    - For reflected CRCs (ref_in=True):
        initCrc = bit_reverse(alg.init, alg.width) XOR alg.xor_out
    - For normal CRCs (ref_in=False):
        initCrc = alg.init XOR alg.xor_out
    xorOut is passed through unchanged in both cases.
    full_poly includes the implicit leading bit: full_poly = alg.poly | (1 << alg.width).
    """
    full_poly = alg.poly | (1 << alg.width)
    if alg.ref_in:
        init_crc = _bit_reverse(alg.init, alg.width) ^ alg.xor_out
        return crcmod.mkCrcFun(full_poly, initCrc=init_crc, rev=True, xorOut=alg.xor_out)
    else:
        init_crc = alg.init ^ alg.xor_out
        return crcmod.mkCrcFun(full_poly, initCrc=init_crc, rev=False, xorOut=alg.xor_out)


# Algorithms to cross-validate — covers all combinations of ref_in/ref_out and
# varied init/xor_out values.
# Note: crcmod only supports CRC widths >= 8; sub-byte algorithms (CRC-3, CRC-5,
# etc.) are intentionally excluded.
CROSS_CHECK = [
    # name, test message
    ("CRC-8/SMBUS",       b"123456789"),
    ("CRC-8/DARC",        b"\xde\xad\xbe\xef"),
    ("CRC-8/MAXIM-DOW",   b"\x01\x02\x03\x04\x05\x06\x07\x08"),
    ("CRC-16/ARC",        b"123456789"),
    ("CRC-16/KERMIT",     b"\xff\x00\xaa\x55"),
    ("CRC-16/MODBUS",     b"\x01\x03\x00\x00\x00\x08"),
    ("CRC-16/IBM-SDLC",   b"123456789"),
    ("CRC-16/IBM-3740",   b"123456789"),      # MIPI CSI-2/DSI
    ("CRC-32/ISO-HDLC",   b"123456789"),      # Ethernet FCS
    ("CRC-32/MPEG-2",     b"\xde\xad\xbe\xef"),
    ("CRC-32/BZIP2",      b"\x01\x02\x03\x04\x05\x06\x07\x08"),
    ("CRC-32/ISCSI",      b"123456789"),      # CRC-32C
    ("CRC-32/JAMCRC",     b"123456789"),
    ("CRC-32/POSIX",      b"123456789"),
    ("CRC-64/GO-ISO",     b"\x01\x02\x03\x04\x05\x06\x07\x08"),
    ("CRC-64/ECMA-182",   b"\xde\xad\xbe\xef\x00\x11\x22\x33"),
]


@pytest.mark.parametrize("name,message", CROSS_CHECK)
def test_matches_crcmod(name, message):
    """software_crc result must equal crcmod result for the same inputs."""
    alg = CATALOG[name]
    our_result = compute_crc(alg, message)
    crcmod_fn = _make_crcmod_fn(alg)
    crcmod_result = crcmod_fn(message)
    hex_w = (alg.width + 3) // 4
    assert our_result == crcmod_result, (
        f"{name}: our=0x{our_result:0{hex_w}X}, crcmod=0x{crcmod_result:0{hex_w}X}"
    )


@pytest.mark.parametrize("name,_", CROSS_CHECK)
def test_check_value_matches_crcmod(name, _):
    """Check value (CRC of b'123456789') must match crcmod."""
    alg = CATALOG[name]
    crcmod_fn = _make_crcmod_fn(alg)
    crcmod_check = crcmod_fn(b"123456789")
    hex_w = (alg.width + 3) // 4
    assert alg.check == crcmod_check, (
        f"{name}: catalog check=0x{alg.check:0{hex_w}X}, crcmod=0x{crcmod_check:0{hex_w}X}"
    )
