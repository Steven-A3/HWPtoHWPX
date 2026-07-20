from tests.samplepaths import hwp as _hwp, hwpx as _hwpx

from lxml import etree

from hwp2hwpx.hwpmodel.reader import (
    _cs_border_fill, hwp5_char_shape_border_fills,
    read_docinfo, hwp5_xml,
)
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def test_cs_border_fill_reads_offset_68():
    payload = bytes(68) + bytes([5, 0]) + bytes(4)   # len 74, u16le at 68 == 5
    assert _cs_border_fill(payload) == 5


def test_cs_border_fill_short_payload_falls_back_to_one():
    assert _cs_border_fill(bytes(40)) == 1


def _hancom_charpr_refs(pre):
    ref = _hwpx(pre)
    root = etree.fromstring(unzip_parts(ref)["Contents/header.xml"])
    return [int(cp.get("borderFillIDRef"))
            for cp in root.iter("{%s}charPr" % "http://www.hancom.co.kr/hwpml/2011/head")]


def test_border_fills_match_hancom_on_no_insert_doc():
    # sample 3 gets no null-insert, so the raw offset-68 ids equal Hancom's
    # charPr borderFillIDRef directly.
    hwp = _hwp("3.")
    got = hwp5_char_shape_border_fills(hwp)
    assert got == _hancom_charpr_refs("3.")


def test_read_docinfo_assigns_when_lengths_match():
    hwp = _hwp("3.")
    xml = hwp5_xml(hwp)
    bfs = hwp5_char_shape_border_fills(hwp)
    di = read_docinfo(xml, char_border_fills=bfs)
    assert [cs.border_fill_id for cs in di.char_shapes] == bfs


def test_read_docinfo_ignores_on_length_mismatch():
    hwp = _hwp("3.")
    xml = hwp5_xml(hwp)
    di = read_docinfo(xml, char_border_fills=[7, 7, 7])  # wrong length
    assert all(cs.border_fill_id == 1 for cs in di.char_shapes)
