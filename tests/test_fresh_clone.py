"""The suite must survive a clone that has no private samples/ directory.

CI is exactly that clone: samples/ is git-ignored private material and will
never exist there. Collection errors cannot be skipped, so a module that
resolves a sample at import time takes the whole run down.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

from tests.samplepaths import samples_available

# A real CI checkout has samples/ populated with exactly the two tracked
# public-fixture files (everything else under it is git-ignored). Blanket-
# excluding the whole "samples" directory here would under-simulate that:
# it would also hide the public fixture, which CI actually has.
_PUBLIC_FIXTURE_NAMES = {"test_document.hwp", "test_document.hwpx"}

_OTHER_IGNORED = shutil.ignore_patterns(
    ".git", ".venv", "build", "dist", "__pycache__",
    ".pytest_cache", "*.egg-info", "fixtures")


def _ignore_private_samples(dir_, names):
    if os.path.basename(dir_) == "samples":
        return [n for n in names if n not in _PUBLIC_FIXTURE_NAMES]
    return _OTHER_IGNORED(dir_, names)


@pytest.mark.skipif(not samples_available(),
                    reason="already running without the private samples")
def test_suite_collects_and_passes_without_samples(tmp_path):
    # Run pytest in a copy of the repo that has no private samples/ content.
    # A copy, not a temporary rename: renaming the real directory would
    # destroy the private corpus if this process were interrupted mid-test.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work = str(tmp_path / "clone")
    shutil.copytree(root, work, ignore=_ignore_private_samples)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header"],
        cwd=work, capture_output=True, text=True)
    assert "error" not in result.stdout.lower().split("warnings summary")[0], (
        "collection or run errors without samples/:\n%s" % result.stdout[-3000:])
    assert result.returncode == 0, result.stdout[-3000:]
    assert " skipped" in result.stdout, (
        "expected sample-dependent tests to skip:\n%s" % result.stdout[-2000:])
