from hwp2hwpx.hwpmodel.model import HwpRangeTag, HwpParagraph
from hwp2hwpx.owpml.model import MarkpenBegin, MarkpenEnd


def test_range_tag_fields():
    rt = HwpRangeTag(start=16, end=34, color="#FFFFFF")
    assert (rt.start, rt.end, rt.color) == (16, 34, "#FFFFFF")


def test_paragraph_markpens_default_is_independent_empty_list():
    a = HwpParagraph(para_shape_id=0)
    b = HwpParagraph(para_shape_id=0)
    a.markpens.append(HwpRangeTag(1, 2, "#FFFFFF"))
    assert a.markpens != b.markpens and b.markpens == []


def test_owpml_markpen_markers():
    assert MarkpenBegin(color="#00FF00").color == "#00FF00"
    assert MarkpenBegin().color == "#FFFFFF"
    MarkpenEnd()  # constructs with no args
