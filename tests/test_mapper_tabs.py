from hwp2hwpx.mapper.tab import map_tab_defs
from hwp2hwpx.mapper.para_pr import map_para_shapes
from hwp2hwpx.hwpmodel.model import HwpTab, HwpTabDef, HwpParaShape


def test_map_tab_defs_transform():
    src = [HwpTabDef(index=1, auto_tab_left=0, auto_tab_right=0, tabs=[
        HwpTab(pos=3216, kind="left", fill_type=0),
        HwpTab(pos=37296, kind="right", fill_type=3),
    ])]
    out = map_tab_defs(src)
    td = out[0]
    assert td.id == 1
    assert td.tabs[0].pos == 3216
    assert td.tabs[0].type == "LEFT"
    assert td.tabs[0].leader == "NONE"
    assert td.tabs[1].type == "RIGHT"
    assert td.tabs[1].leader == "DASH"


def test_map_empty_tab_def():
    out = map_tab_defs([HwpTabDef(index=0)])
    assert out[0].tabs == []


def test_para_shapes_emit_real_tab_pr_id():
    src = [HwpParaShape(index=0, tab_def_id=5)]
    out = map_para_shapes(src)
    assert out[0].tab_pr_id == 5
