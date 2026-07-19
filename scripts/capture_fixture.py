"""Capture pyhwp's hwp5proc XML dump for a sample, as a test fixture."""
import subprocess
import sys
import os

# Run from repo root as a plain script, so tests/ (a package) isn't on
# sys.path by default; add it to reuse the shared sample resolver.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.samplepaths import S3

SAMPLE = S3
OUT = "tests/fixtures/sample3.hwp5.xml"


def main():
    os.makedirs("tests/fixtures", exist_ok=True)
    xml = subprocess.check_output(["hwp5proc", "xml", SAMPLE])
    with open(OUT, "wb") as f:
        f.write(xml)
    print("wrote", OUT, len(xml), "bytes")


if __name__ == "__main__":
    sys.exit(main())
