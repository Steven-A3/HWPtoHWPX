from hwp2hwpx.mapper.char_pr import map_char_shapes
from hwp2hwpx.hwpmodel.model import HwpCharShape


def test_map_char_shape_fields():
    src = [HwpCharShape(index=0, base_size=1400, text_color="#FF0000", font_id=3,
                        bold=True, italic=False)]
    out = map_char_shapes(src)
    assert out[0].id == 0
    assert out[0].height == 1400
    assert out[0].text_color == "#FF0000"
    assert out[0].font_ref_id == 3
    assert out[0].bold is True
    assert out[0].italic is False


def test_map_preserves_order_and_count():
    src = [HwpCharShape(index=0, base_size=1000, text_color="#000000"),
           HwpCharShape(index=1, base_size=1200, text_color="#112233")]
    out = map_char_shapes(src)
    assert [c.id for c in out] == [0, 1]
    assert [c.text_color for c in out] == ["#000000", "#112233"]
