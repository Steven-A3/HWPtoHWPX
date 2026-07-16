from hwp2hwpx.hwpmodel.reader import read_docinfo, read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _bytes():
    with open(FIXTURE, "rb") as f:
        return f.read()


def test_styles_parsed():
    di = read_docinfo(_bytes())
    assert len(di.styles) == 63
    s0 = di.styles[0]
    assert s0.local_name == "바탕글"
    assert s0.eng_name == "Normal"
    assert s0.char_shape_id == 17
    assert s0.para_shape_id == 3
    assert s0.kind == "paragraph"


def test_style_refs_in_range():
    di = read_docinfo(_bytes())
    n_char = len(di.char_shapes)
    n_para = len(di.para_shapes)
    n_style = len(di.styles)
    for s in di.styles:
        assert 0 <= s.char_shape_id < n_char
        assert 0 <= s.para_shape_id < n_para
        assert 0 <= s.next_style_id < n_style


def test_paragraph_style_ids_in_range():
    doc = read_document(_bytes())
    n_style = len(doc.docinfo.styles)
    seen = []
    for sec in doc.sections:
        for p in sec.paragraphs:
            assert 0 <= p.style_id < n_style
            seen.append(p.style_id)
    # real (non-placeholder) style ids flow through: not everything is 0
    assert any(sid != 0 for sid in seen)
