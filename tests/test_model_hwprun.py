from hwp2hwpx.hwpmodel.model import HwpRun, HwpControl


def test_hwprun_text_property_joins_strings():
    run = HwpRun(char_shape_id=0, contents=["가", HwpControl("fwSpace"), "나"])
    assert run.text == "가나"


def test_hwprun_defaults():
    run = HwpRun(char_shape_id=0)
    assert run.contents == []
    assert run.text == ""
    assert run.table is None


def test_hwpcontrol_kind():
    assert HwpControl("lineBreak").kind == "lineBreak"
