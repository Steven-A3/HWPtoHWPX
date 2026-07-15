from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text, Table, TableRow, Tc
from hwp2hwpx.constants import NS


def _hp(t):
    return "{%s}%s" % (NS["hp"], t)


def _section_with_table():
    cell = Tc(col_addr=0, row_addr=0, col_span=2, row_span=1, width=100, height=50,
              border_fill_id=5, valign="CENTER",
              paras=[Para(id=0, para_pr_id=0,
                          runs=[Run(char_pr_id=3, texts=[Text("셀")])])])
    table = Table(id=0, row_cnt=1, col_cnt=2, cell_spacing=0, border_fill_id=4,
                  width=100, height=50, rows=[TableRow(cells=[cell])])
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[], table=table)])
    return Section(paras=[para])


def test_table_emitted_inside_run():
    root = etree.fromstring(section_xml(_section_with_table()))
    tbl = root.find(".//" + _hp("tbl"))
    assert tbl is not None
    assert tbl.get("rowCnt") == "1" and tbl.get("colCnt") == "2"
    assert tbl.get("borderFillIDRef") == "4"
    # tbl lives inside a run
    assert tbl.getparent().tag == _hp("run")
    tc = tbl.find(".//" + _hp("tc"))
    assert tc.get("borderFillIDRef") == "5"
    assert tc.find(_hp("cellAddr")).get("colAddr") == "0"
    assert tc.find(_hp("cellSpan")).get("colSpan") == "2"
    assert tc.find(_hp("cellSz")).get("width") == "100"
    # cell paragraph text is present in the subList
    assert tc.find(_hp("subList")) is not None
    texts = [t.text for t in tc.iter(_hp("t"))]
    assert "셀" in texts


def test_table_id_is_set_and_wellformed():
    root = etree.fromstring(section_xml(_section_with_table()))
    tbl = root.find(".//" + _hp("tbl"))
    assert tbl.get("id") is not None and tbl.get("id") != ""
    assert tbl.find(_hp("sz")) is not None
    assert tbl.find(_hp("pos")) is not None


def test_plain_paragraph_unchanged():
    from hwp2hwpx.owpml.model import Section as S, Para as P, Run as R, Text as T
    root = etree.fromstring(section_xml(S(paras=[P(id=0, para_pr_id=1,
                                                   runs=[R(char_pr_id=2, texts=[T("x")])])])))
    p = root.find(_hp("p"))
    assert p.get("paraPrIDRef") == "1"
    assert p.find(_hp("run")).find(_hp("t")).text == "x"
