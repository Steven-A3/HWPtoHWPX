import os
import re
import subprocess

# samples/ is private and git-ignored, so no committed file may name a sample.
# Match a samples/ path that is a literal filename rather than a prefix glob:
# every legitimate reference contains a '*'.
_LITERAL_SAMPLE = re.compile(r"samples/[^\"'*\s]*\.hwpx?")


def _tracked_python_files():
    out = subprocess.run(["git", "ls-files", "*.py"],
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p]


def test_no_committed_file_names_a_sample():
    offenders = []
    for path in _tracked_python_files():
        with open(path, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                match = _LITERAL_SAMPLE.search(line)
                if match and not match.group(0).startswith("samples/goldens"):
                    offenders.append("%s:%d" % (path, lineno))
    assert offenders == [], (
        "committed files name private samples; use tests/samplepaths.py: %s"
        % ", ".join(offenders))


def test_no_fixture_derived_from_a_sample_is_tracked():
    # tests/fixtures/ holds dumps (e.g. hwp5proc xml) of private samples --
    # generated on demand by tests/samplepaths.py, not committed. A tracked
    # file there would leak the same document content this module guards
    # against, just one step removed from samples/ itself.
    tracked = subprocess.run(["git", "ls-files", "tests/fixtures"],
                             capture_output=True, text=True, check=True).stdout
    tracked = [p for p in tracked.splitlines() if p]
    assert tracked == [], (
        "tests/fixtures/ must stay generated-and-ignored (derived from "
        "private samples/), but git tracks: %s" % ", ".join(tracked))
