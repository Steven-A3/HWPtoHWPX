from hwp2hwpx.mapper.para_pr import map_para_shapes
from hwp2hwpx.hwpmodel.model import HwpParaShape


def test_margins_halved_sign_preserved():
    out = map_para_shapes([HwpParaShape(index=0, indent=-4000, margin_left=2000,
                                        margin_right=2000, margin_top=0, margin_bottom=0)])
    p = out[0]
    assert p.intent == -2000
    assert p.margin_left == 1000 and p.margin_right == 1000
    assert p.margin_prev == 0 and p.margin_next == 0


def test_linespacing_ratio_to_percent_and_border_raw():
    out = map_para_shapes([HwpParaShape(index=2, line_spacing=140,
                                        line_spacing_type="ratio", border_fill_id=13)])
    p = out[0]
    assert p.id == 2
    assert p.line_spacing == 140 and p.line_spacing_type == "PERCENT"
    assert p.border_fill_id == 13          # raw, 1-based, no shift
    assert p.tab_pr_id == 0                # clamped
    assert p.heading_type == "NONE"


def test_odd_negative_halves_toward_zero():
    out = map_para_shapes([HwpParaShape(index=0, indent=-4001)])
    assert out[0].intent == -2000          # toward zero, not -2001
