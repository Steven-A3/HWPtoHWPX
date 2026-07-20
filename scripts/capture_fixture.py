"""Capture pyhwp's hwp5proc XML dump for a sample, as a test fixture."""
import sys
import os

# Run from repo root as a plain script, so tests/ (a package) isn't on
# sys.path by default; add it to reuse the shared sample resolver.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.samplepaths import fixture3


def main():
    path = fixture3()
    print("wrote", path, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    sys.exit(main())
