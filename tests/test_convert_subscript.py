import glob
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _score(prefix, part, tmp_path):
    hwp = glob.glob(prefix + "*.hwp")[0]
    ref = glob.glob(prefix + "*.hwpx")[0]
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return score_part(unzip_parts(str(out))[part], unzip_parts(ref)[part])


def test_sample3_subscript_present(tmp_path):
    s = _score("samples/3.", "Contents/header.xml", tmp_path)
    assert s["missing"].get("subscript", 0) == 0


def test_sample4_subscript_present(tmp_path):
    s = _score("samples/4.", "Contents/header.xml", tmp_path)
    assert s["missing"].get("subscript", 0) == 0


def test_sample3_header_match_rises(tmp_path):
    s = _score("samples/3.", "Contents/header.xml", tmp_path)
    assert s["match"] > 0.9987


def test_sample3_section_unchanged_by_subscript(tmp_path):
    # subscript is header-only; section0 must have no missing subscript and
    # remain at its pre-milestone match (>= 0.9994).
    s = _score("samples/3.", "Contents/section0.xml", tmp_path)
    assert s["match"] > 0.9993
