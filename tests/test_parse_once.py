import glob
import os
import subprocess
import tempfile

import pytest

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

SAMPLES = ["samples/3.", "samples/4.", "samples/★131008", "samples/20131106"]

# Goldens are *.golden.hwpx beside each sample, captured from the converter as of
# f114e7b (the commit before the parse-once refactor). They are derived artifacts
# living under the git-ignored samples/, so a fresh checkout has none and this
# gate skips rather than failing on a missing input. To recreate them, run
# convert() from a worktree at f114e7b over each sample, writing
# <sample-basename>.golden.hwpx.


@pytest.mark.parametrize("pre", SAMPLES)
def test_convert_spawns_no_subprocess(pre, monkeypatch):
    hwp = glob.glob(pre + "*.hwp")[0]
    def boom(*a, **k):
        raise AssertionError("subprocess spawned: %r" % (a[0] if a else k))
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "check_output", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    with tempfile.TemporaryDirectory() as td:
        convert(hwp, os.path.join(td, "o.hwpx"))  # must succeed with no spawns


@pytest.mark.parametrize("pre", SAMPLES)
def test_output_matches_golden(pre):
    hwp = glob.glob(pre + "*.hwp")[0]
    golden = glob.glob(pre + "*.golden.hwpx")
    if not golden:
        pytest.skip("no pre-refactor golden captured for this sample")
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "o.hwpx")
        convert(hwp, out)
        got = unzip_parts(out)
    want = unzip_parts(golden[0])
    assert set(got) == set(want)
    for part in want:
        assert got[part] == want[part], part
