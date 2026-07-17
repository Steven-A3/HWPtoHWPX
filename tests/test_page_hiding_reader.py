import glob
from lxml import etree
from hwp2hwpx.hwpmodel.reader import parse_paragraph, read_document, hwp5_xml
from hwp2hwpx.mapper.body import map_paragraph


def _para(inner):
    xml = ('<Paragraph parashape-id="0" style-id="0"><LineSeg>%s</LineSeg>'
           '</Paragraph>' % inner)
    return parse_paragraph(etree.fromstring(xml))


def test_pagehide_attaches_to_following_text_run():
    p = _para('<PageHide basepage="0" header="0" footer="0" pageborder="0" '
              'pagefill="0" pagenumber="1"/>'
              '<Text charshape-id="48">hi</Text>')
    run = p.runs[0]
    assert len(run.ctrls) == 1
    assert run.ctrls[0].hide_page_num == 1
    assert run.ctrls[0].hide_header == 0


def test_two_pagehides_attach():
    p = _para('<PageHide pagenumber="1"/><PageHide pagenumber="1"/>'
              '<Text charshape-id="48">hi</Text>')
    assert len(p.runs[0].ctrls) == 2


def test_no_pagehide_means_no_ctrls():
    p = _para('<Text charshape-id="48">hi</Text>')
    assert p.runs[0].ctrls == []


def test_pagehide_marks_paragraph_markpen_unsafe():
    p = _para('<PageHide pagenumber="1"/><Text charshape-id="48">hi</Text>')
    assert p.markpen_unsafe is True


def test_mapper_maps_ctrls():
    from hwp2hwpx.hwpmodel.model import HwpRun, HwpPageHide, HwpParagraph
    hpar = HwpParagraph(para_shape_id=0,
                        runs=[HwpRun(char_shape_id=48, contents=["hi"],
                                     ctrls=[HwpPageHide(hide_page_num=1)])])
    para = map_paragraph(hpar, 0)
    assert len(para.runs[0].ctrls) == 1
    assert para.runs[0].ctrls[0].hide_page_num == 1


def test_sample3_has_two_pagehides_attached():
    from hwp2hwpx.hwpmodel.model import HwpPageHide
    doc = read_document(hwp5_xml(glob.glob("samples/3.*.hwp")[0]))
    def walk(paras):
        for p in paras:
            for run in p.runs:
                # count only PageHide ctrls -- run.ctrls also carries other
                # inline controls now (e.g. a leading newNum on a table run).
                yield sum(1 for c in run.ctrls if isinstance(c, HwpPageHide))
                if run.table is not None:
                    for row in run.table.table_rows:
                        for cell in row.cells:
                            yield from walk(cell.paragraphs)
    assert sum(walk(doc.sections[0].paragraphs)) == 2


def test_pagehide_with_no_text_becomes_ctrl_only_run():
    # A PageHide in an otherwise-empty paragraph (PageHide then paragraph break,
    # no text) must still emit: Hancom writes a ctrl-only run carrying the
    # paragraph-mark char shape. The flush()-based attach can't place it (no
    # content run), so parse_paragraph appends a dedicated ctrl-only run.
    p = _para('<PageHide pagenumber="1"/>'
              '<ControlChar name="PARAGRAPH_BREAK" charshape-id="34" code="13" kind="CHAR"/>')
    ctrl_runs = [r for r in p.runs if r.ctrls]
    assert len(ctrl_runs) == 1
    assert ctrl_runs[0].contents == []
    assert ctrl_runs[0].char_shape_id == 34
    assert ctrl_runs[0].ctrls[0].hide_page_num == 1
