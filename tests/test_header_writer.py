from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, Font, CharPr, ParaPr
from hwp2hwpx.constants import NS


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def test_header_has_fonts_charprs_paraprs():
    header = Header(
        fonts_by_lang={"HANGUL": [Font(id=0, face="바탕"), Font(id=1, face="굴림")]},
        char_prs=[CharPr(id=0, height=1000, text_color="#000000")],
        para_prs=[ParaPr(id=0, align="CENTER")],
    )
    root = etree.fromstring(header_xml(header))
    assert root.tag == _hh("head")
    faces = [f.get("face") for f in root.iter(_hh("font"))]
    assert faces == ["바탕", "굴림"]
    charprs = list(root.iter(_hh("charPr")))
    assert charprs[0].get("height") == "1000"
    aligns = [a.get("horizontal") for a in root.iter(_hh("align"))]
    assert aligns == ["CENTER"]
