from hwp2hwpx.hwpmodel.model import HwpTab, HwpTabDef, HwpDocInfo, HwpParaShape
from hwp2hwpx.owpml.model import TabItem, TabDef, Header


def test_hwp_tab_defaults():
    t = HwpTab()
    assert t.pos == 0 and t.kind == "left" and t.fill_type == 0
    td = HwpTabDef(index=0)
    assert td.auto_tab_left == 0 and td.auto_tab_right == 0 and td.tabs == []


def test_docinfo_and_parashape_tab_fields():
    assert HwpDocInfo().tab_defs == []
    assert HwpParaShape(index=0).tab_def_id == 0


def test_owpml_tab_defaults():
    ti = TabItem()
    assert ti.pos == 0 and ti.type == "LEFT" and ti.leader == "NONE"
    td = TabDef(id=0)
    assert td.auto_tab_left == 0 and td.auto_tab_right == 0 and td.tabs == []
    assert Header().tab_defs == []
