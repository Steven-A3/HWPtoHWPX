from hwp2hwpx.hwpmodel.model import HwpParaShape
from hwp2hwpx.owpml.model import ParaPr


def test_hwp_para_shape_new_fields():
    s = HwpParaShape(index=1, align="CENTER", indent=-4000, margin_left=2000,
                     margin_right=2000, margin_top=0, margin_bottom=0,
                     line_spacing=140, line_spacing_type="ratio",
                     border_fill_id=2, level=0)
    assert s.indent == -4000 and s.margin_left == 2000
    assert s.line_spacing == 140 and s.border_fill_id == 2


def test_para_pr_new_fields_have_defaults():
    p = ParaPr(id=0)
    assert p.intent == 0 and p.margin_prev == 0
    assert p.line_spacing == 100 and p.line_spacing_type == "PERCENT"
    assert p.border_fill_id == 1 and p.tab_pr_id == 0
    # existing 2-arg construction still works
    assert ParaPr(id=3, align="RIGHT").align == "RIGHT"
