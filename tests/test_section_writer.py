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
