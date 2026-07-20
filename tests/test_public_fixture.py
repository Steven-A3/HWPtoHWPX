"""End-to-end gate on the one document that can be public.

This is the only fixture CI can see: the private corpus never reaches it. The
floors below record what the converter produces *today* -- a ratchet against
regression, not a claim of correctness. Only the private samples can measure
fidelity in general.
"""
import os
import tempfile

import pytest

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.samplepaths import TEST_DOC, TEST_DOC_REF

# Measured against Hancom's export of this document. Known gaps, deliberately
# recorded at their true values rather than excluded so they stay visible:
#   header.xml   -- substFont x24, a documented non-goal (not derivable)
#   section0.xml -- one run
#   settings.xml -- emitted as a near-empty stub
_FLOORS = {
    "Contents/content.hpf": 1.0,
    "META-INF/container.xml": 1.0,
    "META-INF/manifest.xml": 1.0,
    "version.xml": 1.0,
    "Contents/section0.xml": 0.996,
    "Contents/header.xml": 0.991,
    "settings.xml": 0.10,
}


@pytest.fixture(scope="module")
def converted():
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.hwpx")
        convert(TEST_DOC, out)
        yield unzip_parts(out), unzip_parts(TEST_DOC_REF)


def test_part_set_matches_hancom(converted):
    ours, theirs = converted
    assert set(ours) == set(theirs)


@pytest.mark.parametrize("part", sorted(_FLOORS))
def test_part_meets_its_floor(converted, part):
    ours, theirs = converted
    result = score_part(ours[part], theirs[part])
    assert result["match"] >= _FLOORS[part], "%s regressed to %.4f, missing %s" % (
        part, result["match"], result["missing"])


def test_conversion_is_deterministic():
    # The floors are only meaningful if the same input yields the same output.
    with tempfile.TemporaryDirectory() as td:
        first, second = os.path.join(td, "a.hwpx"), os.path.join(td, "b.hwpx")
        convert(TEST_DOC, first)
        convert(TEST_DOC, second)
        assert open(first, "rb").read() == open(second, "rb").read()
