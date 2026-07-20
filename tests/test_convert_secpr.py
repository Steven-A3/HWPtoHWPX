import zipfile
import pytest
from lxml import etree
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.samplepaths import S3, S3_REF, S4, S4_REF

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

PAIRS = [
    (S3, S3_REF),
    (S4, S4_REF),
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


# section0 match floors this milestone actually achieves (verified against a
# clean-main baseline: s3 0.9885->0.9931, s4 0.9640->0.9677). Sample 4's ceiling
# is bounded by unimplemented drawing objects (pic/img/line/matrices — a separate
# milestone), not by secPr, so its floor sits below sample 3's.
_SECTION0_FLOOR = {
    S3: 0.99,
    S4: 0.966,
}


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_section0_match_improved(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(ref)["Contents/section0.xml"]
    assert score_part(ours, theirs)["match"] > _SECTION0_FLOOR[hwp]
