"""Serialize an OWPML Section to Contents/sectionN.xml."""
from lxml import etree
from ..constants import NS, XML_DECL

_NSMAP = {k: v for k, v in NS.items()}


def _hs(tag):
    return "{%s}%s" % (NS["hs"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _write_run(p_el, run, state):
    r = etree.SubElement(p_el, _hp("run"))
    r.set("charPrIDRef", str(run.char_pr_id))
    for t in run.texts:
        te = etree.SubElement(r, _hp("t"))
        te.text = t.content
    if getattr(run, "table", None) is not None:
        _write_table(r, run.table, state)


def _write_paragraph(parent_el, para, state):
    p = etree.SubElement(parent_el, _hp("p"))
    p.set("id", str(state["para_id"]))
    state["para_id"] += 1
    p.set("paraPrIDRef", str(para.para_pr_id))
    p.set("styleIDRef", str(para.style_id))
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")
    for run in para.runs:
        _write_run(p, run, state)


def _write_table(run_el, table, state):
    state["tbl_id"] += 1
    t = etree.SubElement(run_el, _hp("tbl"))
    t.set("id", str(state["tbl_id"]))
    for k, v in (("zOrder", "0"), ("numberingType", "TABLE"),
                 ("textWrap", "TOP_AND_BOTTOM"), ("textFlow", "BOTH_SIDES"),
                 ("lock", "0"), ("dropcapstyle", "None"), ("pageBreak", "NONE"),
                 ("repeatHeader", "1")):
        t.set(k, v)
    t.set("rowCnt", str(table.row_cnt))
    t.set("colCnt", str(table.col_cnt))
    t.set("cellSpacing", str(table.cell_spacing))
    t.set("borderFillIDRef", str(table.border_fill_id))
    t.set("noAdjust", "0")
    sz = etree.SubElement(t, _hp("sz"))
    sz.set("width", str(table.width))
    sz.set("widthRelTo", "ABSOLUTE")
    sz.set("height", str(table.height))
    sz.set("heightRelTo", "ABSOLUTE")
    sz.set("protect", "0")
    pos = etree.SubElement(t, _hp("pos"))
    for k, v in (("treatAsChar", "1"), ("affectLSpacing", "0"),
                 ("flowWithText", "1"), ("allowOverlap", "0"),
                 ("holdAnchorAndSO", "0"), ("vertRelTo", "PARA"),
                 ("horzRelTo", "COLUMN"), ("vertAlign", "TOP"),
                 ("horzAlign", "LEFT")):
        pos.set(k, v)
    for tag in ("outMargin", "inMargin"):
        m = etree.SubElement(t, _hp(tag))
        for side in ("left", "right", "top", "bottom"):
            m.set(side, "141")
    for row in table.rows:
        tr = etree.SubElement(t, _hp("tr"))
        for cell in row.cells:
            _write_cell(tr, cell, state)


def _write_cell(tr_el, cell, state):
    tc = etree.SubElement(tr_el, _hp("tc"))
    tc.set("name", "")
    tc.set("header", "0")
    tc.set("hasMargin", "0")
    tc.set("protect", "0")
    tc.set("editable", "0")
    tc.set("dirty", "0")
    tc.set("borderFillIDRef", str(cell.border_fill_id))
    sub = etree.SubElement(tc, _hp("subList"))
    for k, v in (("id", ""), ("textDirection", "HORIZONTAL"), ("lineWrap", "BREAK"),
                 ("vertAlign", cell.valign), ("linkListIDRef", "0"),
                 ("linkListNextIDRef", "0"), ("textWidth", "0"),
                 ("textHeight", "0"), ("hasTextRef", "0"), ("hasNumRef", "0")):
        sub.set(k, v)
    for para in cell.paras:
        _write_paragraph(sub, para, state)
    ca = etree.SubElement(tc, _hp("cellAddr"))
    ca.set("colAddr", str(cell.col_addr))
    ca.set("rowAddr", str(cell.row_addr))
    cspan = etree.SubElement(tc, _hp("cellSpan"))
    cspan.set("colSpan", str(cell.col_span))
    cspan.set("rowSpan", str(cell.row_span))
    csz = etree.SubElement(tc, _hp("cellSz"))
    csz.set("width", str(cell.width))
    csz.set("height", str(cell.height))
    cm = etree.SubElement(tc, _hp("cellMargin"))
    for side in ("left", "right", "top", "bottom"):
        cm.set(side, "141")


def section_xml(section):
    root = etree.Element(_hs("sec"), nsmap=_NSMAP)
    state = {"tbl_id": 0, "para_id": 0}
    for para in section.paras:
        _write_paragraph(root, para, state)
    return XML_DECL + etree.tostring(root, encoding="UTF-8")
