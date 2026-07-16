"""Map HWP tables to OWPML tables. Cell paragraphs reuse map_paragraph."""
from ..hwpmodel.model import HwpParagraph
from ..owpml.model import Table, TableRow, Tc
from .body import map_paragraph

_VALIGN = {"middle": "CENTER", "center": "CENTER", "top": "TOP", "bottom": "BOTTOM"}


def _map_cell_paras(paragraphs):
    if not paragraphs:
        # HWPX requires at least one hp:p per subList; an emptied-out cell
        # (e.g. a cleared table cell) still needs one placeholder paragraph
        # with one empty hp:run, mirroring the body-paragraph guard.
        return [map_paragraph(HwpParagraph(para_shape_id=0), 0)]
    return [map_paragraph(p, i) for i, p in enumerate(paragraphs)]


def map_table(hwp_table):
    rows = []
    for hrow in hwp_table.table_rows:
        cells = []
        for c in hrow.cells:
            cells.append(Tc(
                col_addr=c.col,
                row_addr=c.row,
                col_span=c.col_span,
                row_span=c.row_span,
                width=c.width,
                height=c.height,
                border_fill_id=c.border_fill_id,
                valign=_VALIGN.get((c.valign or "").lower(), "CENTER"),
                paras=_map_cell_paras(c.paragraphs),
            ))
        rows.append(TableRow(cells=cells))
    return Table(
        id=0,
        row_cnt=hwp_table.rows,
        col_cnt=hwp_table.cols,
        cell_spacing=hwp_table.cell_spacing,
        border_fill_id=hwp_table.border_fill_id,
        width=hwp_table.width,
        height=hwp_table.height,
        rows=rows,
    )
