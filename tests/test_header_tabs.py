from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, CharPr, ParaPr, TabDef, TabItem
from hwp2hwpx.constants import NS


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _root(tab_defs):
    header = Header(char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)], tab_defs=tab_defs)
    return etree.fromstring(header_xml(header))


def test_tab_properties_item_count_and_ids():
    root = _root([TabDef(id=0), TabDef(id=1, tabs=[TabItem(pos=3216)])])
    tp = next(root.iter(_hh("tabProperties")))
    assert tp.get("itemCnt") == "2"
    tabprs = list(root.iter(_hh("tabPr")))
    assert [t.get("id") for t in tabprs] == ["0", "1"]


def test_empty_tab_def_is_self_closing():
    root = _root([TabDef(id=0, auto_tab_left=1)])
    tabpr = next(root.iter(_hh("tabPr")))
    assert tabpr.get("autoTabLeft") == "1"
    assert list(tabpr) == []  # no children


def test_non_empty_tab_def_emits_switch_case_default():
    root = _root([TabDef(id=1, tabs=[TabItem(pos=3216, type="LEFT", leader="DASH")])])
    tabpr = list(root.iter(_hh("tabPr")))[0]
    switches = list(tabpr.iter(_hp("switch")))
    assert len(switches) == 1
    case = switches[0].find(_hp("case"))
    default = switches[0].find(_hp("default"))
    ci = case.find(_hh("tabItem"))
    di = default.find(_hh("tabItem"))
    assert ci.get("pos") == "1608"        # 3216 // 2
    assert ci.get("unit") == "HWPUNIT"
    assert ci.get("type") == "LEFT"
    assert ci.get("leader") == "DASH"
    assert di.get("pos") == "3216"        # raw
    assert di.get("unit") is None         # default has no unit


def test_empty_tab_defs_falls_back_to_default():
    root = _root([])
    tabprs = list(root.iter(_hh("tabPr")))
    assert len(tabprs) == 1
    assert tabprs[0].get("id") == "0"
