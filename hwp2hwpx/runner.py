"""Plan and execute a batch of HWP -> HWPX conversions.

Planning is separated from execution so that every naming, arity, and overwrite
rule can be tested against paths alone -- a real conversion costs ~0.4 s, and
these rules are where the data-loss risk lives, not in the conversion itself.
"""
import os
from collections import namedtuple

from .convert import convert

# action: "convert" (destination is free), "skip" (destination exists, leave it),
# "overwrite" (destination exists and --force was given).
Job = namedtuple("Job", "input output action")
Result = namedtuple("Result", "input output action ok error error_type")


class UsageError(Exception):
    """A bad invocation, detected before any conversion runs."""


def default_output(input_path):
    return os.path.splitext(input_path)[0] + ".hwpx"


def plan_jobs(inputs, out_file=None, outdir=None, force=False):
    """Resolve inputs and flags into a job list. Reads the filesystem only to
    test whether each destination already exists; creates nothing."""
    if out_file and outdir:
        raise UsageError("-o and --outdir cannot be used together")
    if out_file and len(inputs) != 1:
        raise UsageError(
            "-o accepts exactly one input; use --outdir for several")
    if force and not (out_file or outdir):
        raise UsageError(
            "--force requires an explicit -o or --outdir, so that overwriting "
            "a directory of documents in place has to be asked for by name")
    jobs = []
    for path in inputs:
        if out_file:
            output = out_file
        elif outdir:
            output = os.path.join(outdir, os.path.basename(default_output(path)))
        else:
            output = default_output(path)
        if os.path.exists(output):
            action = "overwrite" if force else "skip"
        else:
            action = "convert"
        jobs.append(Job(path, output, action))
    _reject_output_collisions(jobs)
    return jobs


def _reject_output_collisions(jobs):
    """Raise if two jobs would write the same destination. Sequential
    execution would let the second silently clobber the first, so this must
    be caught here -- before any conversion runs -- rather than in run_jobs."""
    inputs_by_output = {}
    for job in jobs:
        # Group on the normalized path so that "d/a.hwp" and "d/./a.hwp" -- the
        # same destination spelled two ways -- still collide. normpath is pure
        # string work; resolving symlinks would need the filesystem.
        key = os.path.normpath(job.output)
        inputs_by_output.setdefault(key, []).append(job.input)
    for output, inputs in inputs_by_output.items():
        if len(inputs) > 1:
            raise UsageError(
                "multiple inputs resolve to the same output {!r}: {}".format(
                    output, ", ".join(inputs)))


def run_jobs(jobs, on_result=None):
    """Convert each job, isolating per-file failures, and report each Result to
    `on_result` as it completes, in job order (jobs run sequentially, one at a
    time, in the order given)."""
    results = []
    for job in jobs:
        if job.action == "skip":
            result = Result(job.input, job.output, job.action, True, None, None)
        else:
            try:
                convert(job.input, job.output)
            except Exception as exc:  # one bad document must not end the run
                result = Result(job.input, job.output, job.action, False,
                                str(exc), type(exc).__name__)
            else:
                result = Result(job.input, job.output, job.action, True,
                                None, None)
        results.append(result)
        if on_result is not None:
            on_result(result)
    return results
