import glob
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]
S4_REF = glob.glob("samples/4.*.hwpx")[0]
S3_REF = glob.glob("samples/3.*.hwpx")[0]


def _section(hwp, tmp_path):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return unzip_parts(str(out))["Contents/section0.xml"]


def test_sample4_no_missing_runs(tmp_path):
    ours = _section(S4, tmp_path)
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    assert score_part(ours, theirs)["missing"].get("run", 0) == 0


def test_sample4_known_paragraph_gains_trailing_empty_run(tmp_path):
    # A known paragraph's text run is immediately followed by a bare
    # <hp:run charPrIDRef="34"/>: the paragraph-break's char shape differs
    # from its last content run, so it gets its own trailing empty run.
    xml = _section(S4, tmp_path).decode("utf-8")
    assert '</hp:run><hp:run charPrIDRef="34"/>' in xml


def test_sample4_section_match_rises(tmp_path):
    ours = _section(S4, tmp_path)
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    assert score_part(ours, theirs)["match"] > 0.996


def test_sample3_no_missing_runs_and_match_rises(tmp_path):
    ours = _section(S3, tmp_path)
    theirs = unzip_parts(S3_REF)["Contents/section0.xml"]
    s = score_part(ours, theirs)
    assert s["missing"].get("run", 0) == 0
    # Captured live from the implemented pipeline: match == 0.9936923076923077
    # (rounds to 0.9937 at 4dp, hence the brief's headline number). Threshold
    # set just below the exact float so the "rises from 0.9932" regression
    # guard doesn't flake on rounding.
    assert s["match"] > 0.9936
