"""Validate GF(2) equation derivation against the software_crc oracle.

For each algorithm, we simulate the derived parallel equations word by word
and compare to the software CRC.  This cross-checks that the GF(2) iterative
unrolling produces results identical to the Williams model reference.

Byte-to-word mapping convention
--------------------------------
In reflected mode (ref_in=True), the LFSR feeds data_in[0] first (LSB of the
data word).  This matches the bit sequence the software CRC produces when it
reflects each byte then feeds MSB-first.  Therefore:

  word = int.from_bytes(word_bytes, 'little')   # LSB of first byte at bit 0

In normal mode (ref_in=False), data_in[D-1] is fed first (MSB of the word):

  word = int.from_bytes(word_bytes, 'big')       # MSB of first byte at bit D-1

The equations in reflected mode already output the post-reflection CRC so NO
additional ref_out is applied when simulating equations; only xor_out is applied
at the very end.
"""

import pytest
from crczero.catalog import CATALOG
from crczero.equations import derive_equations, simulate_equations
from crczero.software_crc import compute_crc


def _bit_reverse(value: int, width: int) -> int:
    result = 0
    for _ in range(width):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def _simulate_full_message(algorithm, data_width, message: bytes) -> int:
    """Feed 'message' through the derived equations word by word.

    For ref_in=True algorithms the DUT operates in LFSR-register space
    (bit_reverse of the Williams register), so the starting crc_in must be
    bit_reverse(Williams_init).  The equations output the next LFSR register
    value, which feeds naturally into the next word's crc_in.

    For mixed ref_in/ref_out modes the output space differs from the input
    space; an inter-word conversion is applied as needed.
    """
    assert data_width % 8 == 0
    bytes_per_word = data_width // 8
    assert len(message) % bytes_per_word == 0

    eqs = derive_equations(algorithm, data_width)
    N = algorithm.width
    mask = (1 << N) - 1

    # Hardware init: bit_reverse(Williams_init) for reflected algorithms.
    if algorithm.ref_in:
        crc = _bit_reverse(algorithm.init, N) & mask
    else:
        crc = algorithm.init & mask

    words = [message[i:i + bytes_per_word] for i in range(0, len(message), bytes_per_word)]
    for idx, word_bytes in enumerate(words):
        word = int.from_bytes(word_bytes, 'little' if algorithm.ref_in else 'big')
        crc = simulate_equations(eqs, crc, word)
        # Mixed modes: convert output space back to input space between words.
        if algorithm.ref_in != algorithm.ref_out and idx < len(words) - 1:
            crc = _bit_reverse(crc, N)

    return (crc ^ algorithm.xor_out) & mask


CROSS_CHECK_ALGORITHMS = [
    ("CRC-8/SMBUS",       8, b"\x01\x02\x03\x04\x05\x06\x07\x08"),
    ("CRC-8/DARC",        8, b"\xde\xad\xbe\xef\x00\x11\x22\x33"),
    ("CRC-16/ARC",        8, b"\x01\x02\x03\x04\x05\x06\x07\x08"),
    ("CRC-16/MODBUS",     8, b"\x01\x03\x00\x00\x00\x08"),
    ("CRC-16/KERMIT",     8, b"\xff\x00\xaa\x55\x12\x34\x56\x78"),
    ("CRC-32/ISO-HDLC",   8, b"\x01\x02\x03\x04\x05\x06\x07\x08"),
    ("CRC-32/MPEG-2",     8, b"\xde\xad\xbe\xef"),
    ("CRC-32/ISCSI",      8, b"\x01\x02\x03\x04\x05\x06\x07\x08"),
    ("CRC-64/GO-ISO",     8, b"\x01\x02\x03\x04\x05\x06\x07\x08"),
    ("CRC-64/ECMA-182",   8, b"\xde\xad\xbe\xef\x00\x11\x22\x33"),
]


@pytest.mark.parametrize("name,data_width,message", CROSS_CHECK_ALGORITHMS)
def test_equations_match_software_crc(name, data_width, message):
    alg = CATALOG[name]
    expected = compute_crc(alg, message)
    got = _simulate_full_message(alg, data_width, message)
    assert got == expected, (
        f"{name} D={data_width}: software=0x{expected:0{(alg.width+3)//4}X}, "
        f"equations=0x{got:0{(alg.width+3)//4}X}"
    )


@pytest.mark.parametrize("name,data_width,message", CROSS_CHECK_ALGORITHMS)
def test_check_value_via_equations(name, data_width, message):
    alg = CATALOG[name]
    got = _simulate_full_message(alg, 8, b"123456789")
    assert got == alg.check, (
        f"{name}: check=0x{alg.check:0{(alg.width+3)//4}X}, "
        f"equations=0x{got:0{(alg.width+3)//4}X}"
    )


def test_equation_structure_crc8():
    alg = CATALOG["CRC-8/SMBUS"]
    eqs = derive_equations(alg, 8)
    assert eqs.width == 8
    assert eqs.data_width == 8
    assert len(eqs.crc_terms) == 8
    assert len(eqs.data_terms) == 8
    for i in range(8):
        assert len(eqs.crc_terms[i]) + len(eqs.data_terms[i]) > 0


def test_equation_structure_crc32():
    alg = CATALOG["CRC-32/ISO-HDLC"]
    eqs = derive_equations(alg, 8)
    assert eqs.width == 32
    assert eqs.data_width == 8
    assert len(eqs.crc_terms) == 32
    assert len(eqs.data_terms) == 32


def test_wide_data_width():
    alg = CATALOG["CRC-32/ISO-HDLC"]
    message = b"\xde\xad\xbe\xef"
    expected = compute_crc(alg, message)
    got = _simulate_full_message(alg, 32, message)
    assert got == expected, f"D=32: software=0x{expected:08X}, equations=0x{got:08X}"


# ---------------------------------------------------------------------------
# Full catalog coverage: every width-%8==0 algorithm vs its check value
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    n for n in sorted(CATALOG.keys())
    if CATALOG[n].width % 8 == 0
])
def test_check_value_all_catalog(name):
    """Equations must reproduce the catalog check value for every algorithm."""
    alg = CATALOG[name]
    got = _simulate_full_message(alg, 8, b"123456789")
    hex_w = (alg.width + 3) // 4
    assert got == alg.check, (
        f"{name}: catalog check=0x{alg.check:0{hex_w}X}, "
        f"equations=0x{got:0{hex_w}X}"
    )


# ---------------------------------------------------------------------------
# Per-word random inputs: equations vs software_crc for single-word messages
# ---------------------------------------------------------------------------

SINGLE_WORD_CASES = [
    ("CRC-8/SMBUS",      8),
    ("CRC-8/DARC",       8),
    ("CRC-16/ARC",       8),
    ("CRC-16/IBM-3740",  8),
    ("CRC-32/ISO-HDLC",  8),
    ("CRC-32/ISO-HDLC", 32),
    ("CRC-32/MPEG-2",    8),
    ("CRC-32/MPEG-2",   32),
    ("CRC-64/GO-ISO",    8),
]


@pytest.mark.parametrize("name,data_width", SINGLE_WORD_CASES)
def test_single_word_equations_vs_software(name, data_width):
    """32 deterministic single-word inputs must match between equations and software_crc."""
    alg = CATALOG[name]
    bytes_per_word = data_width // 8
    eqs = derive_equations(alg, data_width)
    N = alg.width
    mask = (1 << N) - 1

    for seed in range(32):
        # Deterministic pseudo-random word derived from seed
        raw = (seed * 0x9E3779B9 + 0xDEADBEEF) & ((1 << data_width) - 1)
        word_bytes = raw.to_bytes(bytes_per_word, 'little' if alg.ref_in else 'big')

        # Software oracle
        sw = compute_crc(alg, word_bytes)

        # Equations: single-word simulation from init
        crc = alg.init & mask
        crc = simulate_equations(eqs, crc, raw)
        eq = (crc ^ alg.xor_out) & mask

        hex_w = (N + 3) // 4
        assert eq == sw, (
            f"{name} D={data_width} seed={seed} word=0x{raw:0{data_width//4}X}: "
            f"software=0x{sw:0{hex_w}X}, equations=0x{eq:0{hex_w}X}"
        )


# ---------------------------------------------------------------------------
# Mixed ref_in / ref_out modes (uncommon but valid)
# ---------------------------------------------------------------------------

def test_mixed_ref_in_true_ref_out_false():
    """ref_in=True, ref_out=False: equations must match software_crc."""
    from crczero.algorithm import Algorithm
    alg = Algorithm(
        name="MIXED-T-F",
        width=16,
        poly=0x8005,
        init=0x0000,
        ref_in=True,
        ref_out=False,
        xor_out=0x0000,
        check=0,
        residue=0,
    )
    message = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    expected = compute_crc(alg, message)
    got = _simulate_full_message(alg, 8, message)
    assert got == expected, (
        f"MIXED ref_in=T ref_out=F: software=0x{expected:04X}, equations=0x{got:04X}"
    )


def test_mixed_ref_in_false_ref_out_true():
    """ref_in=False, ref_out=True: equations must match software_crc."""
    from crczero.algorithm import Algorithm
    alg = Algorithm(
        name="MIXED-F-T",
        width=16,
        poly=0x1021,
        init=0xFFFF,
        ref_in=False,
        ref_out=True,
        xor_out=0x0000,
        check=0,
        residue=0,
    )
    message = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    expected = compute_crc(alg, message)
    got = _simulate_full_message(alg, 8, message)
    assert got == expected, (
        f"MIXED ref_in=F ref_out=T: software=0x{expected:04X}, equations=0x{got:04X}"
    )
