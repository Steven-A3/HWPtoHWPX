from hwp2hwpx.mapper.char_pr import map_char_shapes
from hwp2hwpx.hwpmodel.model import HwpCharShape


def _src(**kw):
    base = dict(index=0, base_size=1000,
                font_ref={"ko": 12, "en": 24, "cn": 3, "jp": 3,
                          "other": 3, "symbol": 3, "user": 3},
                ratio={l: 100 for l in ("ko", "en", "cn", "jp", "other", "symbol", "user")},
                spacing={l: 0 for l in ("ko", "en", "cn", "jp", "other", "symbol", "user")})
    base.update(kw)
    return HwpCharShape(**base)


def test_font_ref_language_key_translation():
    out = map_char_shapes([_src()])
    fr = out[0].font_ref
    assert fr["hangul"] == 12
    assert fr["latin"] == 24
    assert fr["hanja"] == 3
    assert fr["japanese"] == 3
    assert set(fr.keys()) == {"hangul", "latin", "hanja", "japanese", "other", "symbol", "user"}


def test_shade_color_white_becomes_none():
    assert map_char_shapes([_src(shade_color="#ffffff")])[0].shade_color == "none"
    assert map_char_shapes([_src(shade_color="#FF0000")])[0].shade_color == "#FF0000"


def test_border_fill_id_passes_through_from_source():
    src = _src()
    src.border_fill_id = 7
    assert map_char_shapes([src])[0].border_fill_id == 7


def test_effects_passthrough():
    out = map_char_shapes([_src(underline_type="BOTTOM", underline_shape="SOLID",
                                outline_type="SOLID", shadow_type="DROP",
                                shadow_color="#B2B2B2", shadow_offset_x=10)])
    cp = out[0]
    assert cp.underline_type == "BOTTOM"
    assert cp.outline_type == "SOLID"
    assert cp.shadow_type == "DROP"
    assert cp.shadow_color == "#B2B2B2"
    assert cp.ratio["hangul"] == 100
