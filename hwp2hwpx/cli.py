"""Command-line entry point."""
import argparse


def main(argv):
    parser = argparse.ArgumentParser(prog="hwp2hwpx",
                                     description="Convert HWP 5.0 files to HWPX.")
    parser.add_argument("input", help="path to input .hwp file")
    parser.add_argument("-o", "--output", required=True, help="path to output .hwpx file")
    parser.parse_args(argv)
    # Wired to convert() in Task 18.
    return 0


def entrypoint():
    import sys
    raise SystemExit(main(sys.argv[1:]))
