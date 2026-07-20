import os
import re
import subprocess

import pytest

# samples/ is private and git-ignored, so no committed file may name a sample.
# Match a samples/ path written as a quoted string literal, rather than any
# bare mention of the word "samples/" (which also appears in ordinary prose,
# e.g. doc comments describing where a derived artifact lives). Requiring a
# quote immediately before "samples/" and another right after the extension
# means the body between them can allow whitespace -- half of the real
# sample filenames contain a space (e.g. "20131106 ETRI ...") -- while still
# stopping at the string's own boundary. '*' stays excluded from the body so
# a prefix glob like "samples/%s*.hwp" % prefix is not mistaken for a literal
# filename: every legitimate glob reference contains one.
_LITERAL_SAMPLE = re.compile(r"""['"]samples/[^'"*]*\.hwpx?(?=['"])""")

# samples/test_document.hwp(x) is the one sample this project commits (task 2):
# a document authored for this project with no confidential content. tests/
# samplepaths.py names it literally by design (TEST_DOC/TEST_DOC_REF), so it
# must not trip a gate meant to catch the private corpus.
_PUBLIC_FIXTURE = {"samples/test_document.hwp", "samples/test_document.hwpx"}


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git_ls_files(pattern):
    # test_fresh_clone.py exercises the suite from a plain directory copy
    # (deliberately excluding .git, for speed and to avoid nesting a repo),
    # so `git ls-files` has nothing to query there. Skip only that specific,
    # intended case -- no .git directory at the repo root -- by checking for
    # it directly rather than treating any nonzero exit as "not a checkout".
    # A missing git binary or git's "detected dubious ownership" error (both
    # real failure modes in container CI) must raise instead of skip: this
    # gate exists because private document content once reached this public
    # repository, and a silently-disabled gate is worse than a noisy one.
    if not os.path.isdir(os.path.join(_repo_root(), ".git")):
        pytest.skip("not running inside a git checkout: no .git directory")
    result = subprocess.run(["git", "ls-files", pattern],
                            capture_output=True, text=True, check=True)
    return [p for p in result.stdout.splitlines() if p]


def _tracked_python_files():
    paths = _git_ls_files("*.py")
    # This module's own synthetic examples of the dangerous pattern (used to
    # prove the gate actually catches it) match _LITERAL_SAMPLE by design but
    # are not real sample names -- exclude this file from the scan it runs,
    # or it would flag itself.
    return [p for p in paths if os.path.basename(p) != "test_samples_privacy.py"]


def _names_a_sample(line):
    """True if `line` contains a literal samples/<file>.hwp(x) string.

    No exemption for samples/goldens/: those derived artifacts are named
    samples/goldens/<sample basename>.hwpx (see tests/test_parse_once.py), so
    a literal path into that directory always embeds a real sample basename
    -- exactly what this gate exists to catch, not wave through. The one
    legitimate mention of that directory (test_parse_once.py, built via
    os.path.join, plus a prose comment naming the pattern) is never a single
    quoted "samples/...hwp(x)" literal, so it never matches this in the
    first place -- nothing legitimate needs an exemption here.
    """
    m = _LITERAL_SAMPLE.search(line)
    return m is not None and m.group(0)[1:] not in _PUBLIC_FIXTURE


def test_no_committed_file_names_a_sample():
    offenders = []
    for path in _tracked_python_files():
        with open(path, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                if _names_a_sample(line):
                    offenders.append("%s:%d" % (path, lineno))
    assert offenders == [], (
        "committed files name private samples; use tests/samplepaths.py: %s"
        % ", ".join(offenders))


def test_gate_catches_a_quoted_sample_path_with_an_embedded_space():
    # I4: the bug this locks -- a spaced filename inside a string literal
    # used to slip past the old [^\s]* exclusion (half of the real sample
    # filenames contain a space). Constructed synthetically; a real sample
    # filename must never appear in a committed file.
    assert _names_a_sample('SAMPLE = "samples/made up report name.hwp"\n')


def test_gate_still_ignores_a_prefix_glob():
    # Regression guard: legitimate references (tests/samplepaths.py) look
    # like "samples/%s*.hwp" % prefix -- the '*' must keep this unmatched.
    assert not _names_a_sample('return _one("samples/%s*.hwp" % prefix)\n')


def test_gate_ignores_a_prose_mention_of_the_goldens_directory():
    # Regression guard for the widened body class: a doc comment describing
    # where goldens live (no quotes around the path) must not be mistaken
    # for a quoted literal.
    line = ("# Goldens live in samples/goldens/<sample-basename>.hwpx, "
            "captured from the\n")
    assert not _names_a_sample(line)


def test_gate_ignores_the_public_test_document_fixture():
    # samples/test_document.hwp(x) is the one sample committed in task 2;
    # tests/samplepaths.py names it literally (TEST_DOC/TEST_DOC_REF) by
    # design, so the gate must not flag its own sanctioned literal.
    assert not _names_a_sample('TEST_DOC = "samples/test_document.hwp"\n')
    assert not _names_a_sample('TEST_DOC_REF = "samples/test_document.hwpx"\n')


def test_gate_catches_a_literal_golden_path():
    # M2: samples/goldens/<basename>.hwpx leaks the same basename a plain
    # samples/<basename>.hwpx literal would -- a prefix exemption for
    # "samples/goldens" must not wave this through just because it starts
    # with the goldens directory name.
    assert _names_a_sample('GOLDEN = "samples/goldens/made-up-basename.hwpx"\n')


def test_public_fixture_exemption_does_not_shadow_a_private_sample():
    # The exemption must be exact-match. A prefix- or directory-shaped rule
    # would wave through any path that merely starts the same way.
    assert _names_a_sample('X = "samples/test_document_private.hwp"\n')
    assert _names_a_sample('X = "samples/test_document/real name.hwp"\n')


def test_public_fixture_is_tracked():
    # Routed through _git_ls_files (not a raw subprocess call) so this test
    # skips, rather than crashes, in test_fresh_clone.py's simulated clone,
    # which deliberately has no .git -- the same reason that helper exists.
    tracked = sorted(_git_ls_files("samples"))
    assert tracked == ["samples/test_document.hwp",
                       "samples/test_document.hwpx"], (
        "exactly the public fixture must be tracked under samples/, got: %s"
        % tracked)


def test_no_fixture_derived_from_a_sample_is_tracked():
    # tests/fixtures/ holds dumps (e.g. hwp5proc xml) of private samples --
    # generated on demand by tests/samplepaths.py, not committed. A tracked
    # file there would leak the same document content this module guards
    # against, just one step removed from samples/ itself.
    tracked = _git_ls_files("tests/fixtures")
    assert tracked == [], (
        "tests/fixtures/ must stay generated-and-ignored (derived from "
        "private samples/), but git tracks: %s" % ", ".join(tracked))
