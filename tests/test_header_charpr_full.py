from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, Font, CharPr, ParaPr
from hwp2hwpx.constants import NS

_LANGS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def _charpr(**kw):
    base = dict(id=0, height=1000, text_color="#000000",
                font_ref={l: 1 for l in _LANGS},
                ratio={l: 100 for l in _LANGS},
                spacing={l: 0 for l in _LANGS},
                rel_sz={l: 100 for l in _LANGS},
                offset={l: 0 for l in _LANGS})
    base.update(kw)
    return CharPr(**base)


def _first_charpr(header):
    root = etree.fromstring(header_xml(header))
    return root, next(root.iter(_hh("charPr")))


def test_charpr_attributes():
    header = Header(char_prs=[_charpr(shade_color="none", border_fill_id=1)],
                    para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    assert ce.get("height") == "1000"
    assert ce.get("textColor") == "#000000"
    assert ce.get("shadeColor") == "none"
    assert ce.get("useFontSpace") == "0"
    assert ce.get("useKerning") == "0"
    assert ce.get("symMark") == "NONE"
    assert ce.get("borderFillIDRef") == "1"


def test_charpr_fontref_seven_languages():
    header = Header(char_prs=[_charpr(font_ref={l: i for i, l in enumerate(_LANGS)})],
                    para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    fr = ce.find(_hh("fontRef"))
    assert fr.get("hangul") == "0"
    assert fr.get("user") == "6"
    assert all(fr.get(l) is not None for l in _LANGS)


def test_charpr_child_order():
    header = Header(char_prs=[_charpr(bold=True, italic=True)], para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    tags = [etree.QName(c).localname for c in ce]
    assert tags == ["fontRef", "ratio", "spacing", "relSz", "offset",
                    "italic", "bold", "underline", "strikeout", "outline", "shadow"]


def test_charpr_effects_emitted():
    header = Header(char_prs=[_charpr(underline_type="BOTTOM", underline_shape="SOLID",
                                      underline_color="#000000", outline_type="NONE",
                                      shadow_type="DROP", shadow_color="#B2B2B2",
                                      shadow_offset_x=10, shadow_offset_y=10)],
                    para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    ul = ce.find(_hh("underline"))
    assert ul.get("type") == "BOTTOM" and ul.get("shape") == "SOLID" and ul.get("color") == "#000000"
    sh = ce.find(_hh("shadow"))
    assert sh.get("type") == "DROP" and sh.get("color") == "#B2B2B2"
    assert sh.get("offsetX") == "10" and sh.get("offsetY") == "10"


def test_charpr_no_bold_when_unset():
    header = Header(char_prs=[_charpr()], para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    tags = [etree.QName(c).localname for c in ce]
    assert "bold" not in tags and "italic" not in tags
