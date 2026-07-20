"""Resolve sample documents by prefix.

samples/ holds private documents and is git-ignored, so no committed file may
name one. Tests locate their samples through this module instead, by the
number/tag prefix the project uses to refer to them (3, 4, 2013, ★131008).
"""
import glob
import os
import subprocess

FIXTURE3 = "tests/fixtures/sample3.hwp5.xml"

_fixture3_cache = None  # generated at most once per session


def _one(pattern):
    matches = sorted(glob.glob(pattern))  # sorted: never depend on FS order
    if not matches:
        raise FileNotFoundError("no sample matches %s" % pattern)
    return matches[0]


def hwp(prefix):
    """The source document whose filename starts with `prefix`."""
    return _one("samples/%s*.hwp" % prefix)


def hwpx(prefix):
    """Hancom's own .hwpx export of that document -- the fidelity reference."""
    return _one("samples/%s*.hwpx" % prefix)


S3 = hwp("3.")
S3_REF = hwpx("3.")
S4 = hwp("4.")
S4_REF = hwpx("4.")


def fixture3():
    """Path to the hwp5proc xml dump of S3, generating it if absent.

    tests/fixtures/ is git-ignored: the dump embeds document text, so it must
    stay a local, regenerable artifact rather than a committed file. Caches
    the check so repeated calls within a session don't re-shell out once the
    file exists.
    """
    global _fixture3_cache
    if _fixture3_cache is not None:
        return _fixture3_cache
    if not os.path.exists(FIXTURE3):
        os.makedirs(os.path.dirname(FIXTURE3), exist_ok=True)
        xml = subprocess.check_output(["hwp5proc", "xml", S3])
        with open(FIXTURE3, "wb") as f:
            f.write(xml)
    _fixture3_cache = FIXTURE3
    return _fixture3_cache
