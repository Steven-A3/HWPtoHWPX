from hwp2hwpx.owpml.model import Control, Run, Text


def test_control_kind():
    assert Control(kind="lineBreak").kind == "lineBreak"
    assert Control().kind == "fwSpace"


def test_run_texts_can_mix_text_and_control():
    run = Run(char_pr_id=0, texts=[Text("가"), Control("fwSpace"), Text("나")])
    assert [type(x).__name__ for x in run.texts] == ["Text", "Control", "Text"]
