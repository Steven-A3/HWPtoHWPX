"""Resolve sample documents by prefix.

samples/ holds private documents and is git-ignored, so no committed file may
name one. Tests locate their samples through this module instead, by the
number/tag prefix the project uses to refer to them (3, 4, 2013, ★131008).

Resolution never raises when a sample is missing: 34 test modules import these
constants at module scope, so raising here turns an absent private corpus into
collection errors, which pytest cannot skip. Missing samples yield a path that
simply does not exist, and tests/conftest.py skips the tests that need one.
"""
import glob
import os
import subprocess
import tempfile

FIXTURE3 = "tests/fixtures/sample3.hwp5.xml"

# The one public, committed document: authored in Hancom Office for this
# project, contains no confidential content, and is the only sample CI can see.
TEST_DOC = "samples/test_document.hwp"
TEST_DOC_REF = "samples/test_document.hwpx"

_fixture3_cache = None  # generated at most once per session


def _one(pattern, fallback):
    matches = sorted(glob.glob(pattern))  # sorted: never depend on FS order
    return matches[0] if matches else fallback


def hwp(prefix):
    """The source document whose filename starts with `prefix`.

    Returns a non-existent placeholder path when the sample is absent. The
    fallback keeps the glob's own '*' rather than going fully literal: the
    privacy gate (tests/test_samples_privacy.py) treats any quoted
    samples/...hwp(x) string with no '*' as a leaked filename, and this one
    never resolves to a real document anyway.
    """
    return _one("samples/%s*.hwp" % prefix, "samples/%s*missing.hwp" % prefix)


def hwpx(prefix):
    """Hancom's own .hwpx export of that document -- the fidelity reference."""
    return _one("samples/%s*.hwpx" % prefix, "samples/%s*missing.hwpx" % prefix)


S3 = hwp("3.")
S3_REF = hwpx("3.")
S4 = hwp("4.")
S4_REF = hwpx("4.")


def samples_available():
    """True when the private corpus is present.

    The public fixture lives in samples/ too, so the directory existing proves
    nothing -- check the private documents themselves.
    """
    return all(os.path.exists(p) for p in (S3, S3_REF, S4, S4_REF))


def fixture3():
    """Path to the hwp5proc xml dump of S3, generating it if absent.

    tests/fixtures/ is git-ignored: the dump embeds document text, so it must
    stay a local, regenerable artifact rather than a committed file. Caches
    the check so repeated calls within a session don't re-shell out once the
    file exists.

    Skips generation when S3 itself is absent, returning the (possibly
    nonexistent) FIXTURE3 path instead of shelling out to hwp5proc against a
    placeholder. 14 test_reader_*.py modules call this at module scope
    (`FIXTURE = fixture3()`); those modules import this function's name, so
    tests/conftest.py's identity-based skip already catches them once
    collection succeeds -- but collection itself happens before any skip
    marker can apply, so this function must not raise (or crash out to a
    subprocess) just because the corpus is missing.
    """
    global _fixture3_cache
    if _fixture3_cache is not None:
        return _fixture3_cache
    if not os.path.exists(FIXTURE3) and os.path.exists(S3):
        fixture_dir = os.path.dirname(FIXTURE3)
        os.makedirs(fixture_dir, exist_ok=True)
        # M6: with the corpus present but hwp5proc missing from PATH, this
        # used to raise a raw FileNotFoundError out of collection (pytest
        # can't skip a collection-time error) with no hint of the cause --
        # a contributor's first run getting an opaque traceback instead of
        # "install hwp5proc". The corpus-absent case above already returns
        # early without shelling out at all; this is strictly the
        # corpus-present-but-tool-missing case.
        try:
            xml = subprocess.check_output(["hwp5proc", "xml", S3])
        except FileNotFoundError as exc:
            raise RuntimeError(
                "hwp5proc (from pyhwp) not found on PATH -- required to "
                "generate %s from the private samples/ corpus. Install "
                "pyhwp (`pip install pyhwp`) or otherwise put hwp5proc on "
                "PATH, then re-run." % FIXTURE3
            ) from exc
        # Atomic: write to a temp file in the same directory, then rename.
        # A process interrupted mid-write (Ctrl-C, OOM kill) must never
        # leave a truncated FIXTURE3 behind -- os.path.exists(FIXTURE3)
        # above would then treat that truncated file as already-generated
        # forever, poisoning every later run in this checkout.
        fd, tmp_path = tempfile.mkstemp(
            dir=fixture_dir, prefix=".fixture3-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(xml)
            os.replace(tmp_path, FIXTURE3)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    _fixture3_cache = FIXTURE3
    return _fixture3_cache
