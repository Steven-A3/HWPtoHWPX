from hwp2hwpx.mapper.border_fill import map_border_fills
from hwp2hwpx.hwpmodel.model import HwpBorderFill, HwpBorder


def test_maps_stroke_width_color_and_fill():
    src = [HwpBorderFill(index=2, borders=[
        HwpBorder(kind="left", stroke_type="solid", width="0.4mm", color="#000000"),
        HwpBorder(kind="top", stroke_type="none", width="0.1mm", color="#123456"),
    ], fill_color="#bbbbbb")]
    out = map_border_fills(src)
    assert out[0].id == 2
    left = out[0].borders[0]
    assert left.kind == "left"
    assert left.type == "SOLID"
    assert left.width == "0.4 mm"
    assert left.color == "#000000"
    assert out[0].borders[1].type == "NONE"
    assert out[0].fill_color == "#bbbbbb"


def test_width_already_spaced_is_untouched():
    src = [HwpBorderFill(index=0, borders=[
        HwpBorder(kind="left", stroke_type="solid", width="0.5 mm", color="#000000")])]
    assert map_border_fills(src)[0].borders[0].width == "0.5 mm"
