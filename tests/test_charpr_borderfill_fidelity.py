import glob
import os
import tempfile

from lxml import etree

import pytest

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _charpr_refs(header_xml):
    root = etree.fromstring(header_xml)
    return [cp.get("borderFillIDRef") for cp in root.iter("{%s}charPr" % _HH)]


@pytest.mark.parametrize("pre", ["samples/3.", "samples/4.", "samples/★131008"])
def test_charpr_border_fill_refs_match_hancom(pre):
    hwp = glob.glob(pre + "*.hwp")[0]
    ref = glob.glob(pre + "*.hwpx")[0]
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.hwpx")
        convert(hwp, out)
        ours = unzip_parts(out)
    theirs = unzip_parts(ref)
    assert _charpr_refs(ours["Contents/header.xml"]) == \
        _charpr_refs(theirs["Contents/header.xml"])
