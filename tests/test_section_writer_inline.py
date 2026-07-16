from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text, Control
from hwp2hwpx.constants import NS


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _run_el(run):
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[run])])
    root = etree.fromstring(section_xml(sec))
    return next(root.iter(_hp("run")))


def test_control_between_texts_is_mixed_content():
    r = _run_el(Run(char_pr_id=1, texts=[Text("가"), Control("fwSpace"), Text("나")]))
    ts = list(r.iter(_hp("t")))
    assert len(ts) == 1
    t = ts[0]
    assert t.text == "가"
    fw = list(t)[0]
    assert etree.QName(fw).localname == "fwSpace"
    assert fw.tail == "나"


def test_control_first_puts_text_in_tail():
    r = _run_el(Run(char_pr_id=1, texts=[Control("lineBreak"), Text("AI")]))
    t = next(r.iter(_hp("t")))
    assert t.text is None
    lb = list(t)[0]
    assert etree.QName(lb).localname == "lineBreak"
    assert lb.tail == "AI"


def test_adjacent_texts_concatenate_in_one_t():
    r = _run_el(Run(char_pr_id=1, texts=[Text("가나"), Text("다라")]))
    ts = list(r.iter(_hp("t")))
    assert len(ts) == 1
    assert ts[0].text == "가나다라"


def test_empty_run_emits_no_t():
    r = _run_el(Run(char_pr_id=0, texts=[]))
    assert list(r.iter(_hp("t"))) == []
