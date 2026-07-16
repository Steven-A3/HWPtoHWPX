from hwp2hwpx.mapper.body import map_paragraph
from hwp2hwpx.hwpmodel.model import HwpParagraph, HwpLineSeg


def test_line_segs_mapped_field_for_field():
    hpar = HwpParagraph(para_shape_id=0, style_id=0, runs=[], line_segs=[
        HwpLineSeg(text_pos=0, vert_pos=10, vert_size=1800, text_height=1800,
                   baseline=1530, spacing=1080, horz_pos=0, horz_size=35816,
                   flags=393216),
    ])
    para = map_paragraph(hpar, 0)
    assert len(para.line_segs) == 1
    ls = para.line_segs[0]
    assert ls.vert_pos == 10
    assert ls.horz_size == 35816
    assert ls.flags == 393216
    assert ls.baseline == 1530


def test_no_line_segs_maps_to_empty():
    para = map_paragraph(HwpParagraph(para_shape_id=0), 0)
    assert para.line_segs == []
