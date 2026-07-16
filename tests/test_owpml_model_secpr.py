# tests/test_owpml_model_secpr.py
from hwp2hwpx.owpml.model import (
    SecPr, Grid, StartNum, Visibility, LineNumberShape, PagePr, Margin,
    NotePr, AutoNumFormat, NoteLine, NoteSpacing, Numbering, Placement,
    PageBorderFill, Offset, ColPr, PageNum, Section,
)


def test_secpr_defaults_are_hancom_constants():
    sp = SecPr()
    assert sp.id == ""
    assert sp.tab_stop_val == 4000
    assert sp.tab_stop_unit == "HWPUNIT"
    assert sp.memo_shape_id == 0
    assert sp.text_vertical_width_head == 0
    assert sp.master_page_cnt == 0
    assert sp.page_border_fills == []
    assert AutoNumFormat().type == "DIGIT"
    assert Numbering().type == "CONTINUOUS"
    assert LineNumberShape().restart_type == 0


def test_section_carries_sec_pr():
    s = Section(paras=[], sec_pr=SecPr(space_columns=1134))
    assert s.sec_pr.space_columns == 1134
