from hwp2hwpx.hwpmodel.model import HwpStyle, HwpDocInfo
from hwp2hwpx.owpml.model import Style, Header


def test_hwp_style_defaults():
    s = HwpStyle(index=0)
    assert s.kind == "paragraph"
    assert s.local_name == ""
    assert s.eng_name == ""
    assert s.para_shape_id == 0
    assert s.char_shape_id == 0
    assert s.next_style_id == 0
    assert s.lang_id == 1042


def test_docinfo_has_styles_list():
    assert HwpDocInfo().styles == []


def test_owpml_style_defaults():
    s = Style(id=0)
    assert s.type == "PARA"
    assert s.name == ""
    assert s.eng_name == ""
    assert s.para_pr_id == 0
    assert s.char_pr_id == 0
    assert s.next_style_id == 0
    assert s.lang_id == 1042
    assert s.lock_form == "0"


def test_header_has_styles_list():
    assert Header().styles == []
