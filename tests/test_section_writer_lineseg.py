# tests/test_section_writer_lineseg.py
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text, LineSeg
from hwp2hwpx.constants import NS


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _p_el(para):
    root = etree.fromstring(section_xml(Section(paras=[para])))
    return next(root.iter(_hp("p")))


def test_linesegarray_after_runs_with_attrs():
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=1, texts=[Text("가")])],
                line_segs=[LineSeg(text_pos=0, vert_pos=10, vert_size=1800,
                                   text_height=1800, baseline=1530, spacing=1080,
                                   horz_pos=0, horz_size=35816, flags=393216)])
    p = _p_el(para)
    children = [etree.QName(c).localname for c in p]
    assert children == ["run", "linesegarray"]  # linesegarray follows the run
    lsa = p.find(_hp("linesegarray"))
    segs = lsa.findall(_hp("lineseg"))
    assert len(segs) == 1
    s = segs[0]
    assert s.get("textpos") == "0"
    assert s.get("vertpos") == "10"
    assert s.get("vertsize") == "1800"
    assert s.get("textheight") == "1800"
    assert s.get("baseline") == "1530"
    assert s.get("spacing") == "1080"
    assert s.get("horzpos") == "0"
    assert s.get("horzsize") == "35816"
    assert s.get("flags") == "393216"


def test_multiple_line_segs():
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[])],
                line_segs=[LineSeg(vert_pos=0), LineSeg(vert_pos=1800)])
    p = _p_el(para)
    segs = list(p.iter(_hp("lineseg")))
    assert [s.get("vertpos") for s in segs] == ["0", "1800"]


def test_no_linesegarray_when_empty():
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[])], line_segs=[])
    p = _p_el(para)
    assert p.find(_hp("linesegarray")) is None
