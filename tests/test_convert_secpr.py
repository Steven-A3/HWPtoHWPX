import zipfile
import pytest
from lxml import etree
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

PAIRS = [
    ("samples/3.과업지시서_070.hwp", "samples/3.과업지시서_070.hwpx"),
    ("samples/4.제안요청서_070.hwp", "samples/4.제안요청서_070.hwpx"),
]


def _canon(el):
    """Structural signature: local tag, attribute dict, stripped text, ordered
    children — recursively. Namespace prefixes are stripped so only structure
    and values are compared."""
    tag = etree.QName(el).localname
    return (tag, dict(el.attrib), (el.text or "").strip(),
            [_canon(c) for c in el])


def _secpr_from_bytes(xml_bytes):
    root = etree.fromstring(xml_bytes)
    return root.find(".//{%s}secPr" % HP)


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_secpr_subtree_structurally_identical_to_hancom(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    with zipfile.ZipFile(str(out)) as z:
        ours = _secpr_from_bytes(z.read("Contents/section0.xml"))
    with zipfile.ZipFile(ref) as z:
        theirs = _secpr_from_bytes(z.read("Contents/section0.xml"))
    assert ours is not None and theirs is not None
    assert _canon(ours) == _canon(theirs)


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_secpr_cluster_tags_leave_miss_list(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(ref)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    for tag in ("secPr", "grid", "startNum", "visibility", "lineNumberShape",
                "pagePr", "margin", "footNotePr", "endNotePr", "colPr",
                "pageNum", "pageBorderFill"):
        assert tag not in missing, "%s still missing on %s" % (tag, hwp)


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_section0_match_improved(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(ref)["Contents/section0.xml"]
    assert score_part(ours, theirs)["match"] > 0.97
