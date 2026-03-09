# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""GF(2) parallel CRC equation derivation.

Uses iterative symbolic unrolling to derive, for each CRC output bit,
the exact set of crc_in and data_in bits that must be XORed together.

The result is a CrcEquations object that renderers consume to produce HDL.

Algorithm overview
------------------
We maintain a state vector of N bitmasks (one per CRC register bit).
Each bitmask has (N + D) positions:
  - Bits 0..N-1:   which crc_in  bits contribute to this state bit
  - Bits N..N+D-1: which data_in bits contribute to this state bit

We initialize the state so that state[i] = (1 << i), meaning crc_out[i]
starts as exactly crc_in[i].

Then we feed D symbolic data bits through the LFSR update rule one at a time.
Feeding symbolic bit d (index N+d in the combined bitmask) applies the LFSR
transition in GF(2):  all operations are XOR (addition mod 2).

After D iterations the state encodes the complete parallel combinatorial
equations for the D-bit-wide CRC computation.

Reflection handling
-------------------
For ref_in=True algorithms the DUT operates in LFSR-register space, which is
the bit-reversal of the Williams register.  The caller must supply:

  crc_in (first word) = bit_reverse(Williams_init, N)

and chain crc_out → crc_in for subsequent words.  The final CRC is then:

  crc_out ^ xor_out

This convention means bit_reverse(init) is the hardware reset value.  For
most common algorithms (CRC-32/ISO-HDLC, CRC-16/ARC, etc.) init is either 0
or all-ones, both of which are self-symmetric under bit-reversal, so no
conversion is necessary.  For algorithms with asymmetric init (e.g.
CRC-24/BLE with init=0x555555), the hardware init differs from the catalog
init.  The generated header comment advertises the correct hardware init.

- ref_in == ref_out == True:
    Use reflected polynomial. LFSR shifts right. Data bit 0 is fed first.
    Feedback = state[0] XOR d_bit.
    new_state[i] = state[i+1] XOR (feedback if poly_ref bit i+1 else 0)
    new_state[N-1] = feedback

- ref_in == ref_out == False:
    Normal mode. LFSR shifts left. Data bit D-1 (MSB) is fed first.
    Feedback = state[N-1] XOR d_bit.
    new_state[0] = feedback AND poly[1]
    new_state[i] = state[i-1] XOR (feedback if poly bit i else 0)

- Mixed (ref_in != ref_out):
    Handled by post-processing: after deriving equations in the dominant
    mode, apply a bit-reversal permutation to the output bit ordering.
    Rare in practice; all common algorithms use matching ref_in/ref_out pairs.
"""

from __future__ import annotations

from dataclasses import dataclass

from crczero.algorithm import Algorithm


@dataclass
class CrcEquations:
    """Parallel CRC equations for one data word of data_width bits.

    For each output bit i (0 = LSB):
      crc_out[i] = XOR of { crc_in[j]  for j in crc_terms[i] }
                   XOR of { data_in[k] for k in data_terms[i] }

    If both term sets are empty, crc_out[i] = 0.
    """

    width: int                        # CRC width (N)
    data_width: int                   # Parallel data width (D)
    crc_terms: list[frozenset[int]]   # crc_terms[i]: set of crc_in bit indices
    data_terms: list[frozenset[int]]  # data_terms[i]: set of data_in bit indices


def _bit_reverse(value: int, width: int) -> int:
    """Reverse the bits of 'value' within 'width' bits."""
    result = 0
    for _ in range(width):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def derive_equations(algorithm: Algorithm, data_width: int) -> CrcEquations:
    """Derive parallel CRC combinatorial equations for the given algorithm.

    Returns a CrcEquations object encoding, for each output bit,
    which crc_in and data_in bits are XORed together.
    """
    N = algorithm.width
    D = data_width
    poly = algorithm.poly
    ref_in = algorithm.ref_in
    ref_out = algorithm.ref_out

    # State: list of N bitmasks over (N + D) symbolic bits.
    # Initial value: state[i] = (1 << i)  → crc_out[i] = crc_in[i]
    state = [1 << i for i in range(N)]

    if ref_in and ref_out:
        # Reflected mode: use reflected polynomial, shift right, LSB first.
        # r'[i] = r[i+1] ^ (poly_ref[i] * feedback)  for i = 0..N-2
        # r'[N-1] = feedback  (poly_ref[N-1] is always 1 for valid CRC polynomials)
        poly_ref = _bit_reverse(poly, N)
        for d in range(D):
            data_sym = 1 << (N + d)   # symbolic data bit d
            feedback = state[0] ^ data_sym
            new_state = [0] * N
            for i in range(N - 1):
                new_state[i] = state[i + 1]
                if (poly_ref >> i) & 1:       # check bit i, not bit i+1
                    new_state[i] ^= feedback
            new_state[N - 1] = feedback
            state = new_state

    elif not ref_in and not ref_out:
        # Normal mode: standard polynomial, shift left, MSB first.
        # Data bits enter MSB first: data bit D-1 is fed in clock 0.
        for d in range(D):
            data_sym = 1 << (N + (D - 1 - d))  # feed MSB first
            feedback = state[N - 1] ^ data_sym
            new_state = [0] * N
            new_state[0] = feedback if poly & 1 else 0
            for i in range(1, N):
                new_state[i] = state[i - 1]
                if (poly >> i) & 1:
                    new_state[i] ^= feedback
            state = new_state

    elif ref_in and not ref_out:
        # Input reflected, output not reflected.
        # Derive in reflected mode (LSB first), then map to Williams space.
        poly_ref = _bit_reverse(poly, N)
        for d in range(D):
            data_sym = 1 << (N + d)
            feedback = state[0] ^ data_sym
            new_state = [0] * N
            for i in range(N - 1):
                new_state[i] = state[i + 1]
                if (poly_ref >> i) & 1:
                    new_state[i] ^= feedback
            new_state[N - 1] = feedback
            state = new_state
        # Reverse output bit ordering to undo ref_out
        state = list(reversed(state))

    else:
        # ref_in=False, ref_out=True (very rare).
        # Derive in normal mode, then reverse output bit ordering.
        for d in range(D):
            data_sym = 1 << (N + (D - 1 - d))
            feedback = state[N - 1] ^ data_sym
            new_state = [0] * N
            new_state[0] = feedback if poly & 1 else 0
            for i in range(1, N):
                new_state[i] = state[i - 1]
                if (poly >> i) & 1:
                    new_state[i] ^= feedback
            state = new_state
        state = list(reversed(state))

    # Decode the bitmasks into separate crc_terms / data_terms sets.
    crc_terms: list[frozenset[int]] = []
    data_terms: list[frozenset[int]] = []

    for mask in state:
        crc_bits: set[int] = set()
        data_bits: set[int] = set()
        for bit in range(N):
            if (mask >> bit) & 1:
                crc_bits.add(bit)
        for bit in range(D):
            if (mask >> (N + bit)) & 1:
                data_bits.add(bit)
        crc_terms.append(frozenset(crc_bits))
        data_terms.append(frozenset(data_bits))

    return CrcEquations(
        width=N,
        data_width=D,
        crc_terms=crc_terms,
        data_terms=data_terms,
    )


def simulate_equations(equations: CrcEquations, crc_in: int, data_in: int) -> int:
    """Simulate the derived equations on concrete input values.

    Used for cross-validation against software_crc.compute_crc().

    Args:
        equations: derived CRC equations
        crc_in:    integer value of the CRC register input
        data_in:   integer value of the data input word

    Returns:
        integer value of crc_out
    """
    result = 0
    for i in range(equations.width):
        bit = 0
        for j in equations.crc_terms[i]:
            bit ^= (crc_in >> j) & 1
        for k in equations.data_terms[i]:
            bit ^= (data_in >> k) & 1
        result |= (bit << i)
    return result
