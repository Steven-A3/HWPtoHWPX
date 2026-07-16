from hwp2hwpx.hwpmodel.model import (
    HwpShapeComponent, HwpLineShape, HwpDrawing, HwpRun,
)


def test_drawing_defaults():
    c = HwpShapeComponent()
    assert c.trans_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert HwpLineShape().stroke == "solid"
    assert HwpLineShape().p0 == (0, 0)
    d = HwpDrawing()
    assert d.kind == "line" and d.component is None and d.line is None


def test_hwprun_carries_drawing():
    r = HwpRun(char_shape_id=0, drawing=HwpDrawing(instance_id=42))
    assert r.drawing.instance_id == 42
    assert r.table is None
