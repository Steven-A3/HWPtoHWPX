from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import (
    Section, Para, Run, SecPr, Grid, StartNum, Visibility, LineNumberShape,
    PagePr, Margin, NotePr, AutoNumFormat, NoteLine, NoteSpacing, Numbering,
    Placement, PageBorderFill, PageBorderOffset, ColPr, PageNum,
)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _q(tag):
    return "{%s}%s" % (HP, tag)


def _full_secpr():
    return SecPr(
        space_columns=1134, tab_stop=8000,
        grid=Grid(), start_num=StartNum(), visibility=Visibility(),
        line_number_shape=LineNumberShape(),
        page_pr=PagePr(width=59528, height=84188, margin=Margin(left=7088)),
        foot_note_pr=NotePr(auto_num_format=AutoNumFormat(), note_line=NoteLine(),
                            note_spacing=NoteSpacing(), numbering=Numbering(),
                            placement=Placement(place="EACH_COLUMN")),
        end_note_pr=NotePr(auto_num_format=AutoNumFormat(), note_line=NoteLine(),
                           note_spacing=NoteSpacing(), numbering=Numbering(),
                           placement=Placement(place="END_OF_DOCUMENT")),
        page_border_fills=[PageBorderFill(type=t, offset=PageBorderOffset(left=1417))
                           for t in ("BOTH", "EVEN", "ODD")],
        col_pr=ColPr(), page_num=PageNum(),
    )


def _root(section):
    return etree.fromstring(section_xml(section).split(b"?>", 1)[1])


def test_secpr_is_first_child_of_first_paragraphs_first_run():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=5)])],
                  sec_pr=_full_secpr())
    root = _root(sec)
    first_p = root.find(_q("p"))
    first_run = first_p.find(_q("run"))
    assert first_run is not None
    assert etree.QName(first_run[0]).localname == "secPr"


def test_secpr_subtree_shape():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])],
                  sec_pr=_full_secpr())
    sp = _root(sec).find(".//" + _q("secPr"))
    kids = [etree.QName(c).localname for c in sp]
    assert kids == ["grid", "startNum", "visibility", "lineNumberShape",
                    "pagePr", "footNotePr", "endNotePr",
                    "pageBorderFill", "pageBorderFill", "pageBorderFill"]
    assert sp.get("spaceColumns") == "1134"
    assert sp.get("tabStopVal") == "4000"
    pp = sp.find(_q("pagePr"))
    assert pp.find(_q("margin")).get("left") == "7088"
    fn = sp.find(_q("footNotePr"))
    assert [etree.QName(c).localname for c in fn] == [
        "autoNumFormat", "noteLine", "noteSpacing", "numbering", "placement"]
    pbf = sp.findall(_q("pageBorderFill"))
    assert [b.get("type") for b in pbf] == ["BOTH", "EVEN", "ODD"]
    assert pbf[0].find(_q("offset")).get("left") == "1417"


def test_colpr_and_pagenum_are_ctrl_wrapped_in_first_paragraph():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])],
                  sec_pr=_full_secpr())
    first_p = _root(sec).find(_q("p"))
    ctrls = first_p.findall(".//" + _q("ctrl"))
    wrapped = [etree.QName(c[0]).localname for c in ctrls]
    assert "colPr" in wrapped and "pageNum" in wrapped


def test_no_secpr_when_section_has_none():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])])
    assert _root(sec).find(".//" + _q("secPr")) is None


def test_absent_colpr_pagenum_not_emitted():
    sp = _full_secpr()
    sp.col_pr = None
    sp.page_num = None
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])],
                  sec_pr=sp)
    first_p = _root(sec).find(_q("p"))
    assert first_p.find(".//" + _q("colPr")) is None
    assert first_p.find(".//" + _q("pageNum")) is None


def test_only_first_paragraph_gets_secpr():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)]),
                         Para(id=1, para_pr_id=0, runs=[Run(char_pr_id=0)])],
                  sec_pr=_full_secpr())
    ps = _root(sec).findall(_q("p"))
    assert ps[1].find(".//" + _q("secPr")) is None
