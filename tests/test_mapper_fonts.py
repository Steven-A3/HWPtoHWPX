from hwp2hwpx.mapper.fonts import map_fonts
from hwp2hwpx.hwpmodel.model import HwpFont


_ALL_LANGS = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]


def test_maps_fonts_preserving_order_and_index():
    src = [HwpFont(index=0, name="바탕"), HwpFont(index=1, name="굴림")]
    out = map_fonts(src)
    assert [f.id for f in out["HANGUL"]] == [0, 1]
    assert [f.face for f in out["HANGUL"]] == ["바탕", "굴림"]


def test_maps_fonts_to_all_seven_language_buckets():
    """charPr/fontRef sets all 7 language attrs (hangul/latin/hanja/
    japanese/other/symbol/user); every one of them must resolve to a
    real <hh:fontface lang=...> bucket, or 6 of the 7 refs dangle."""
    src = [HwpFont(index=0, name="바탕"), HwpFont(index=1, name="굴림")]
    out = map_fonts(src)
    assert set(out.keys()) == set(_ALL_LANGS)
    for lang in _ALL_LANGS:
        assert [f.id for f in out[lang]] == [0, 1]
        assert [f.face for f in out[lang]] == ["바탕", "굴림"]
