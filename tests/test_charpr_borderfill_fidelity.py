import os
import tempfile

from lxml import etree

import pytest

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.samplepaths import hwp as _hwp, hwpx as _hwpx

_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _charpr_refs(header_xml):
    root = etree.fromstring(header_xml)
    return [cp.get("borderFillIDRef") for cp in root.iter("{%s}charPr" % _HH)]


# samples 3/4/★131008 get no null-insert (raw offset-68 id == Hancom charPr ref);
# 2013 IS a null-insert doc, so its charPr refs are offset-68 + 1 (supplied by
# normalize_borderfill_null) — included here to lock that cross-cutting path.
@pytest.mark.parametrize("pre", ["3.", "4.", "★131008", "20131106"])
def test_charpr_border_fill_refs_match_hancom(pre):
    hwp = _hwp(pre)
    ref = _hwpx(pre)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.hwpx")
        convert(hwp, out)
        ours = unzip_parts(out)
    theirs = unzip_parts(ref)
    assert _charpr_refs(ours["Contents/header.xml"]) == \
        _charpr_refs(theirs["Contents/header.xml"])
