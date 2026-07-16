from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, Font, CharPr, ParaPr, TypeInfo
from hwp2hwpx.constants import NS


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def test_font_emits_typeinfo_child():
    header = Header(
        fonts_by_lang={"HANGUL": [Font(id=0, face="굴림",
            type_info=TypeInfo(family_type="FCAT_GOTHIC", weight=6, proportion=9,
                               contrast=0, stroke_variation=1, arm_style=1,
                               letterform=1, midline=1, x_height=1))]},
        char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)],
    )
    root = etree.fromstring(header_xml(header))
    font = next(root.iter(_hh("font")))
    assert font.get("face") == "굴림"          # existing attrs intact
    ti = font.find(_hh("typeInfo"))
    assert ti is not None
    assert ti.get("familyType") == "FCAT_GOTHIC"
    assert ti.get("weight") == "6"
    assert ti.get("proportion") == "9"
    assert ti.get("strokeVariation") == "1"
    assert ti.get("armStyle") == "1"
    assert ti.get("xHeight") == "1"


def test_font_without_typeinfo_emits_none():
    header = Header(fonts_by_lang={"HANGUL": [Font(id=0, face="굴림")]},
                    char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)])
    root = etree.fromstring(header_xml(header))
    font = next(root.iter(_hh("font")))
    assert font.find(_hh("typeInfo")) is None
