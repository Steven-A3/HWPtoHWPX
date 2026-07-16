from hwp2hwpx.mapper.style import map_styles
from hwp2hwpx.mapper.body import map_paragraph
from hwp2hwpx.hwpmodel.model import HwpStyle, HwpParagraph, HwpRun


def test_map_style_transform():
    src = [HwpStyle(index=0, kind="paragraph", local_name="바탕글", eng_name="Normal",
                    para_shape_id=3, char_shape_id=17, next_style_id=0, lang_id=1042)]
    out = map_styles(src)
    s = out[0]
    assert s.id == 0
    assert s.type == "PARA"
    assert s.name == "바탕글"
    assert s.eng_name == "Normal"
    assert s.para_pr_id == 3
    assert s.char_pr_id == 17
    assert s.next_style_id == 0
    assert s.lang_id == 1042
    assert s.lock_form == "0"


def test_map_style_char_kind():
    out = map_styles([HwpStyle(index=1, kind="char")])
    assert out[0].type == "CHAR"


def test_map_preserves_order_and_count():
    src = [HwpStyle(index=0, local_name="A"), HwpStyle(index=1, local_name="B")]
    out = map_styles(src)
    assert [s.id for s in out] == [0, 1]
    assert [s.name for s in out] == ["A", "B"]


def test_map_paragraph_uses_real_style_id():
    hpar = HwpParagraph(para_shape_id=2, style_id=5,
                        runs=[HwpRun(char_shape_id=0, contents=["x"])])
    para = map_paragraph(hpar, 0)
    assert para.style_id == 5
