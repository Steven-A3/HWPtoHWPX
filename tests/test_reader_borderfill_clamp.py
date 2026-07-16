"""Out-of-range borderfill-id refs must clamp into [0, len(border_fills)-1]
rather than dangling past the last defined BorderFill."""
from hwp2hwpx.hwpmodel.reader import read_document

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


def _table():
    doc = read_document(_XML.encode("utf-8"))
    para = doc.sections[0].paragraphs[0]
    return next(r.table for r in para.runs if r.table is not None)


def test_out_of_range_table_borderfill_id_clamps_into_range():
    # 2 BorderFill defs -> valid ids are 0..1. A raw ref of 9999 must not
    # dangle; it clamps to the last valid index (1), not 9998.
    table = _table()
    assert table.border_fill_id == 1


def test_out_of_range_cell_borderfill_id_clamps_into_range():
    table = _table()
    cell = table.table_rows[0].cells[0]
    assert cell.border_fill_id == 1


def test_in_range_shift_still_correct():
    # Regression guard: the existing 1-based -> 0-based shift for in-range
    # ids must be untouched by the clamp (raw 2 -> 1, still within [0, 1]).
    doc = read_document(_XML.encode("utf-8"))
    di_xml = _XML.replace('borderfill-id="9999"', 'borderfill-id="2"')
    doc2 = read_document(di_xml.encode("utf-8"))
    para = doc2.sections[0].paragraphs[0]
    table = next(r.table for r in para.runs if r.table is not None)
    assert table.border_fill_id == 1
    assert table.table_rows[0].cells[0].border_fill_id == 1
