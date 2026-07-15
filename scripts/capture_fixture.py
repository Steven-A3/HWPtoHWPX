"""Capture pyhwp's hwp5proc XML dump for a sample, as a test fixture."""
import subprocess
import sys
import os

SAMPLE = "samples/3.과업지시서_070.hwp"
OUT = "tests/fixtures/sample3.hwp5.xml"


def main():
    os.makedirs("tests/fixtures", exist_ok=True)
    xml = subprocess.check_output(["hwp5proc", "xml", SAMPLE])
    with open(OUT, "wb") as f:
        f.write(xml)
    print("wrote", OUT, len(xml), "bytes")


if __name__ == "__main__":
    sys.exit(main())
