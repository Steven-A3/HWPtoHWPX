from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _doc():
    with open(FIXTURE, "rb") as f:
        return read_document(f.read())


def test_has_one_section_with_many_paragraphs():
    doc = _doc()
    assert len(doc.sections) == 1
    # 220 direct ColumnSet>Paragraph children in this sample (table-cell paras excluded)
    assert len(doc.sections[0].paragraphs) == 220


def test_paragraphs_have_multiple_runs_and_real_text():
    doc = _doc()
    paras = doc.sections[0].paragraphs
    # at least one paragraph is split into multiple Text runs
    assert any(len(p.runs) >= 2 for p in paras)
    all_text = "".join(r.text for p in paras for r in p.runs)
    assert all_text.strip() != ""
    # runs carry a real charshape-id reference
    a_run = next(r for p in paras for r in p.runs)
    assert a_run.char_shape_id >= 0


def test_docinfo_attached():
    doc = _doc()
    assert len(doc.docinfo.fonts) == 65
