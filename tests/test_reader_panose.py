from hwp2hwpx.hwpmodel.reader import read_docinfo

from tests.samplepaths import fixture3

FIXTURE = fixture3()


def _fonts():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read()).fonts


def test_every_font_has_panose():
    fonts = _fonts()
    assert len(fonts) == 65
    assert all(f.panose is not None for f in fonts)


def test_panose_values_for_known_font():
    fonts = _fonts()
    # font 0 is 굴림체: Panose1 family-type=2, weight=6, x-height=1
    p = fonts[0].panose
    assert fonts[0].name == "굴림체"
    assert p.family_type == 2
    assert p.weight == 6
    assert p.x_height == 1
    assert p.stroke_variation == 1
