from hwp2hwpx.owpml.model import (
    Border, BorderFill, Tc, TableRow, Table, Run, Header,
)


def test_borderfill_and_table():
    bf = BorderFill(id=5, borders=[Border(kind="left", type="SOLID",
                                          width="0.4 mm", color="#000000")],
                    fill_color="#bbbbbb")
    tc = Tc(col_addr=0, row_addr=0, col_span=2, row_span=1, width=100, height=50,
            border_fill_id=5, valign="CENTER", paras=[])
    table = Table(id=1, row_cnt=1, col_cnt=3, cell_spacing=0, border_fill_id=4,
                  width=300, height=50, rows=[TableRow(cells=[tc])])
    assert bf.borders[0].type == "SOLID"
    assert table.rows[0].cells[0].col_span == 2


def test_run_table_and_header_border_fills_defaults():
    assert Run(char_pr_id=0).table is None
    assert Header().border_fills == []
