from hwp2hwpx.mapper.body import map_paragraph
from hwp2hwpx.hwpmodel.model import HwpParagraph, HwpRun, HwpControl
from hwp2hwpx.owpml.model import Control, Text


def test_run_contents_map_to_text_and_control():
    hpar = HwpParagraph(para_shape_id=0, style_id=0, runs=[
        HwpRun(char_shape_id=7, contents=["가", HwpControl("fwSpace"), "나",
                                          HwpControl("lineBreak")]),
    ])
    para = map_paragraph(hpar, 0)
    items = para.runs[0].texts
    assert [type(x).__name__ for x in items] == ["Text", "Control", "Text", "Control"]
    assert items[0].content == "가"
    assert items[1].kind == "fwSpace"
    assert items[2].content == "나"
    assert items[3].kind == "lineBreak"
    assert para.runs[0].char_pr_id == 7


def test_empty_run_still_placeholder():
    hpar = HwpParagraph(para_shape_id=0, style_id=0, runs=[])
    para = map_paragraph(hpar, 0)
    assert len(para.runs) == 1
    assert para.runs[0].texts == []
