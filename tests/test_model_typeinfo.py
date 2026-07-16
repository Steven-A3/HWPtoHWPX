from hwp2hwpx.hwpmodel.model import HwpPanose, HwpFont
from hwp2hwpx.owpml.model import TypeInfo, Font


def test_hwp_panose_defaults():
    p = HwpPanose()
    assert (p.family_type, p.weight, p.proportion, p.contrast, p.stroke_variation,
            p.arm_style, p.letterform, p.midline, p.x_height) == (0,) * 9
    assert HwpFont(index=0, name="굴림").panose is None


def test_owpml_typeinfo_defaults():
    t = TypeInfo(family_type="FCAT_MYUNGJO", weight=6, x_height=1)
    assert t.family_type == "FCAT_MYUNGJO"
    assert t.weight == 6 and t.x_height == 1
    assert Font(id=0, face="굴림").type_info is None
