from hwp2hwpx.mapper.fonts import map_fonts
from hwp2hwpx.hwpmodel.model import HwpFont


def test_maps_fonts_preserving_order_and_index():
    src = [HwpFont(index=0, name="바탕"), HwpFont(index=1, name="굴림")]
    out = map_fonts(src)
    assert list(out.keys()) == ["HANGUL"]
    assert [f.id for f in out["HANGUL"]] == [0, 1]
    assert [f.face for f in out["HANGUL"]] == ["바탕", "굴림"]
