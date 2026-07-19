"""Command-line entry point."""
import argparse
import json
import os
import sys

from .runner import UsageError, plan_jobs, run_jobs

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2  # argparse's own convention for a bad invocation


def _installed_version():
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("hwp2hwpx")
    except PackageNotFoundError:  # running from a source tree, not installed
        return "unknown"


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="hwp2hwpx", description="Convert HWP 5.0 files to HWPX.")
    parser.add_argument("input", nargs="+", help="path to an input .hwp file")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument(
        "-o", "--output", help="output .hwpx path (exactly one input)")
    destination.add_argument(
        "--outdir", help="directory to write outputs into (created if absent)")
    parser.add_argument(
        "--force", action="store_true",
        help="overwrite existing outputs; requires -o or --outdir")
    # A mandatory value: with nargs="?" argparse binds the next positional to
    # this flag and silently drops that document from the run.
    parser.add_argument(
        "--json", dest="json_path", metavar="FILE",
        help="write a JSON report to FILE ('-' for stdout)")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-q", "--quiet", action="store_true",
        help="suppress per-failure messages; the exit code is the only signal")
    verbosity.add_argument(
        "-v", "--verbose", action="store_true",
        help="report every file and a summary on stderr")
    parser.add_argument("--version", action="version",
                        version=_installed_version())
    return parser


def _counts(results):
    counts = {"converted": 0, "overwritten": 0, "skipped": 0, "failed": 0}
    for result in results:
        if not result.ok:
            counts["failed"] += 1
        elif result.action == "skip":
            counts["skipped"] += 1
        elif result.action == "overwrite":
            counts["overwritten"] += 1
        else:
            counts["converted"] += 1
    return counts


def _write_json(path, counts, results):
    report = {
        "counts": counts,
        "files": [{"input": r.input, "output": r.output, "action": r.action,
                   "ok": r.ok, "error": r.error, "error_type": r.error_type}
                  for r in results],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if path == "-":
        print(text)
    else:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def main(argv):
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        jobs = plan_jobs(args.input, out_file=args.output,
                         outdir=args.outdir, force=args.force)
    except UsageError as exc:
        parser.error(str(exc))  # raises SystemExit(EXIT_USAGE)
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)

    def report(result):
        if result.ok:
            if args.verbose:
                print("%s: %s -> %s" % (result.action, result.input,
                                        result.output), file=sys.stderr)
        elif not args.quiet:
            # The exception type is noise in a batch log unless asked for, and
            # a traceback always is.
            detail = ("%s: %s" % (result.error_type, result.error)
                      if args.verbose else result.error)
            print("error: %s: %s" % (result.input, detail), file=sys.stderr)

    results = run_jobs(jobs, on_result=report)
    counts = _counts(results)
    if args.verbose:
        print("converted %(converted)d, overwritten %(overwritten)d, "
              "skipped %(skipped)d, failed %(failed)d" % counts,
              file=sys.stderr)
    if args.json_path:
        _write_json(args.json_path, counts, results)
    return EXIT_FAILED if counts["failed"] else EXIT_OK


def entrypoint():
    raise SystemExit(main(sys.argv[1:]))
