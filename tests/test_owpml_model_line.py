from hwp2hwpx.owpml.model import (
    Line, Offset, OrgSz, CurSz, Flip, RotationInfo, Matrix, RenderingInfo,
    LineShape, WinBrush, Shadow, Pt, ShapeSz, ShapePos, ShapeOutMargin, Run,
)


def test_line_and_children_defaults():
    assert Matrix().e1 == "1" and Matrix().e5 == "1"
    assert LineShape().style == "SOLID"
    assert WinBrush().face_color == "#FFFFFF"
    assert Shadow().type == "NONE"
    assert ShapeSz().width_rel_to == "ABSOLUTE"
    assert ShapePos().horz_rel_to == "PAPER"
    ln = Line(id=7)
    assert ln.id == 7 and ln.text_wrap == "TOP_AND_BOTTOM"
    assert ln.line_shape is None and ln.start_pt is None


def test_run_carries_drawing():
    r = Run(char_pr_id=0, texts=[Line(id=9)])
    assert r.drawing.id == 9 and r.table is None
