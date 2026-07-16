# tests/test_model_charpr_fields.py
from hwp2hwpx.hwpmodel.model import HwpCharShape
from hwp2hwpx.owpml.model import CharPr


def test_hwp_char_shape_new_fields_default():
    cs = HwpCharShape(index=0, base_size=1000)
    assert cs.font_ref == {}
    assert cs.ratio == {}
    assert cs.shade_color == "#ffffff"
    assert cs.underline_type == "NONE"
    assert cs.underline_shape == "SOLID"
    assert cs.strikeout_shape == "NONE"
    assert cs.outline_type == "NONE"
    assert cs.shadow_type == "NONE"
    assert cs.shadow_offset_x == 10
    assert cs.shadow_offset_y == 10


def test_owpml_charpr_new_fields_default():
    cp = CharPr(id=0)
    assert cp.font_ref == {}
    assert cp.ratio == {}
    assert cp.border_fill_id == 1
    assert cp.shade_color == "none"
    assert cp.underline_type == "NONE"
    assert cp.shadow_type == "NONE"
    assert cp.shadow_offset_x == 10
    # existing fields still present
    assert cp.height == 1000
    assert cp.font_ref_id == 0
