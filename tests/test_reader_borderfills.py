from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _docinfo():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read())


def test_border_fills_count_and_shape():
    di = _docinfo()
    assert len(di.border_fills) == 52
    bf = di.border_fills[0]
    kinds = [b.kind for b in bf.borders]
    assert kinds == ["left", "right", "top", "bottom", "diagonal"]


def test_some_borderfill_has_solid_border():
    di = _docinfo()
    assert any(any(b.stroke_type == "solid" for b in bf.borders)
               for bf in di.border_fills)


def test_some_borderfill_has_fill_color():
    di = _docinfo()
    assert any(bf.fill_color for bf in di.border_fills)
