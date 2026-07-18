from hwp2hwpx.hwpmodel.model import (
    HwpBorder, HwpBorderFill, HwpTableCell, HwpTableRow, HwpTable,
    HwpRun, HwpParagraph, HwpDocInfo,
)


def test_border_and_borderfill():
    bf = HwpBorderFill(index=3, borders=[HwpBorder(kind="left", stroke_type="solid",
                                                   width="0.4mm", color="#000000")],
                       fill_color="#bbbbbb")
    assert bf.index == 3
    assert bf.borders[0].kind == "left"
    assert bf.fill_color == "#bbbbbb"


def test_table_structure_and_run_table():
    cell = HwpTableCell(col=1, row=0, col_span=2, row_span=1, width=100, height=50,
                        border_fill_id=5, valign="middle",
                        paragraphs=[HwpParagraph(para_shape_id=0)])
    table = HwpTable(rows=1, cols=3, cell_spacing=0, border_fill_id=4,
                     width=300, height=50, table_rows=[HwpTableRow(cells=[cell])])
    run = HwpRun(char_shape_id=0, contents=[table])
    assert run.table.table_rows[0].cells[0].col_span == 2
    assert HwpRun(char_shape_id=0, contents=["x"]).table is None


def test_docinfo_border_fills_default_empty():
    assert HwpDocInfo().border_fills == []
