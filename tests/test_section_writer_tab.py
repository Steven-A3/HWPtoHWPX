from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text, Control
from hwp2hwpx.constants import NS


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _run_el(run):
    root = etree.fromstring(section_xml(Section(paras=[Para(id=0, para_pr_id=0, runs=[run])])))
    return next(root.iter(_hp("run")))


def test_tab_emits_hp_tab_with_attrs():
    r = _run_el(Run(char_pr_id=1, texts=[Text("가"), Control("tab"), Text("나")]))
    t = next(r.iter(_hp("t")))
    tab = t.find(_hp("tab"))
    assert tab is not None
    assert tab.get("width") == "0"
    assert tab.get("leader") == "0"
    assert tab.get("type") == "0"
    assert tab.tail == "나"


def test_fwspace_stays_empty():
    r = _run_el(Run(char_pr_id=1, texts=[Control("fwSpace")]))
    fw = next(r.iter(_hp("fwSpace")))
    assert fw.keys() == []  # no attributes
