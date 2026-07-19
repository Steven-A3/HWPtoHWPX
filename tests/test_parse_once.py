import gc
import glob
import os
import subprocess
import tempfile
from collections import Counter

import pytest
from hwp5.binmodel import ModelStream
from hwp5.xmlmodel import XmlEventsMixin

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

SAMPLES = ["samples/3.", "samples/4.", "samples/★131008", "samples/20131106"]


class _SubprocessSpawned(BaseException):
    """Not an Exception: a bare `except Exception:` (the fail-safe pattern
    used by rangetags.py and HwpSource._read_stream) must not be able to
    swallow this sentinel and silently degrade a reintroduced subprocess
    spawn into an empty/None result while this gate keeps passing."""

# Goldens live in samples/goldens/<sample-basename>.hwpx, captured from the
# converter as of f114e7b (the commit before the parse-once refactor). They must
# stay out of samples/ itself: the fidelity tests locate Hancom's reference via
# globs like samples/3.*.hwpx, and a golden sitting there can win the glob and
# make those tests compare our output against itself. They are derived artifacts
# under the git-ignored samples/, so a fresh checkout has none and this gate
# skips rather than failing on a missing input. To recreate them, run convert()
# from a worktree at f114e7b over each sample into samples/goldens/.


@pytest.mark.parametrize("pre", SAMPLES)
def test_convert_spawns_no_subprocess(pre, monkeypatch):
    hwp = glob.glob(pre + "*.hwp")[0]
    def boom(*a, **k):
        raise _SubprocessSpawned("subprocess spawned: %r" % (a[0] if a else k))
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "check_output", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "call", boom)
    monkeypatch.setattr(subprocess, "check_call", boom)
    with tempfile.TemporaryDirectory() as td:
        convert(hwp, os.path.join(td, "o.hwpx"))  # must succeed with no spawns


@pytest.mark.parametrize("pre", SAMPLES)
def test_output_matches_golden(pre):
    hwp = glob.glob(pre + "*.hwp")[0]
    golden = glob.glob(os.path.join(
        "samples/goldens", os.path.basename(os.path.splitext(hwp)[0]) + ".hwpx"))
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


@pytest.mark.parametrize("pre", SAMPLES)
def test_convert_shares_the_model_walk_per_stream(pre, monkeypatch):
    """The parse-once gate the design spec called for (V3): patch pyhwp's own
    per-stream `models()` and `xmlevents()`, not HwpSource's wrapper methods,
    so a consumer that bypasses HwpSource's cache (as rangetags.py used to,
    I1) is caught.

    Two `models()` calls per stream (DocInfo, and each BodyText/SectionN) is
    the true floor here, not one: `Hwp5File.xmlevents()`'s XML-event dump
    independently walks `docinfo.events()`/`section.events()` (which call
    `.models()` internally) to build the XML tree, while
    `HwpSource.docinfo_models()`/`section_models()` separately provide the
    raw model dicts (`content` + `payload`) that hwp5_char_shapes,
    hwp5_char_shape_border_fills, and rangetags need. Those are genuinely
    different pyhwp objects/codepaths -- HwpSource's memoization does not
    (and is not asked to) collapse them into one. What it does guarantee, and
    what this gate catches, is that among the second group of consumers a
    stream is walked only once no matter how many of them read it: before
    the I1 fix, rangetags.py re-walked `f.bodytext[name].models()` on its
    own uncached Section object, so BodyText/Section0 was parsed a third
    time (3 calls, not 2)."""
    hwp = glob.glob(pre + "*.hwp")[0]

    calls = []
    real_models = ModelStream.models
    def counting_models(self, **kwargs):
        calls.append(getattr(self, "path", type(self).__name__))
        return real_models(self, **kwargs)
    monkeypatch.setattr(ModelStream, "models", counting_models)

    xmlevents_calls = {"n": 0}
    real_xmlevents = XmlEventsMixin.xmlevents
    def counting_xmlevents(self, **kwargs):
        xmlevents_calls["n"] += 1
        return real_xmlevents(self, **kwargs)
    monkeypatch.setattr(XmlEventsMixin, "xmlevents", counting_xmlevents)

    with tempfile.TemporaryDirectory() as td:
        convert(hwp, os.path.join(td, "o.hwpx"))

    assert xmlevents_calls["n"] == 1

    counts = Counter(calls)
    assert counts["DocInfo"] == 2
    section_paths = [p for p in counts if str(p).startswith("BodyText/Section")]
    assert section_paths, "expected at least one section stream to be walked"
    for path in section_paths:
        assert counts[path] == 2, (
            "%s walked %d times -- a consumer is bypassing the shared "
            "section_models() cache" % (path, counts[path]))


def test_convert_does_not_leak_file_descriptors_across_repeated_runs():
    """`Hwp5File`'s wrapper chain holds a reference cycle (each wrapper keeps
    `self.wrapped`), so with the garbage collector off -- as a long-running
    CLI batch process might run it, for throughput -- plain refcounting never
    reclaims a dropped `HwpSource`'s OLE storage. `convert()`'s `with
    HwpSource(...)` must close the handle deterministically instead, or
    descriptor counts climb without bound across repeated conversions."""
    hwp = glob.glob("samples/3.*.hwp")[0]
    gc.disable()
    try:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "o.hwpx")
            for _ in range(3):  # warm up: absorb one-time lazy-import fds
                convert(hwp, out)
            baseline = len(os.listdir("/dev/fd"))
            for _ in range(20):
                convert(hwp, out)
            assert len(os.listdir("/dev/fd")) <= baseline
    finally:
        gc.enable()
