from hwp2hwpx.hwpmodel.model import HwpDrawing, HwpShapeComponent, HwpPicture
from hwp2hwpx.mapper.drawing import map_drawing


def _pic_drawing():
    return HwpDrawing(
        kind="pic", instance_id=1111203703, z_order=15, flow="block", inline=1,
        x=0, y=0, width=46545, height=65913, hrelto="paragraph", vrelto="paragraph",
        component=HwpShapeComponent(initial_width=36480, initial_height=51660,
                                    width=46545, height=65913, center_x=23272,
                                    center_y=32956,
                                    scaler_matrix=[1.2759, 0.0, 0.0, 1.2759, 0.0, 0.0]),
        picture=HwpPicture(instance_id=37461880, bindata_id=1,
                           img_rect=[(0, 0), (36480, 0), (36480, 51660), (0, 51660)],
                           img_clip=(0, 36480, 0, 51660), brightness=0, contrast=0,
                           effect=0, dim_width=36480, dim_height=51660),
    )


def test_map_pic_container_and_image():
    pic = map_drawing(_pic_drawing())
    assert pic.__class__.__name__ == "Pic"
    assert pic.id == 1111203703 and pic.z_order == 15 and pic.instid == 37461880
    assert pic.text_wrap == "TOP_AND_BOTTOM"
    assert pic.rotation_info.rotate_image == 1     # pictures: 1 (lines: 0)
    assert pic.org_sz.width == 36480 and pic.cur_sz.width == 46545
    assert pic.pos.horz_rel_to == "PARA" and pic.pos.treat_as_char == 1
    assert pic.img.bin_item_id == "image1" and pic.img.effect == "REAL_PIC"
    assert (pic.img_rect.pt2.x, pic.img_rect.pt2.y) == (36480, 51660)
    assert pic.img_clip.right == 36480 and pic.img_clip.bottom == 51660
    assert pic.img_dim.dim_width == 36480
    assert pic.shape_comment is not None


def test_line_still_maps_and_rotate_image_zero():
    from hwp2hwpx.hwpmodel.model import HwpLineShape
    ln = map_drawing(HwpDrawing(kind="line", component=HwpShapeComponent(),
                                line=HwpLineShape(p0=(0, 0), p1=(1, 1))))
    assert ln.__class__.__name__ == "Line"
    assert ln.rotation_info.rotate_image == 0


def test_none_and_unknown_kind():
    assert map_drawing(None) is None
    assert map_drawing(HwpDrawing(kind="rect", component=HwpShapeComponent())) is None
