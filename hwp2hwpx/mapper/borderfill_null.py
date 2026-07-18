"""Reproduce Hancom's reserved canonical-null borderFill at id=1.

Hancom guarantees the borderFill at id=1 is a canonical null (all side borders
NONE, a SOLID diagonal, no fill). When a document's first source borderFill is
not that, Hancom prepends the null and shifts every borderFillIDRef +1. This
pass reproduces that transform; documents whose first fill is already the
canonical null are left untouched.
"""
from ..owpml.model import BorderFill, Border, Table, Rect, Container


def _canonical_null():
    return BorderFill(
        id=1,
        borders=[
            Border(kind="left", type="NONE", width="0.1 mm", color="#000000"),
            Border(kind="right", type="NONE", width="0.1 mm", color="#000000"),
            Border(kind="top", type="NONE", width="0.1 mm", color="#000000"),
            Border(kind="bottom", type="NONE", width="0.1 mm", color="#000000"),
            Border(kind="diagonal", type="SOLID", width="0.1 mm", color="#000000"),
        ],
        fill_color=None,
        gradation=None,
    )


def _is_canonical_null(bf):
    by_kind = {b.kind: b for b in bf.borders}
    sides_none = all(by_kind.get(k) is not None and by_kind[k].type == "NONE"
                     for k in ("left", "right", "top", "bottom"))
    diag = by_kind.get("diagonal")
    diag_ok = (diag is not None and diag.type == "SOLID"
               and diag.width == "0.1 mm" and diag.color == "#000000")
    no_fill = (not bf.fill_color) and bf.gradation is None
    return sides_none and diag_ok and no_fill


def _offset_paras(paras, delta):
    for para in paras:
        for run in para.runs:
            for item in run.texts:
                _offset_item(item, delta)


def _offset_item(item, delta):
    if isinstance(item, Table):
        item.border_fill_id += delta
        for row in item.rows:
            for cell in row.cells:
                cell.border_fill_id += delta
                _offset_paras(cell.paras, delta)
    elif isinstance(item, Rect):
        if item.draw_text is not None and item.draw_text.sub_list is not None:
            _offset_paras(item.draw_text.sub_list.paras, delta)
    elif isinstance(item, Container):
        for child in item.children:
            _offset_item(child, delta)


def normalize_borderfill_null(doc):
    bfs = doc.header.border_fills
    if not bfs or _is_canonical_null(bfs[0]):
        return doc
    delta = 1
    doc.header.border_fills = [_canonical_null()] + list(bfs)
    for i, bf in enumerate(doc.header.border_fills):
        bf.id = i + 1
    for cp in doc.header.char_prs:
        cp.border_fill_id += delta
    for pp in doc.header.para_prs:
        pp.border_fill_id += delta
    for sec in doc.sections:
        if sec.sec_pr is not None:
            for pbf in sec.sec_pr.page_border_fills:
                pbf.border_fill_id += delta
        _offset_paras(sec.paras, delta)
    return doc
