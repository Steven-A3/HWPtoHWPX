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


def test_header_emits_default_style_table():
    """paragraphs emit styleIDRef="0"; header.xml must carry a matching
    <hh:styles> table with a style id 0, or the reference dangles."""
    header = Header(
        fonts_by_lang={"HANGUL": [Font(id=0, face="바탕")]},
        char_prs=[CharPr(id=0, height=1000, text_color="#000000")],
        para_prs=[ParaPr(id=0, align="CENTER")],
    )
    root = etree.fromstring(header_xml(header))
    styles = list(root.iter(_hh("style")))
    assert len(styles) == 1
    assert styles[0].get("id") == "0"


def test_header_emits_fontface_per_language_bucket():
    """header_writer emits one <hh:fontface lang=...> per key of
    fonts_by_lang; map_fonts now populates all 7 OWPML language buckets,
    so header_xml must round-trip all 7 as separate fontface elements."""
    langs = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]
    header = Header(
        fonts_by_lang={lang: [Font(id=0, face="바탕")] for lang in langs},
        char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)],
    )
    root = etree.fromstring(header_xml(header))
    fontfaces = list(root.iter(_hh("fontface")))
    assert len(fontfaces) == 7
    assert {ff.get("lang") for ff in fontfaces} == set(langs)


def test_header_sec_cnt_defaults_to_one():
    header = Header()
    root = etree.fromstring(header_xml(header))
    assert root.get("secCnt") == "1"


def test_header_sec_cnt_reflects_argument():
    header = Header()
    root = etree.fromstring(header_xml(header, sec_cnt=2))
    assert root.get("secCnt") == "2"
