from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _sec_def():
    with open(FIXTURE, "rb") as f:
        return read_document(f.read()).sections[0].sec_def


def test_section_def_attached_and_scalar_fields():
    sd = _sec_def()
    assert sd is not None
    assert sd.column_spacing == 1134
    assert sd.default_tab_stops == 8000
    assert sd.text_direction == 0
    assert sd.hide_blank_line == 0


def test_page_def_parsed():
    p = _sec_def().page
    assert p.width == 59528 and p.height == 84188
    assert p.left_offset == 7088 and p.right_offset == 7088
    assert p.top_offset == 5668 and p.bottom_offset == 4252
    assert p.header_offset == 4252 and p.footer_offset == 4252
    assert p.orientation == "portrait" and p.bookbinding == "left"


def test_footnote_and_endnote_parsed():
    sd = _sec_def()
    assert sd.footnote.stroke_type == "solid"
    assert sd.footnote.splitter_length == -1
    assert sd.footnote.line_width == "0.12mm"
    assert sd.footnote.notes_spacing == 284
    assert sd.endnote.stroke_type == "none"
    assert sd.endnote.splitter_length == 0


def test_page_borders_parsed():
    b = _sec_def().page_borders
    assert len(b) == 3
    assert b[0].borderfill_id == 1
    assert b[0].margin_left == 1417 and b[0].margin_bottom == 1417
    assert b[0].relative_to == "paper" and b[0].fill == "paper"


def test_columns_and_page_num_scoped_to_first_paragraph():
    sd = _sec_def()
    assert sd.columns.count == 1 and sd.columns.kind == "normal"
    assert sd.columns.direction == "l2r"
    assert sd.page_num.position == "bottom_center"
    assert sd.page_num.dash == "-" and sd.page_num.shape == 0
