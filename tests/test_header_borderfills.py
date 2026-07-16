from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, BorderFill, Border
from hwp2hwpx.constants import NS


def _hh(t):
    return "{%s}%s" % (NS["hh"], t)


def _hc(t):
    return "{%s}%s" % (NS["hc"], t)


def _header():
    return Header(border_fills=[
        BorderFill(id=0, borders=[
            Border(kind="left", type="SOLID", width="0.4 mm", color="#000000"),
            Border(kind="right", type="SOLID", width="0.4 mm", color="#000000"),
            Border(kind="top", type="SOLID", width="0.4 mm", color="#000000"),
            Border(kind="bottom", type="SOLID", width="0.4 mm", color="#000000"),
            Border(kind="diagonal", type="NONE", width="0.1 mm", color="#000000"),
        ]),
        BorderFill(id=1, borders=[], fill_color="#bbbbbb"),
    ])


def test_borderfills_present_with_count():
    root = etree.fromstring(header_xml(_header()))
    bfs = root.find(".//" + _hh("borderFills"))
    assert bfs is not None
    assert bfs.get("itemCnt") == "2"
    assert len(bfs.findall(_hh("borderFill"))) == 2
    first = bfs.findall(_hh("borderFill"))[0]
    assert first.find(_hh("leftBorder")).get("type") == "SOLID"
    assert first.find(_hh("leftBorder")).get("width") == "0.4 mm"


def test_fillbrush_only_when_filled():
    root = etree.fromstring(header_xml(_header()))
    bfs = root.findall(".//" + _hh("borderFill"))
    assert bfs[0].find(_hc("fillBrush")) is None          # id 0: no fill
    wb = bfs[1].find(_hc("fillBrush")).find(_hc("winBrush"))
    assert wb.get("faceColor") == "#bbbbbb"


def test_borderfills_before_charproperties():
    root = etree.fromstring(header_xml(_header()))
    ref = root.find(_hh("refList"))
    order = [c.tag.rsplit("}", 1)[-1] for c in ref]
    assert order.index("borderFills") < order.index("charProperties")
    assert order.index("fontfaces") < order.index("borderFills")
