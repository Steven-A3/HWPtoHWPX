from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _doc():
    with open(FIXTURE, "rb") as f:
        return read_document(f.read())


def _tables(doc):
    return [r.table for s in doc.sections for p in s.paragraphs
            for r in p.runs if r.table is not None]


def test_body_still_has_220_paragraphs():
    doc = _doc()
    assert len(doc.sections[0].paragraphs) == 220


def test_thirty_three_tables_in_body():
    doc = _doc()
    assert len(_tables(_doc())) == 33


def test_table_has_rows_cells_and_cell_text():
    tables = _tables(_doc())
    t = tables[0]
    assert len(t.table_rows) >= 1
    cell = t.table_rows[0].cells[0]
    assert cell.border_fill_id > 0
    # a cell somewhere in the first table has real paragraph text
    text = "".join(r.text for row in t.table_rows for c in row.cells
                   for para in c.paragraphs for r in para.runs)
    assert text.strip() != ""


def test_merged_cell_span_detected():
    tables = _tables(_doc())
    spans = [(c.col_span, c.row_span) for t in tables
             for row in t.table_rows for c in row.cells]
    assert any(cs > 1 or rs > 1 for cs, rs in spans)
