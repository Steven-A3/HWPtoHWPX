import glob

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]
S3_REF = glob.glob("samples/3.*.hwpx")[0]
S4_REF = glob.glob("samples/4.*.hwpx")[0]


def _section(hwp, tmp_path):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return unzip_parts(str(out))["Contents/section0.xml"]


def test_sample3_no_missing_t_and_match_rises(tmp_path):
    ours = _section(S3, tmp_path)
    theirs = unzip_parts(S3_REF)["Contents/section0.xml"]
    s = score_part(ours, theirs)
    assert s["missing"].get("t", 0) == 0
    assert s["match"] > 0.998


def test_sample4_no_missing_t_and_match_rises(tmp_path):
    ours = _section(S4, tmp_path)
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    s = score_part(ours, theirs)
    assert s["missing"].get("t", 0) == 0
    assert s["match"] > 0.999


def test_sample4_inline_pic_run_has_trailing_empty_t(tmp_path):
    # each inline <hp:pic> run ends with a bare <hp:t/> anchor.
    xml = _section(S4, tmp_path).decode("utf-8")
    assert "</hp:pic><hp:t/></hp:run>" in xml
