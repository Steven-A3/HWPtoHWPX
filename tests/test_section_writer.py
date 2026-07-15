from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text
from hwp2hwpx.constants import NS


def _hs(tag):
    return "{%s}%s" % (NS["hs"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def test_section_paragraph_run_text():
    sec = Section(paras=[
        Para(id=0, para_pr_id=2, style_id=1,
             runs=[Run(char_pr_id=3, texts=[Text("가나"), Text("다라")])]),
    ])
    root = etree.fromstring(section_xml(sec))
    assert root.tag == _hs("sec")
    p = root.find(_hp("p"))
    assert p.get("paraPrIDRef") == "2"
    assert p.get("styleIDRef") == "1"
    run = p.find(_hp("run"))
    assert run.get("charPrIDRef") == "3"
    texts = [t.text for t in run.iter(_hp("t"))]
    assert texts == ["가나", "다라"]


def test_section_paragraph_always_has_at_least_one_run():
    """Every <hp:p> must have >=1 <hp:run> child, even for a paragraph
    with no text -- Hancom never emits a run-less <hp:p>, and a
    self-closing <hp:run charPrIDRef="N"/> (no <hp:t>) is how it
    represents an empty paragraph."""
    sec = Section(paras=[
        Para(id=0, para_pr_id=0, style_id=0,
             runs=[Run(char_pr_id=0, texts=[])]),
    ])
    root = etree.fromstring(section_xml(sec))
    for p in root.iter(_hp("p")):
        runs = list(p.iter(_hp("run")))
        assert len(runs) >= 1
    run = root.find(_hp("p")).find(_hp("run"))
    assert run.get("charPrIDRef") == "0"
    assert list(run.iter(_hp("t"))) == []
