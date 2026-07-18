from hwp2hwpx.owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Metadata,
    BorderFill, Border, Table, TableRow, Tc, Rect, DrawText, SubList, Container,
    CharPr, ParaPr, SecPr, PageBorderFill,
)
from hwp2hwpx.mapper.borderfill_null import (
    normalize_borderfill_null, _is_canonical_null, _canonical_null,
)


def _null_bf(id=1):
    return BorderFill(id=id, borders=[
        Border(kind="left", type="NONE", width="0.1 mm", color="#000000"),
        Border(kind="right", type="NONE", width="0.1 mm", color="#000000"),
        Border(kind="top", type="NONE", width="0.1 mm", color="#000000"),
        Border(kind="bottom", type="NONE", width="0.1 mm", color="#000000"),
        Border(kind="diagonal", type="SOLID", width="0.1 mm", color="#000000"),
    ], fill_color=None, gradation=None)


def _null_but_filled(id=1):
    bf = _null_bf(id)
    bf.fill_color = "#FF0000"
    return bf


def test_is_canonical_null_true():
    assert _is_canonical_null(_null_bf()) is True


def test_is_canonical_null_false_when_filled():
    assert _is_canonical_null(_null_but_filled()) is False


def test_is_canonical_null_false_when_side_border_present():
    bf = _null_bf()
    bf.borders[0].type = "SOLID"   # left border now visible
    assert _is_canonical_null(bf) is False


def test_canonical_null_matches_detector():
    assert _is_canonical_null(_canonical_null()) is True


def _doc(first_bf):
    # header: 2 borderFills; a charPr ref=1, a paraPr ref=2
    header = Header(
        border_fills=[first_bf, _null_bf(id=2)],
        char_prs=[CharPr(id=0, border_fill_id=1)],
        para_prs=[ParaPr(id=0, border_fill_id=2)],
    )
    # a top-level table (ref=1) whose cell (ref=2) holds a nested table (ref=1)
    nested_tbl = Table(border_fill_id=1, rows=[TableRow(cells=[Tc(border_fill_id=2)])])
    nested_para = Para(id=1, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[nested_tbl])])
    cell = Tc(border_fill_id=2, paras=[nested_para])
    tbl = Table(border_fill_id=1, rows=[TableRow(cells=[cell])])
    # a drawing text-box (Rect) whose nested para has a run with a table (ref=1)
    box_tbl = Table(border_fill_id=1, rows=[TableRow(cells=[Tc(border_fill_id=2)])])
    box_para = Para(id=2, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[box_tbl])])
    rect = Rect(draw_text=DrawText(sub_list=SubList(paras=[box_para])))
    # a Container whose child text-box Rect has a nested table (ref=1)
    con_tbl = Table(border_fill_id=1, rows=[TableRow(cells=[Tc(border_fill_id=2)])])
    con_para = Para(id=3, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[con_tbl])])
    con_rect = Rect(draw_text=DrawText(sub_list=SubList(paras=[con_para])))
    container = Container(children=[con_rect])
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[tbl, rect, container])])
    sec = Section(paras=[para],
                  sec_pr=SecPr(page_border_fills=[PageBorderFill(border_fill_id=1)]))
    return OwpmlDocument(header=header, sections=[sec], metadata=Metadata(title="t"))


def _all_refs(doc):
    refs = [cp.border_fill_id for cp in doc.header.char_prs]
    refs += [pp.border_fill_id for pp in doc.header.para_prs]
    for sec in doc.sections:
        refs += [p.border_fill_id for p in sec.sec_pr.page_border_fills]
    def visit(item):
        if isinstance(item, Table):
            refs.append(item.border_fill_id)
            for row in item.rows:
                for c in row.cells:
                    refs.append(c.border_fill_id)
                    walk(c.paras)
        elif isinstance(item, Rect) and item.draw_text and item.draw_text.sub_list:
            walk(item.draw_text.sub_list.paras)
        elif isinstance(item, Container):
            for child in item.children:
                visit(child)

    def walk(paras):
        for para in paras:
            for run in para.runs:
                for item in run.texts:
                    visit(item)
    for sec in doc.sections:
        walk(sec.paras)
    return refs


def test_noop_when_first_is_canonical():
    doc = _doc(_null_bf(id=1))
    before_count = len(doc.header.border_fills)
    before_refs = _all_refs(doc)
    normalize_borderfill_null(doc)
    assert len(doc.header.border_fills) == before_count
    assert _all_refs(doc) == before_refs


def test_insert_and_offset_when_first_not_canonical():
    doc = _doc(_null_but_filled(id=1))
    before_refs = _all_refs(doc)
    normalize_borderfill_null(doc)
    # a null was prepended and ids renumbered 1..N+1
    assert len(doc.header.border_fills) == 3
    assert _is_canonical_null(doc.header.border_fills[0])
    assert [bf.id for bf in doc.header.border_fills] == [1, 2, 3]
    # every ref shifted +1, none missed (incl. nested table/cell and drawing box)
    assert _all_refs(doc) == [r + 1 for r in before_refs]
