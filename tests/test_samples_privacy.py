import os
import re
import subprocess

import pytest

# samples/ is private and git-ignored, so no committed file may name a sample.
# Match a samples/ path written as a quoted string literal, rather than any
# bare mention of the word "samples/" (which also appears in ordinary prose,
# e.g. doc comments describing where a derived artifact lives). '*' stays
# excluded from the body so a prefix glob like "samples/%s*.hwp" % prefix is
# not mistaken for a literal filename: every legitimate glob reference
# contains one. Whitespace is allowed in the body -- half of the real sample
# filenames contain a space (e.g. "20131106 ETRI ...").
#
# I1 hardening: the previous version anchored "samples/" *immediately* after
# the opening quote and required the extension immediately before the
# closing quote. Both anchors were too tight and let realistic spellings
# through untouched: "./samples/x.hwp", "../samples/x.hwp", an absolute path
# ending ".../samples/x.hwp", a backslash separator, and an uppercase
# extension all passed `_names_a_sample` unflagged (verified by calling it
# directly). This version:
#   - captures the "samples/..." path in a named group, not the whole quoted
#     literal, so a leading "./", "../", or absolute-path prefix in front of
#     it doesn't change what gets compared against the public-fixture
#     exemption below;
#   - allows an arbitrary prefix before "samples" (any char except the
#     enclosing quote or '*'), covering "./", "../", and absolute paths in
#     one shot, but requires the character immediately before "samples" to
#     be the opening quote or a path separator (the lookbehind) so an
#     unrelated word like "not_samples/x.hwp" isn't mistaken for the
#     "samples/" directory;
#   - accepts '/' or '\' as the separator, both before and after "samples",
#     so a backslash-separated path is caught too;
#   - matches the extension case-insensitively, so "X.HWP" is caught.
#
# Known, deliberate gaps (not achievable here without unacceptable false
# positives -- do not assume these are covered):
#   - `os.path.join("samples", "x.hwp")`: the directory and filename are two
#     separate string literals: nothing joins them at the text level, and
#     matching "samples" and an *.hwp(x) literal independently would flag
#     ordinary code (e.g. `os.path.join(out_dir, "x.hwp")` next to an
#     unrelated `"samples"` literal elsewhere in the same file).
#   - a bare basename with no directory, e.g. `"x.hwpx"`: closing this would
#     flag every *.hwp/*.hwpx string literal in the suite, the overwhelming
#     majority of which are synthetic temp-file names
#     (`tempfile.mktemp(suffix=".hwpx")` targets, `"out.hwpx"`, etc.), not
#     samples/ references at all.
#   - `"samples/x.hwp.bak"`: the extension check requires the literal to end
#     at ".hwp"/".hwpx" or hit a non-word character there; a suffix tacked on
#     after a *word* character (rare in practice) would still slip through.
_LITERAL_SAMPLE = re.compile(
    r"""['"][^'"*]*(?<=['"/\\])(?P<path>samples[/\\][^'"*]*\.hwpx?)(?=['"])""",
    re.IGNORECASE,
)

# samples/test_document.hwp(x) is the one sample this project commits (task 2):
# a document authored for this project with no confidential content. tests/
# samplepaths.py names it literally by design (TEST_DOC/TEST_DOC_REF), so it
# must not trip a gate meant to catch the private corpus.
_PUBLIC_FIXTURE = {"samples/test_document.hwp", "samples/test_document.hwpx"}


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git_ls_files(*patterns):
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
    # No patterns -> `git ls-files` lists every tracked file (used by I2's
    # widened scan); one or more patterns filter it, same as before.
    result = subprocess.run(["git", "ls-files", *patterns],
                            capture_output=True, text=True, check=True)
    return [p for p in result.stdout.splitlines() if p]


# I2: the only tracked files that are actually binary. Decoding them as text
# would raise; their being tracked at all (and being exactly these two) is
# independently enforced by test_public_fixture_is_tracked and I3's
# test_only_the_public_fixture_is_tracked_as_hwp below.
_BINARY_EXTENSIONS = (".hwp", ".hwpx")

# This module's own repo-relative path -- excluded from the scan it runs.
_THIS_FILE = "tests/test_samples_privacy.py"


def _tracked_text_files():
    """Every tracked file worth scanning for a leaked private-sample path.

    I2: widened from *.py. README.md, the CI workflow YAML, pyproject.toml,
    or any future JSON/YAML/TXT fixture could carry a leaked path just as
    easily as a .py file, and a *.py-only scan would miss all of them.

    Two classes of tracked file are excluded, for different reasons -- both
    on purpose, not by omission:
      - docs/**/*.md: historical planning/design documents. They routinely
        name real sample files by design, as working notes for whoever picks
        a milestone back up (e.g. "Samples live at samples/3...hwp[x]").
        That is pre-existing and accepted; churning every historical doc to
        satisfy this gate is out of scope here.
      - *.hwp / *.hwpx: binary (OLE2/zip), not text. The only two tracked
        are the public fixture pair, and that fact is checked separately
        (below), not by this scan.
    """
    paths = _git_ls_files()
    out = []
    for p in paths:
        if p == _THIS_FILE:
            # M8: excluded by exact repo-relative path, not by basename --
            # a basename match would exempt any file sharing this name
            # anywhere else in the tree, not just this one.
            continue
        if p.startswith("docs/") and p.endswith(".md"):
            continue
        if p.endswith(_BINARY_EXTENSIONS):
            continue
        out.append(p)
    return out


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
    # finditer, not search: search returns only the *first* literal on the
    # line, so a private path sitting after an exempt public one on the same
    # line -- e.g. a list of both -- would never be inspected at all.
    #
    # Normalize backslash separators before comparing against the exemption
    # set, which is spelled with '/': a backslash-separated reference to the
    # public fixture must still be recognized as exempt, not just a
    # backslash-separated private path being caught.
    return any(m.group("path").replace("\\", "/") not in _PUBLIC_FIXTURE
               for m in _LITERAL_SAMPLE.finditer(line))


def test_no_committed_file_names_a_sample():
    offenders = []
    for path in _tracked_text_files():
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


def test_no_hwp_document_is_tracked_outside_the_public_fixture():
    # I3: test_public_fixture_is_tracked (above) only looks under samples/,
    # so nothing stops a private document from being tracked somewhere else
    # entirely -- `git add -f docs/example.hwp` or `tests/data/thing.hwpx`
    # would be caught by neither that test nor _names_a_sample (which only
    # matches a quoted "samples/...hwp(x)" *string literal*, not an actual
    # tracked binary file). Assert directly on the repo-wide set of tracked
    # *.hwp/*.hwpx files instead of trusting they only ever land in samples/.
    tracked = sorted(_git_ls_files("*.hwp", "*.hwpx"))
    assert tracked == ["samples/test_document.hwp",
                       "samples/test_document.hwpx"], (
        "only the public fixture may be tracked as *.hwp/*.hwpx anywhere in "
        "the repo, got: %s" % tracked)


def test_no_fixture_derived_from_a_sample_is_tracked():
    # tests/fixtures/ holds dumps (e.g. hwp5proc xml) of private samples --
    # generated on demand by tests/samplepaths.py, not committed. A tracked
    # file there would leak the same document content this module guards
    # against, just one step removed from samples/ itself.
    tracked = _git_ls_files("tests/fixtures")
    assert tracked == [], (
        "tests/fixtures/ must stay generated-and-ignored (derived from "
        "private samples/), but git tracks: %s" % ", ".join(tracked))


def test_gate_catches_a_private_literal_hiding_behind_the_public_one():
    # A line may hold several literals. Matching only the first one lets an
    # exempt public path act as a shield for a private path after it.
    assert _names_a_sample(
        'PATHS = ["samples/test_document.hwp", "samples/a private report.hwp"]\n')
    assert _names_a_sample(
        'PATHS = ["samples/a private report.hwp", "samples/test_document.hwp"]\n')


def test_gate_still_allows_a_line_of_only_public_literals():
    assert not _names_a_sample(
        'PATHS = ["samples/test_document.hwp", "samples/test_document.hwpx"]\n')


# I1: path-spelling bypasses. All constructed synthetically -- a real sample
# filename must never appear in a committed file, including here.


def test_gate_catches_a_leading_dot_slash():
    assert _names_a_sample('X = "./samples/made up name.hwp"\n')


def test_gate_catches_a_leading_dot_dot_slash():
    assert _names_a_sample('X = "../samples/made up name.hwp"\n')


def test_gate_catches_an_absolute_path():
    assert _names_a_sample('X = "/Users/dev/project/samples/made up name.hwp"\n')


def test_gate_catches_an_uppercase_extension():
    assert _names_a_sample('X = "samples/MADE_UP_NAME.HWP"\n')


def test_gate_catches_a_backslash_separator():
    # Raw string: exactly one literal backslash between "samples" and the
    # filename, as it would appear in a source file's raw bytes.
    assert _names_a_sample(r'X = "samples\made up name.hwp"' + "\n")


def test_gate_still_ignores_the_public_fixture_with_a_leading_dot_slash():
    # The path-only capture group (not the whole quoted literal) is what's
    # compared to the exemption set, so a "./" or "../" prefix in front of
    # the *public* fixture must still be recognized as exempt.
    assert not _names_a_sample('X = "./samples/test_document.hwp"\n')
    assert not _names_a_sample('X = "../samples/test_document.hwpx"\n')


def test_gate_does_not_flag_an_unrelated_word_ending_in_samples():
    # The lookbehind requires the character right before "samples" to be a
    # quote or a path separator, so "not_samples/" isn't mistaken for the
    # samples/ directory.
    assert not _names_a_sample('X = "not_samples/made-up-name.hwp"\n')
