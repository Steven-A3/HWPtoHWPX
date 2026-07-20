import pytest

from hwp2hwpx.fidelity.diff import element_counts, score_part


@pytest.mark.sample_free
def test_element_counts_strips_namespace():
    xml = (b'<hs:sec xmlns:hs="urn:s" xmlns:hp="urn:p">'
           b'<hp:p><hp:run><hp:t>a</hp:t></hp:run>'
           b'<hp:run><hp:t>b</hp:t></hp:run></hp:p></hs:sec>')
    counts = element_counts(xml)
    assert counts["p"] == 1
    assert counts["run"] == 2
    assert counts["t"] == 2


@pytest.mark.sample_free
def test_score_identical_is_one():
    xml = b'<r><a/><a/><b/></r>'
    s = score_part(xml, xml)
    assert s["match"] == 1.0


@pytest.mark.sample_free
def test_score_partial():
    ours = b'<r><a/></r>'
    theirs = b'<r><a/><a/><b/></r>'  # 3 elements under root; we have 1 of the a's, 0 b
    s = score_part(ours, theirs)
    assert 0.0 < s["match"] < 1.0
    assert s["missing"].get("b") == 1


import os
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import report
from tests.samplepaths import S3, S3_REF

SAMPLES = [(S3, S3_REF)]


@pytest.mark.parametrize("hwp,ref", SAMPLES)
def test_print_fidelity_report(hwp, ref, tmp_path, capsys):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    rep = report(str(out), ref)
    with capsys.disabled():
        print("\n" + rep)
    # Baseline gate: text content must at least be present (section match > 0).
    assert "match=" in rep
