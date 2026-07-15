"""Command-line entry point."""
import argparse
import os
import sys
from .convert import convert


def main(argv):
    parser = argparse.ArgumentParser(prog="hwp2hwpx",
                                     description="Convert HWP 5.0 files to HWPX.")
    parser.add_argument("input", help="path to input .hwp file")
    parser.add_argument("-o", "--output", required=True, help="path to output .hwpx file")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.input):
        print("error: input file not found: %s" % args.input, file=sys.stderr)
        return 1
    try:
        convert(args.input, args.output)
    except Exception as exc:  # convert failures -> clean message, not a traceback
        print("error: conversion failed for %s: %s" % (args.input, exc), file=sys.stderr)
        return 1
    return 0


def entrypoint():
    raise SystemExit(main(sys.argv[1:]))
