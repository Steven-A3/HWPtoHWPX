"""Table/cell borderfill-id refs are raw (1-based) and clamped into [1, N]."""
from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _tables():
    with open(FIXTURE, "rb") as f:
        doc = read_document(f.read())
    return [r.table for s in doc.sections for p in s.paragraphs
            for r in p.runs if r.table is not None]


def test_refs_are_raw_1_based_in_range():
    # every cell border_fill_id is within the defined 1..52 range (no dangling, no -1 shift)
    ids = [c.border_fill_id for t in _tables() for row in t.table_rows for c in row.cells]
    assert ids
    assert all(1 <= i <= 52 for i in ids)


def test_first_table_cell_ref_matches_hwp_raw():
    # first table's body borderfill-id is 4 in the fixture (raw, unshifted)
    assert _tables()[0].border_fill_id == 4
