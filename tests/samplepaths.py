"""Resolve sample documents by prefix.

samples/ holds private documents and is git-ignored, so no committed file may
name one. Tests locate their samples through this module instead, by the
number/tag prefix the project uses to refer to them (3, 4, 2013, ★131008).
"""
import glob


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
