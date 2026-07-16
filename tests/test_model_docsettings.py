from hwp2hwpx.hwpmodel.model import HwpDocProperties, HwpCompatDocument, HwpDocInfo
from hwp2hwpx.owpml.model import BeginNum, CompatDocument, Header


def test_hwp_docsettings_defaults():
    assert HwpDocProperties().page_start == 1
    assert HwpDocProperties().equation_start == 1
    assert HwpCompatDocument().target == 0
    di = HwpDocInfo()
    assert di.doc_properties is None and di.compat is None


def test_owpml_docsettings_defaults():
    assert BeginNum().page == 1 and BeginNum().equation == 1
    assert CompatDocument().target_program == "HWP201X"
    h = Header()
    assert h.begin_num is None and h.compat is None
