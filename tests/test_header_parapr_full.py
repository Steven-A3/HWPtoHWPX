from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, ParaPr
from hwp2hwpx.constants import NS


def _hh(t):
    return "{%s}%s" % (NS["hh"], t)


def _hp(t):
    return "{%s}%s" % (NS["hp"], t)


def _hc(t):
    return "{%s}%s" % (NS["hc"], t)


def _header():
    return Header(para_prs=[ParaPr(id=0, align="CENTER", intent=-2000,
                                   margin_left=1000, margin_right=1000,
                                   margin_prev=0, margin_next=0,
                                   line_spacing=140, line_spacing_type="PERCENT",
                                   border_fill_id=2, heading_level=0, tab_pr_id=0)])


def test_parapr_full_subtree():
    root = etree.fromstring(header_xml(_header()))
    pp = root.find(".//" + _hh("paraPr"))
    assert pp.get("tabPrIDRef") == "0"
    assert pp.find(_hh("align")).get("horizontal") == "CENTER"
    assert pp.find(_hh("heading")).get("type") == "NONE"
    assert pp.find(_hh("breakSetting")).get("breakLatinWord") == "KEEP_WORD"
    assert pp.find(_hh("autoSpacing")) is not None
    sw = pp.find(_hp("switch"))
    assert sw is not None
    case = sw.find(_hp("case"))
    assert case.get("{%s}required-namespace" % NS["hp"]).endswith("HwpUnitChar")
    # both case and default carry margin + lineSpacing
    for branch in (case, sw.find(_hp("default"))):
        m = branch.find(_hh("margin"))
        assert m.find(_hc("intent")).get("value") == "-2000"
        assert m.find(_hc("left")).get("value") == "1000"
        ls = branch.find(_hh("lineSpacing"))
        assert ls.get("type") == "PERCENT" and ls.get("value") == "140"
    bd = pp.find(_hh("border"))
    assert bd.get("borderFillIDRef") == "2"


def test_tabproperties_present_and_ordered():
    root = etree.fromstring(header_xml(_header()))
    ref = root.find(_hh("refList"))
    order = [c.tag.rsplit("}", 1)[-1] for c in ref]
    assert order.index("charProperties") < order.index("tabProperties") < order.index("paraProperties")
    tp = root.find(".//" + _hh("tabProperties"))
    assert tp.get("itemCnt") == "1"
    assert tp.find(_hh("tabPr")).get("id") == "0"
