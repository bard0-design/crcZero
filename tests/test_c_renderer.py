# crcZero -- CRC HDL Generator
# https://github.com/bard0-design/crcZero
#
# Author     : Leonardo Capossio - bard0 design <hello@bard0.com>
# License    : MIT
"""Tests for the C reference renderer."""

from crczero.catalog import CATALOG
from crczero.renderers.c import CRenderer


def test_c_renderer_outputs_header_and_source():
    alg = CATALOG["CRC-32/ISO-HDLC"]
    header, source = CRenderer().render(alg)
    assert "#ifndef CRC_32_ISO_HDLC_H_" in header
    assert "uint64_t crc_32_iso_hdlc(" in header
    assert '#include "crc_32_iso_hdlc.h"' in source
    assert "crc_32_iso_hdlc_self_test" in source
