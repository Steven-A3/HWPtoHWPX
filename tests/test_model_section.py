from hwp2hwpx.hwpmodel.model import (
    HwpPageDef, HwpNoteShape, HwpPageBorder, HwpColumnsDef, HwpPageNum,
    HwpSectionDef, HwpSection,
)


def test_section_records_default_construct():
    assert HwpPageDef().width == 0
    assert HwpNoteShape().stroke_type == "none"
    assert HwpPageBorder().borderfill_id == 1
    assert HwpColumnsDef().count == 1
    assert HwpPageNum().position == "bottom_center"
    sd = HwpSectionDef()
    assert sd.page is None and sd.footnote is None and sd.page_borders == []
    assert sd.columns is None and sd.page_num is None


def test_hwpsection_carries_sec_def():
    s = HwpSection(paragraphs=[], sec_def=HwpSectionDef(column_spacing=1134))
    assert s.sec_def.column_spacing == 1134
