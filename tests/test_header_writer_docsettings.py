from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, BeginNum, CompatDocument

HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _q(t):
    return "{%s}%s" % (HH, t)


def _root(header):
    return etree.fromstring(header_xml(header).split(b"?>", 1)[1])


def test_begin_num_is_first_child_before_reflist():
    h = Header(begin_num=BeginNum(page=1, footnote=2, endnote=3, pic=4, tbl=5,
                                  equation=6))
    root = _root(h)
    assert etree.QName(root[0]).localname == "beginNum"
    bn = root[0]
    assert bn.get("page") == "1" and bn.get("footnote") == "2"
    assert bn.get("equation") == "6"
    # refList comes after beginNum
    tags = [etree.QName(c).localname for c in root]
    assert tags.index("beginNum") < tags.index("refList")


def test_tail_elements_after_reflist():
    h = Header(compat=CompatDocument(target_program="HWP201X"))
    root = _root(h)
    tags = [etree.QName(c).localname for c in root]
    for t in ("compatibleDocument", "docOption", "trackchageConfig"):
        assert t in tags and tags.index(t) > tags.index("refList")
    cd = root.find(_q("compatibleDocument"))
    assert cd.get("targetProgram") == "HWP201X"
    assert cd.find(_q("layoutCompatibility")) is not None
    li = root.find(_q("docOption")).find(_q("linkinfo"))
    assert li.get("path") == "" and li.get("pageInherit") == "1"
    assert li.get("footnoteInherit") == "0"
    assert root.find(_q("trackchageConfig")).get("flags") == "56"


def test_none_begin_num_and_compat_emit_defaults():
    root = _root(Header())
    assert root.find(_q("beginNum")).get("page") == "1"
    assert root.find(_q("compatibleDocument")).get("targetProgram") == "HWP201X"
