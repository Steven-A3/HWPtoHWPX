from hwp2hwpx.hwpmodel.reader import read_docinfo

from tests.samplepaths import fixture3

FIXTURE = fixture3()


def _docinfo():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read())


def test_char_shape_font_ref_is_global_index():
    di = _docinfo()
    cs = di.char_shapes[0]
    # CharShape[0] FontFace ko=12 (hangul group offset 0) -> global 12
    assert cs.font_ref["ko"] == 12
    # en=10, latin group offset = ko-fonts(14) -> global 24
    assert cs.font_ref["en"] == 24
    # every ref resolves within the flat font list
    assert all(0 <= v < len(di.fonts) for v in cs.font_ref.values())


def test_char_shape_per_language_metrics():
    di = _docinfo()
    cs = di.char_shapes[0]
    assert cs.ratio["ko"] == 100
    assert cs.spacing["ko"] == 0
    assert cs.rel_sz["ko"] == 100
    assert cs.offset["ko"] == 0
    assert set(cs.ratio.keys()) == {"ko", "en", "cn", "jp", "other", "symbol", "user"}


def test_char_shape_effects_and_shade():
    di = _docinfo()
    cs = di.char_shapes[0]
    assert cs.shade_color == "#ffffff"
    assert cs.underline_type == "NONE"
    assert cs.shadow_type == "NONE"
    assert cs.shadow_offset_x == 10
    assert cs.shadow_offset_y == 10
    # some CharShape in the doc has underline="underline"
    assert any(c.underline_type == "BOTTOM" for c in di.char_shapes)
