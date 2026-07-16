from hwp2hwpx.hwpmodel.model import (
    HwpDrawing, HwpShapeComponent, HwpLineShape, HwpRun, HwpParagraph,
)
from hwp2hwpx.mapper.drawing import map_drawing
from hwp2hwpx.mapper.body import map_paragraph


def _line_drawing():
    return HwpDrawing(
        kind="line", instance_id=111, z_order=29, flow="front", inline=0,
        x=29344, y=24972, width=0, height=1504, hrelto="paper", vrelto="paper",
        halign="left", valign="top", width_relto="absolute",
        component=HwpShapeComponent(
            initial_width=100, initial_height=100, width=0, height=1504,
            center_x=0, center_y=752,
            trans_matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            scaler_matrix=[0.0, 0.0, 0.0, 15.04, 0.0, 0.0],
            rotator_matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
        line=HwpLineShape(color="#000000", width=200, stroke="solid",
                          line_end="flat", p0=(0, 0), p1=(100, 100)),
    )


def test_map_line_container_and_geometry():
    ln = map_drawing(_line_drawing())
    assert ln.id == 111 and ln.z_order == 29
    assert ln.text_wrap == "IN_FRONT_OF_TEXT"
    assert ln.org_sz.width == 100 and ln.cur_sz.height == 1504
    assert ln.rotation_info.center_y == 752
    assert ln.pos.horz_rel_to == "PAPER" and ln.pos.horz_offset == 29344
    assert ln.pos.vert_offset == 24972
    assert ln.sz.width_rel_to == "ABSOLUTE"
    assert ln.out_margin.left == 0


def test_matrix_mapping_abcdef_to_e1e6():
    ln = map_drawing(_line_drawing())
    # translation identity -> e1=1,e5=1
    assert (ln.rendering_info.trans.e1, ln.rendering_info.trans.e5) == ("1", "1")
    # scaler d=15.04 -> e5
    assert ln.rendering_info.sca.e5 == "15.04"
    assert ln.rendering_info.sca.e1 == "0"


def test_line_shape_and_points():
    ln = map_drawing(_line_drawing())
    assert ln.line_shape.style == "SOLID" and ln.line_shape.end_cap == "FLAT"
    assert ln.line_shape.width == 200
    assert (ln.start_pt.x, ln.start_pt.y) == (0, 0)
    assert (ln.end_pt.x, ln.end_pt.y) == (100, 100)


def test_none_and_non_line_map_to_none():
    assert map_drawing(None) is None
    assert map_drawing(HwpDrawing(kind="pic")) is None


def test_map_paragraph_routes_drawing_run():
    hpar = HwpParagraph(para_shape_id=0, style_id=0,
                        runs=[HwpRun(char_shape_id=0, drawing=_line_drawing())])
    para = map_paragraph(hpar, 0)
    assert len(para.runs) == 1
    assert para.runs[0].drawing is not None
    assert para.runs[0].drawing.id == 111
    assert para.runs[0].table is None
