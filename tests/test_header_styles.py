from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, Font, CharPr, ParaPr, Style
from hwp2hwpx.constants import NS


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def test_header_emits_real_styles():
    header = Header(
        char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)],
        styles=[
            Style(id=0, type="PARA", name="바탕글", eng_name="Normal",
                  para_pr_id=3, char_pr_id=17, next_style_id=0, lang_id=1042),
            Style(id=1, type="PARA", name="본문", eng_name="",
                  para_pr_id=31, char_pr_id=38, next_style_id=1),
        ],
    )
    root = etree.fromstring(header_xml(header))
    styles_el = next(root.iter(_hh("styles")))
    assert styles_el.get("itemCnt") == "2"
    st = list(root.iter(_hh("style")))
    assert st[0].get("name") == "바탕글"
    assert st[0].get("engName") == "Normal"
    assert st[0].get("type") == "PARA"
    assert st[0].get("paraPrIDRef") == "3"
    assert st[0].get("charPrIDRef") == "17"
    assert st[0].get("nextStyleIDRef") == "0"
    assert st[0].get("langID") == "1042"
    assert st[0].get("lockForm") == "0"
    assert st[1].get("name") == "본문"


def test_header_empty_styles_falls_back_to_default():
    header = Header(char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)])
    root = etree.fromstring(header_xml(header))
    st = list(root.iter(_hh("style")))
    assert len(st) == 1
    assert st[0].get("id") == "0"
