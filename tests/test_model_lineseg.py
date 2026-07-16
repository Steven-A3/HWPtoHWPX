from hwp2hwpx.hwpmodel.model import HwpLineSeg, HwpParagraph
from hwp2hwpx.owpml.model import LineSeg, Para


def test_hwp_lineseg_defaults():
    ls = HwpLineSeg()
    assert (ls.text_pos, ls.vert_pos, ls.vert_size, ls.text_height, ls.baseline,
            ls.spacing, ls.horz_pos, ls.horz_size, ls.flags) == (0,) * 9


def test_hwp_paragraph_line_segs_default():
    assert HwpParagraph(para_shape_id=0).line_segs == []


def test_owpml_lineseg_and_para():
    ls = LineSeg(text_pos=1, vert_pos=2, vert_size=3, text_height=4, baseline=5,
                 spacing=6, horz_pos=7, horz_size=8, flags=9)
    assert ls.horz_size == 8 and ls.flags == 9
    assert Para(id=0, para_pr_id=0).line_segs == []
