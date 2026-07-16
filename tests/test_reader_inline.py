from hwp2hwpx.hwpmodel.reader import read_document
from hwp2hwpx.hwpmodel.model import HwpControl

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _walk(paragraphs):
    """Yield paragraphs recursively, descending into table cells too, since
    control chars (e.g. LINE_BREAK) in this fixture live inside table cells."""
    for p in paragraphs:
        yield p
        for r in p.runs:
            if r.table is not None:
                for row in r.table.table_rows:
                    for cell in row.cells:
                        yield from _walk(cell.paragraphs)


def _paras():
    with open(FIXTURE, "rb") as f:
        doc = read_document(f.read())
    return [p for sec in doc.sections for p in _walk(sec.paragraphs)]


def test_fwspace_and_linebreak_present_in_contents():
    paras = _paras()
    kinds = set()
    for p in paras:
        for r in p.runs:
            for item in r.contents:
                if isinstance(item, HwpControl):
                    kinds.add(item.kind)
    assert "fwSpace" in kinds
    assert "lineBreak" in kinds


def test_same_charshape_text_and_control_merge_into_one_run():
    # find a run that contains both a text string and a control marker
    paras = _paras()
    mixed = [r for p in paras for r in p.runs
             if any(isinstance(i, HwpControl) for i in r.contents)
             and any(isinstance(i, str) for i in r.contents)]
    assert mixed, "expected at least one run mixing text and a control"


def test_paragraph_break_is_dropped():
    # PARAGRAPH_BREAK must never appear as a control kind
    paras = _paras()
    for p in paras:
        for r in p.runs:
            for item in r.contents:
                if isinstance(item, HwpControl):
                    assert item.kind in ("fwSpace", "lineBreak")


def test_merged_run_count_below_old_one_per_text():
    # merging collapses runs: total run count is well under the old ~1600
    paras = _paras()
    total_runs = sum(len(p.runs) for p in paras)
    assert total_runs < 1200
