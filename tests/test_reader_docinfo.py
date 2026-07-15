from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _docinfo():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read())


def test_fonts_parsed():
    di = _docinfo()
    assert len(di.fonts) == 65
    assert di.fonts[0].name == "굴림체"
    assert all(isinstance(f.name, str) and f.name for f in di.fonts)


def test_char_shapes_have_font_and_size():
    di = _docinfo()
    assert len(di.char_shapes) == 103
    cs = di.char_shapes[0]
    assert cs.base_size == 1000
    assert cs.text_color.startswith("#") and len(cs.text_color) == 7
    # CharShape[0] FontFace ko=12, ko group starts at global offset 0 -> font_id 12
    assert cs.font_id == 12
    assert 0 <= cs.font_id < len(di.fonts)


def test_para_shapes_have_align():
    di = _docinfo()
    assert len(di.para_shapes) == 126
    assert {p.align for p in di.para_shapes} <= {
        "LEFT", "CENTER", "RIGHT", "JUSTIFY", "DISTRIBUTE"}
    assert any(p.align == "CENTER" for p in di.para_shapes)
