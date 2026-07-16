from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _paras():
    with open(FIXTURE, "rb") as f:
        doc = read_document(f.read())
    # include cell paragraphs
    out = []

    def walk(paras):
        for p in paras:
            out.append(p)
            for r in p.runs:
                if r.table is not None:
                    for row in r.table.table_rows:
                        for cell in row.cells:
                            walk(cell.paragraphs)
    for sec in doc.sections:
        walk(sec.paragraphs)
    return out


def test_every_paragraph_has_line_segs():
    paras = _paras()
    assert len(paras) == 749
    assert all(len(p.line_segs) >= 1 for p in paras)
    assert sum(len(p.line_segs) for p in paras) == 922


def test_lineseg_flags_hex_to_decimal():
    # first paragraph, first line seg: lineseg-flags="00060000" -> 393216
    paras = _paras()
    first = paras[0].line_segs[0]
    assert first.flags == int("00060000", 16) == 393216


def test_lineseg_geometry_fields_are_ints():
    ls = _paras()[0].line_segs[0]
    for v in (ls.text_pos, ls.vert_pos, ls.vert_size, ls.text_height,
              ls.baseline, ls.spacing, ls.horz_pos, ls.horz_size):
        assert isinstance(v, int)
