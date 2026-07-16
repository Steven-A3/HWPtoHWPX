from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _ps():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read()).para_shapes


def test_para_shape_count():
    assert len(_ps()) == 126


def test_para_shape_11_raw_values():
    # verified from the fixture: indent -4000, doubled margins 2000/2000/0/0,
    # linespacing 140 ratio, borderfill-id present
    s = _ps()[11]
    assert s.indent == -4000
    assert s.margin_left == 2000 and s.margin_right == 2000
    assert s.line_spacing == 140 and s.line_spacing_type == "ratio"
    assert s.border_fill_id >= 1


def test_para_shape_14_center_align_and_linespacing_180():
    s = _ps()[14]
    assert s.align == "CENTER"
    assert s.line_spacing == 180
