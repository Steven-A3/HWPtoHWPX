from hwp2hwpx.owpml.model import Run, Text, Table, Pic, Line, ShapePos
from hwp2hwpx.owpml.section_writer import _run_has_inline_object


def test_table_run_is_inline():
    assert _run_has_inline_object(Run(char_pr_id=0, texts=[], table=Table())) is True


def test_inline_pic_run_is_inline():
    run = Run(char_pr_id=0, texts=[], drawing=Pic(pos=ShapePos(treat_as_char=1)))
    assert _run_has_inline_object(run) is True


def test_floating_line_run_is_not_inline():
    run = Run(char_pr_id=0, texts=[], drawing=Line(pos=ShapePos(treat_as_char=0)))
    assert _run_has_inline_object(run) is False


def test_plain_text_run_is_not_inline():
    assert _run_has_inline_object(Run(char_pr_id=5, texts=[Text("가나다")])) is False


def test_drawing_with_no_pos_is_not_inline():
    run = Run(char_pr_id=0, texts=[], drawing=Pic(pos=None))
    assert _run_has_inline_object(run) is False
