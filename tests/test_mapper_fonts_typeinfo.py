from hwp2hwpx.mapper.fonts import map_fonts
from hwp2hwpx.hwpmodel.model import HwpFont, HwpPanose


def _font(ft):
    return HwpFont(index=0, name="X",
                   panose=HwpPanose(family_type=ft, weight=6, x_height=1))


def test_family_type_mapping():
    assert map_fonts([_font(2)])["HANGUL"][0].type_info.family_type == "FCAT_GOTHIC"
    assert map_fonts([_font(1)])["HANGUL"][0].type_info.family_type == "FCAT_MYUNGJO"
    assert map_fonts([_font(99)])["HANGUL"][0].type_info.family_type == "FCAT_GOTHIC"


def test_type_info_fields_passthrough():
    ti = map_fonts([_font(2)])["HANGUL"][0].type_info
    assert ti.weight == 6
    assert ti.x_height == 1


def test_font_without_panose_has_no_type_info():
    out = map_fonts([HwpFont(index=0, name="X")])
    assert out["HANGUL"][0].type_info is None
