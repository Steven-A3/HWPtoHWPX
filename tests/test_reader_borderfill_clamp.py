"""Table/cell borderfill-id refs are raw (1-based) and clamped into [1, N]."""
from hwp2hwpx.hwpmodel.reader import read_document

from tests.samplepaths import fixture3

FIXTURE = fixture3()

# Synthetic doc: 2 BorderFill defs -> valid ids are [1, 2]. Exercises the
# clamp's out-of-range branches directly (the real fixture's raw ids never
# exceed its BorderFill count, so it can't exercise the `n > count` branch).
_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HWPML>
  <DocInfo>
    <IdMappings>
      <BorderFill id="1">
        <Border attribute-name="left" stroke-type="solid" width="0.1mm" color="#000000"/>
      </BorderFill>
      <BorderFill id="2">
        <Border attribute-name="left" stroke-type="solid" width="0.1mm" color="#000000"/>
      </BorderFill>
      <ParaShape align="left" borderfill-id="1"/>
      <ParaShape align="left" borderfill-id="9999"/>
      <ParaShape align="left" borderfill-id="0"/>
    </IdMappings>
  </DocInfo>
  <BodyText>
    <SectionDef>
      <ColumnSet>
        <Paragraph style-id="0" parashape-id="0" paragraph-id="0">
          <LineSeg>
            <TableControl>
              <TableBody borderfill-id="9999" cellspacing="0" cols="1" rows="1">
                <TableRow>
                  <TableCell borderfill-id="9999" col="0" row="0" colspan="1"
                             rowspan="1" width="10" height="10" valign="middle"/>
                </TableRow>
              </TableBody>
            </TableControl>
          </LineSeg>
        </Paragraph>
      </ColumnSet>
    </SectionDef>
  </BodyText>
</HWPML>
"""


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


def _synthetic_doc():
    return read_document(_XML.encode("utf-8"))


def _synthetic_table():
    doc = _synthetic_doc()
    para = doc.sections[0].paragraphs[0]
    return next(r.table for r in para.runs if r.table is not None)


def test_out_of_range_table_borderfill_id_clamps_to_count():
    # 2 BorderFill defs -> valid ids are 1..2. A raw ref of 9999 must not
    # dangle; it clamps to the last valid id (2), not 9998.
    assert _synthetic_table().border_fill_id == 2


def test_out_of_range_cell_borderfill_id_clamps_to_count():
    cell = _synthetic_table().table_rows[0].cells[0]
    assert cell.border_fill_id == 2


def test_out_of_range_para_shape_borderfill_id_clamps_to_count():
    # ParaShape borderFillIDRef must resolve to a defined BorderFill too;
    # a raw id past the last definition (9999) clamps down to count (2).
    ps = _synthetic_doc().docinfo.para_shapes
    assert ps[1].border_fill_id == 2


def test_below_range_para_shape_borderfill_id_clamps_to_1():
    ps = _synthetic_doc().docinfo.para_shapes
    assert ps[2].border_fill_id == 1


def test_in_range_para_shape_borderfill_id_is_unchanged():
    ps = _synthetic_doc().docinfo.para_shapes
    assert ps[0].border_fill_id == 1
