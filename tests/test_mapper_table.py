from hwp2hwpx.mapper.table import map_table
from hwp2hwpx.mapper.body import map_document, map_paragraph
from hwp2hwpx.hwpmodel.model import (
    HwpTable, HwpTableRow, HwpTableCell, HwpParagraph, HwpRun,
    HwpDocument, HwpDocInfo, HwpBorderFill, HwpBorder, HwpSection,
)


def _table():
    cell = HwpTableCell(col=0, row=0, col_span=2, row_span=1, width=100, height=50,
                        border_fill_id=5, valign="middle",
                        paragraphs=[HwpParagraph(para_shape_id=0,
                                                 runs=[HwpRun(char_shape_id=3, text="가")])])
    return HwpTable(rows=1, cols=2, cell_spacing=0, border_fill_id=4,
                    width=100, height=50, table_rows=[HwpTableRow(cells=[cell])])


def test_map_table_structure():
    t = map_table(_table())
    assert t.row_cnt == 1 and t.col_cnt == 2 and t.border_fill_id == 4
    tc = t.rows[0].cells[0]
    assert (tc.col_addr, tc.row_addr) == (0, 0)
    assert (tc.col_span, tc.row_span) == (2, 1)
    assert tc.valign == "CENTER"
    assert tc.paras[0].runs[0].texts[0].content == "가"


def test_map_paragraph_with_table_run():
    hpar = HwpParagraph(para_shape_id=0, runs=[HwpRun(char_shape_id=0, table=_table())])
    para = map_paragraph(hpar, 7)
    assert para.id == 7
    assert para.runs[0].table is not None
    assert para.runs[0].table.col_cnt == 2


def test_empty_cell_gets_placeholder_paragraph():
    cell = HwpTableCell(col=0, row=0, col_span=1, row_span=1, width=10, height=10,
                        border_fill_id=0, valign="middle", paragraphs=[])
    table = HwpTable(rows=1, cols=1, cell_spacing=0, border_fill_id=0,
                     width=10, height=10, table_rows=[HwpTableRow(cells=[cell])])
    t = map_table(table)
    tc = t.rows[0].cells[0]
    assert len(tc.paras) == 1
    assert len(tc.paras[0].runs) == 1


def test_map_document_wires_border_fills():
    di = HwpDocInfo(border_fills=[HwpBorderFill(index=0, borders=[
        HwpBorder(kind="left", stroke_type="solid", width="0.4mm", color="#000000")])])
    doc = map_document(HwpDocument(docinfo=di, sections=[HwpSection(paragraphs=[])]))
    assert len(doc.header.border_fills) == 1
    assert doc.header.border_fills[0].borders[0].type == "SOLID"
