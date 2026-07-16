import zipfile
from hwp2hwpx.convert import convert

SAMPLE_HWP = "samples/3.과업지시서_070.hwp"


def _section(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def test_linesegarray_and_lineseg_counts_match_hancom(tmp_path):
    sec = _section(tmp_path)
    assert sec.count("<hp:linesegarray") == 749
    # trailing space so "<hp:lineseg " does not also match "<hp:linesegarray"
    assert sec.count("<hp:lineseg ") == 922


def test_linesegarray_is_child_of_p(tmp_path):
    from lxml import etree
    from hwp2hwpx.constants import NS
    sec = _section(tmp_path).encode("utf-8")
    root = etree.fromstring(sec)
    hp = "{%s}" % NS["hp"]
    # every linesegarray's parent is an hp:p
    for lsa in root.iter(hp + "linesegarray"):
        assert etree.QName(lsa.getparent()).localname == "p"
