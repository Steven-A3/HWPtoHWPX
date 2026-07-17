from lxml import etree
from hwp2hwpx.hwpmodel.reader import parse_paragraph


def _para(inner):
    xml = ('<Paragraph parashape-id="0" style-id="0"><LineSeg>%s</LineSeg>'
           '</Paragraph>' % inner)
    return parse_paragraph(etree.fromstring(xml))


def test_trailing_empty_run_appended_when_mark_shape_differs():
    p = _para('<Text charshape-id="40">제안요청서</Text>'
              '<ControlChar name="PARAGRAPH_BREAK" charshape-id="34" code="13" kind="CHAR"/>')
    assert len(p.runs) == 2
    assert p.runs[0].char_shape_id == 40 and p.runs[0].contents == ['제안요청서']
    assert p.runs[1].char_shape_id == 34 and p.runs[1].contents == []


def test_no_trailing_run_when_mark_shape_same():
    p = _para('<Text charshape-id="40">abc</Text>'
              '<ControlChar name="PARAGRAPH_BREAK" charshape-id="40" code="13" kind="CHAR"/>')
    assert len(p.runs) == 1
    assert p.runs[0].contents == ['abc']


def test_no_trailing_run_when_break_has_no_charshape():
    p = _para('<Text charshape-id="40">abc</Text>'
              '<ControlChar name="PARAGRAPH_BREAK" code="13" kind="CHAR"/>')
    assert len(p.runs) == 1


def test_no_trailing_run_for_table_terminated_paragraph():
    # a paragraph whose only run is a table run has no contents-bearing run;
    # last_cs is None, so no trailing empty run even if a break shape exists.
    inner = ('<TableControl charshape-id="7"><TableBody rows="1" cols="1" '
             'borderfill-id="1"><TableRow><TableCell col="0" row="0" '
             'colspan="1" rowspan="1" width="100" height="100" borderfill-id="1">'
             '</TableCell></TableRow></TableBody></TableControl>'
             '<ControlChar name="PARAGRAPH_BREAK" charshape-id="34" code="13" kind="CHAR"/>')
    p = _para(inner)
    assert all(r.contents == [] for r in p.runs)
    # exactly the table run, no appended empty text run
    assert len(p.runs) == 1
