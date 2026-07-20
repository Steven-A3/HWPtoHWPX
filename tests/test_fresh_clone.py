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


@pytest.mark.skipif(not samples_available(),
                    reason="already running without the private samples")
def test_suite_collects_and_passes_without_samples(tmp_path):
    # Run pytest in a copy of the repo that has no samples/ at all. A copy,
    # not a temporary rename: renaming the real directory would destroy the
    # private corpus if this process were interrupted mid-test.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work = str(tmp_path / "clone")
    shutil.copytree(root, work, ignore=shutil.ignore_patterns(
        "samples", ".git", ".venv", "build", "dist", "__pycache__",
        ".pytest_cache", "*.egg-info", "fixtures"))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header"],
        cwd=work, capture_output=True, text=True)
    assert "error" not in result.stdout.lower().split("warnings summary")[0], (
        "collection or run errors without samples/:\n%s" % result.stdout[-3000:])
    assert result.returncode == 0, result.stdout[-3000:]
    assert " skipped" in result.stdout, (
        "expected sample-dependent tests to skip:\n%s" % result.stdout[-2000:])
