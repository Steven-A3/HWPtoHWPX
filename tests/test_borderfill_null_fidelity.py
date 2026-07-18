import glob
import re
import tempfile
import os

import pytest
from lxml import etree

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _convert(pre):
    hwp = glob.glob(pre + "*.hwp")[0]
    ref = glob.glob(pre + "*.hwpx")[0]
    td = tempfile.mkdtemp()
    out = os.path.join(td, "out.hwpx")
    convert(hwp, out)
    return unzip_parts(out), unzip_parts(ref)


def _local(t):
    return t.rsplit("}", 1)[-1]


def _count(xml, tag):
    root = etree.fromstring(xml)
    return sum(1 for e in root.iter() if _local(e.tag) == tag)


def _section0_refs(parts):
    return re.findall(rb'borderFillIDRef="(\d+)"', parts["Contents/section0.xml"])


NO_INSERT = ["samples/3.", "samples/4.", "samples/★131008"]


@pytest.mark.parametrize("pre", NO_INSERT)
def test_no_insert_docs_match_hancom_section0_refs(pre):
    ours, theirs = _convert(pre)
    # borderFill count equal, section0 refs byte-identical to Hancom (proves the
    # pass never misfires on a doc whose first fill is already the canonical null)
    assert _count(ours["Contents/header.xml"], "borderFill") == \
        _count(theirs["Contents/header.xml"], "borderFill")
    assert _section0_refs(ours) == _section0_refs(theirs)


def test_2013_inserts_null_and_section0_refs_match_hancom():
    ours, theirs = _convert("samples/20131106")
    o_bf = _count(ours["Contents/header.xml"], "borderFill")
    t_bf = _count(theirs["Contents/header.xml"], "borderFill")
    assert o_bf == t_bf == 68           # 67 source + 1 prepended null
    # id=1 is the canonical null: all side borders NONE, no fillBrush
    root = etree.fromstring(ours["Contents/header.xml"])
    bf1 = [e for e in root.iter() if _local(e.tag) == "borderFill"][0]
    kinds = [_local(c.tag) for c in bf1]
    assert "fillBrush" not in kinds
    for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
        el = next(c for c in bf1 if _local(c.tag) == side)
        assert el.get("type") == "NONE"
    # every section0 borderFillIDRef matches Hancom exactly
    assert _section0_refs(ours) == _section0_refs(theirs)
    assert len(_section0_refs(ours)) == 379
