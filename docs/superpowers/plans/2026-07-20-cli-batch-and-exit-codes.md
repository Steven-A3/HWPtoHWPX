# CLI Batch Conversion and Exit Codes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `hwp2hwpx` from a one-file utility into a tool a script can drive over a corpus: many inputs, isolated failures, meaningful exit codes, an opt-in JSON report, and defaults that cannot destroy data.

**Architecture:** A new `hwp2hwpx/runner.py` holds a pure `plan_jobs()` (paths + flags → job list, no I/O beyond existence checks) and a `run_jobs()` that executes jobs and yields one result record per file. `hwp2hwpx/cli.py` stays thin: argparse, rendering (text and JSON from the same records), exit code. Separately, `owpml/writer.py`'s `write_package` becomes atomic, because skip-existing is only safe if an existing output implies a *completed* conversion.

**Tech Stack:** Python 3.9+, stdlib only (`argparse`, `json`, `os`, `tempfile`, `zipfile`, `importlib.metadata`), pytest.

**Spec:** `docs/superpowers/specs/2026-07-20-cli-batch-and-exit-codes-design.md`

## Global Constraints

- **Python 3.9 floor.** No PEP-604 `X | None` unions — use `typing.Optional`. Mutable dataclass defaults via `field(default_factory=...)`.
- **Run tests only as `.venv/bin/python -m pytest`** — plain `python` lacks the `hwp5proc` entry point that several test oracles use. Full suite ~81 s; use a 420000 ms timeout.
- **`samples/` holds private Korean government documents and is git-ignored.** Committed code, comments, and tests must contain **no sample filename and no sample text content**. Reference samples by number/tag (3, 4, 2013, ★131008) and locate them via prefix glob: `glob.glob("samples/3.*.hwp")[0]`. Never `git add` anything under `samples/`.
- **Conversion output must not change.** `tests/test_parse_once.py::test_output_matches_golden` compares every zip part against pre-refactor goldens in `samples/goldens/` on all four samples and must stay green.
- **Exit codes:** `0` = no failures (skips are not failures), `1` = one or more files failed, `2` = usage error.
- **`--force` is honored only with an explicit `-o` or `--outdir`.** With default beside-input naming it is a usage error.
- **`--json` takes a mandatory value** (`-` means stdout). It must never be able to absorb a positional input.
- Comments explain *why*, not *what*. No debugging scaffolding or commented-out code.
- Don't add dependencies.
- Commit messages: concise imperative, ending with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

| File | Responsibility |
|---|---|
| `hwp2hwpx/owpml/writer.py` (modify) | `write_package` builds the zip at a temp path in the destination directory and `os.replace`s it into position. |
| `hwp2hwpx/runner.py` (create) | `Job`, `Result`, `UsageError`, `default_output`, `plan_jobs` (pure), `run_jobs` (executes, isolates failures). |
| `hwp2hwpx/cli.py` (rewrite) | argparse surface, text/JSON rendering, exit code. No naming or conversion logic. |
| `tests/test_writer_atomic.py` (create) | Atomicity gate. |
| `tests/test_runner.py` (create) | Job planning and execution, almost all without converting anything. |
| `tests/test_cli.py` (rewrite) | CLI surface, exit codes, JSON, argparse hole. Also fixes the hardcoded sample filename. |

---

### Task 1: Atomic package writes

**Files:**
- Modify: `hwp2hwpx/owpml/writer.py:1-23`
- Test: `tests/test_writer_atomic.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `write_package(parts, out_path)` — unchanged signature and unchanged output bytes; now atomic. Task 2's `run_jobs` relies on this so a failed conversion never leaves a partial output that skip-existing would later treat as done.

**Why this is first:** skip-existing (Task 2) is unsafe without it. `zipfile.ZipFile(out_path, "w")` truncates the destination immediately, so a Ctrl-C mid-batch leaves a truncated `.hwpx` that every future run skips as complete.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_writer_atomic.py`:

```python
import os

import pytest

from hwp2hwpx.owpml.writer import write_package

# An int is neither bytes nor str, so zipfile.writestr rejects it -- a cheap way
# to fail *during* the zip write, which is the moment atomicity has to cover.
BAD_PARTS = {"Contents/section0.xml": 12345}
GOOD_PARTS = {"Contents/section0.xml": b"<hello/>"}


def test_failed_write_leaves_previous_content_intact(tmp_path):
    out = tmp_path / "out.hwpx"
    out.write_bytes(b"previous document")
    with pytest.raises(Exception):
        write_package(BAD_PARTS, str(out))
    assert out.read_bytes() == b"previous document"


def test_failed_write_creates_no_output(tmp_path):
    out = tmp_path / "out.hwpx"
    with pytest.raises(Exception):
        write_package(BAD_PARTS, str(out))
    assert not out.exists()


def test_failed_write_leaves_no_temp_file_behind(tmp_path):
    out = tmp_path / "out.hwpx"
    with pytest.raises(Exception):
        write_package(BAD_PARTS, str(out))
    assert os.listdir(str(tmp_path)) == []


def test_successful_write_leaves_only_the_output(tmp_path):
    out = tmp_path / "out.hwpx"
    write_package(GOOD_PARTS, str(out))
    assert os.listdir(str(tmp_path)) == ["out.hwpx"]


def test_output_is_world_readable_not_private(tmp_path):
    # tempfile.mkstemp creates 0600; os.replace would carry that onto the
    # output, silently making every converted document owner-only.
    out = tmp_path / "out.hwpx"
    write_package(GOOD_PARTS, str(out))
    assert os.stat(str(out)).st_mode & 0o044
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_writer_atomic.py -v`

Expected: `test_failed_write_leaves_previous_content_intact` FAILS (the file was truncated to an empty/partial zip), `test_failed_write_creates_no_output` FAILS (a truncated file exists). The three remaining tests may already pass — that is fine and expected.

- [ ] **Step 3: Make `write_package` atomic**

Replace lines 1-23 of `hwp2hwpx/owpml/writer.py` (the imports and the whole `write_package` body) with:

```python
"""Assemble an OWPML document into a .hwpx ZIP package."""
import os
import tempfile
import zipfile
from .. import constants
from . import package_parts
from .header_writer import header_xml
from .section_writer import section_xml


def _umask_file_mode():
    # tempfile.mkstemp creates 0600. Replacing the destination with it would
    # make every converted document owner-only, so restore the mode a normal
    # create would have produced. Reading the umask requires setting it.
    umask = os.umask(0o022)
    os.umask(umask)
    return 0o666 & ~umask


def write_package(parts, out_path):
    """Write `parts` (name->bytes) to a .hwpx ZIP.

    The `mimetype` entry is always written first and STORED (uncompressed),
    as Hancom requires. A caller-supplied "mimetype" value overrides the default.

    The package is built at a temporary path in the destination directory and
    moved into place with os.replace, which is atomic within a filesystem. An
    interrupted write therefore never leaves a truncated .hwpx where a complete
    one is expected -- batch mode skips outputs that already exist, so a corpse
    left at the destination would be treated as a finished conversion forever.
    """
    mimetype = parts.get("mimetype", constants.MIMETYPE.encode("ascii"))
    if isinstance(mimetype, str):
        mimetype = mimetype.encode("ascii")
    out_dir = os.path.dirname(os.path.abspath(out_path))
    fd, tmp_path = tempfile.mkstemp(dir=out_dir, prefix=".hwp2hwpx-", suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(zipfile.ZipInfo("mimetype"), mimetype,
                       compress_type=zipfile.ZIP_STORED)
            for name, data in parts.items():
                if name == "mimetype":
                    continue
                z.writestr(name, data)
        os.chmod(tmp_path, _umask_file_mode())
        os.replace(tmp_path, out_path)
    except BaseException:
        # BaseException, not Exception: KeyboardInterrupt mid-batch is exactly
        # the case that must not strand a temp file next to the output.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

Leave the rest of the file (`write_hwpx`) untouched.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_writer_atomic.py -v`
Expected: 5 passed.

- [ ] **Step 5: Verify conversion output did not change**

Run: `.venv/bin/python -m pytest tests/test_parse_once.py -v`
Expected: all pass, and the four `test_output_matches_golden` cases must PASS (not skip). If they skip, the goldens are missing — stop and report, do not proceed.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/writer.py tests/test_writer_atomic.py
git commit -m "fix: write .hwpx packages atomically via temp file and os.replace

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The runner — job planning and execution

**Files:**
- Create: `hwp2hwpx/runner.py`
- Test: `tests/test_runner.py` (create)

**Interfaces:**
- Consumes: `hwp2hwpx.convert.convert(hwp_path, out_path)`; atomic `write_package` from Task 1.
- Produces, for Task 3:
  - `UsageError(Exception)` — a bad invocation, raised before any conversion.
  - `Job = namedtuple("Job", "input output action")`, `action` in `{"convert", "skip", "overwrite"}`.
  - `Result = namedtuple("Result", "input output action ok error error_type")`; on success `error` and `error_type` are `None`.
  - `default_output(input_path) -> str`
  - `plan_jobs(inputs, out_file=None, outdir=None, force=False) -> list` of `Job`
  - `run_jobs(jobs, on_result=None) -> list` of `Result`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_runner.py`:

```python
import os

import pytest

from hwp2hwpx.runner import (
    Job, Result, UsageError, default_output, plan_jobs, run_jobs,
)


def test_default_output_swaps_the_extension():
    assert default_output("/docs/report.hwp") == "/docs/report.hwpx"


def test_default_output_places_the_file_beside_its_input():
    assert os.path.dirname(default_output("/a/b/c.hwp")) == "/a/b"


def test_plan_uses_beside_input_naming_when_no_destination_given():
    jobs = plan_jobs(["/docs/a.hwp", "/docs/b.hwp"])
    assert [j.output for j in jobs] == ["/docs/a.hwpx", "/docs/b.hwpx"]
    assert all(j.action == "convert" for j in jobs)


def test_plan_puts_outputs_in_outdir_keeping_only_the_basename():
    jobs = plan_jobs(["/docs/deep/a.hwp"], outdir="/out")
    assert jobs[0].output == os.path.join("/out", "a.hwpx")


def test_plan_honors_o_for_a_single_input():
    jobs = plan_jobs(["/docs/a.hwp"], out_file="/tmp/named.hwpx")
    assert jobs == [Job("/docs/a.hwp", "/tmp/named.hwpx", "convert")]


def test_plan_rejects_o_with_several_inputs():
    with pytest.raises(UsageError):
        plan_jobs(["/docs/a.hwp", "/docs/b.hwp"], out_file="/tmp/named.hwpx")


def test_plan_rejects_o_together_with_outdir():
    with pytest.raises(UsageError):
        plan_jobs(["/docs/a.hwp"], out_file="/tmp/named.hwpx", outdir="/out")


def test_plan_rejects_force_without_an_explicit_destination():
    # The V1 gate: --force plus beside-input naming would mass-overwrite a
    # folder in place, destroying reference .hwpx exports stored next to their
    # sources. Overwriting must require naming the destination.
    with pytest.raises(UsageError):
        plan_jobs(["/docs/a.hwp"], force=True)


def test_plan_allows_force_with_an_explicit_destination():
    jobs = plan_jobs(["/docs/a.hwp"], outdir="/out", force=True)
    assert jobs[0].action == "convert"


def test_plan_skips_an_existing_output(tmp_path):
    src = tmp_path / "a.hwp"
    src.write_bytes(b"x")
    (tmp_path / "a.hwpx").write_bytes(b"already here")
    jobs = plan_jobs([str(src)])
    assert jobs[0].action == "skip"


def test_plan_marks_an_existing_output_for_overwrite_under_force(tmp_path):
    src = tmp_path / "a.hwp"
    src.write_bytes(b"x")
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.hwpx").write_bytes(b"already here")
    jobs = plan_jobs([str(src)], outdir=str(out), force=True)
    assert jobs[0].action == "overwrite"


def test_plan_creates_nothing_on_disk(tmp_path):
    plan_jobs([str(tmp_path / "a.hwp")], outdir=str(tmp_path / "nope"))
    assert not (tmp_path / "nope").exists()


def test_run_skips_without_converting(monkeypatch):
    import hwp2hwpx.runner as runner
    calls = []
    monkeypatch.setattr(runner, "convert", lambda i, o: calls.append(i))
    results = run_jobs([Job("a.hwp", "a.hwpx", "skip")])
    assert calls == []
    assert results == [Result("a.hwp", "a.hwpx", "skip", True, None, None)]


def test_run_isolates_a_failure_and_keeps_going(monkeypatch):
    import hwp2hwpx.runner as runner

    def flaky(inp, out):
        if inp == "bad.hwp":
            raise ValueError("broken record")

    monkeypatch.setattr(runner, "convert", flaky)
    results = run_jobs([
        Job("bad.hwp", "bad.hwpx", "convert"),
        Job("good.hwp", "good.hwpx", "convert"),
    ])
    assert [r.ok for r in results] == [False, True]
    assert results[0].error == "broken record"
    assert results[0].error_type == "ValueError"
    assert results[1].error is None


def test_run_reports_each_result_as_it_completes(monkeypatch):
    import hwp2hwpx.runner as runner
    monkeypatch.setattr(runner, "convert", lambda i, o: None)
    seen = []
    run_jobs([Job("a.hwp", "a.hwpx", "convert")], on_result=seen.append)
    assert [r.input for r in seen] == ["a.hwp"]


def test_run_treats_a_missing_input_as_a_per_file_failure():
    # Not a usage error: one typo in a 500-path list must not abort the run.
    results = run_jobs([Job("does-not-exist.hwp", "x.hwpx", "convert")])
    assert results[0].ok is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_runner.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'hwp2hwpx.runner'`.

- [ ] **Step 3: Write the runner**

Create `hwp2hwpx/runner.py`:

```python
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
    return jobs


def run_jobs(jobs, on_result=None):
    """Convert each job, isolating per-file failures, and report each Result to
    `on_result` as it completes."""
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_runner.py -v`
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/runner.py tests/test_runner.py
git commit -m "feat: add runner with pure job planning and isolated execution

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: The CLI surface

**Files:**
- Rewrite: `hwp2hwpx/cli.py` (whole file)
- Rewrite: `tests/test_cli.py` (whole file — also removes the hardcoded sample filename)

**Interfaces:**
- Consumes from Task 2: `UsageError`, `plan_jobs(inputs, out_file=None, outdir=None, force=False)`, `run_jobs(jobs, on_result=None)`, and `Result` fields `input output action ok error error_type`.
- Produces: `main(argv) -> int` and `entrypoint()`, both already referenced by `pyproject.toml`'s `hwp2hwpx = "hwp2hwpx.cli:entrypoint"`.

**Note on usage errors:** argparse exits by raising `SystemExit(2)` rather than returning. `main()` therefore *returns* 0 or 1, and *raises* `SystemExit(2)` for usage errors. Tests assert usage errors with `pytest.raises(SystemExit)` and check `.value.code == 2`.

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_cli.py` with:

```python
import glob
import json
import os

import pytest

from hwp2hwpx.cli import main


def _sample():
    # samples/ is private and git-ignored; locate by prefix, never by filename.
    return glob.glob("samples/3.*.hwp")[0]


def test_converts_a_single_file_with_explicit_output(tmp_path):
    out = tmp_path / "out.hwpx"
    assert main([_sample(), "-o", str(out)]) == 0
    assert os.path.getsize(str(out)) > 0


def test_converts_into_an_outdir_that_does_not_exist_yet(tmp_path):
    outdir = tmp_path / "made-on-demand"
    assert main([_sample(), "--outdir", str(outdir)]) == 0
    assert len(os.listdir(str(outdir))) == 1


def test_missing_input_is_a_per_file_failure_not_a_usage_error(tmp_path):
    out = tmp_path / "out.hwpx"
    assert main(["does-not-exist.hwp", "-o", str(out)]) == 1


def test_failure_message_names_the_input(tmp_path, capsys):
    main(["does-not-exist.hwp", "-o", str(tmp_path / "out.hwpx")])
    assert "does-not-exist.hwp" in capsys.readouterr().err


def test_quiet_suppresses_the_failure_message_but_not_the_exit_code(tmp_path, capsys):
    rc = main(["-q", "does-not-exist.hwp", "-o", str(tmp_path / "out.hwpx")])
    assert rc == 1
    assert capsys.readouterr().err == ""


def test_success_is_silent(tmp_path, capsys):
    main([_sample(), "-o", str(tmp_path / "out.hwpx")])
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_skipping_an_existing_output_exits_zero(tmp_path):
    out = tmp_path / "out.hwpx"
    out.write_bytes(b"already here")
    assert main([_sample(), "-o", str(out)]) == 0
    assert out.read_bytes() == b"already here"


def test_force_overwrites_an_existing_output(tmp_path):
    out = tmp_path / "out.hwpx"
    out.write_bytes(b"already here")
    assert main([_sample(), "-o", str(out), "--force"]) == 0
    assert out.read_bytes() != b"already here"


def test_force_without_an_explicit_destination_is_a_usage_error(tmp_path):
    # The V1 gate.
    with pytest.raises(SystemExit) as exc:
        main([_sample(), "--force"])
    assert exc.value.code == 2


def test_o_with_several_inputs_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([_sample(), _sample(), "-o", "out.hwpx"])
    assert exc.value.code == 2


def test_json_flag_does_not_swallow_a_positional_input(tmp_path):
    # The V3 gate: with an optional-valued --json, argparse binds the first
    # positional to the flag and silently drops it from the run.
    report = tmp_path / "report.json"
    rc = main(["--json", str(report), "does-not-exist-1.hwp",
               "does-not-exist-2.hwp", "--outdir", str(tmp_path)])
    assert rc == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert [f["input"] for f in data["files"]] == [
        "does-not-exist-1.hwp", "does-not-exist-2.hwp"]


def test_json_report_records_counts_and_per_file_status(tmp_path):
    report = tmp_path / "report.json"
    rc = main([_sample(), "does-not-exist.hwp", "--outdir", str(tmp_path),
               "--json", str(report)])
    assert rc == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["counts"] == {"converted": 1, "overwritten": 0,
                              "skipped": 0, "failed": 1}
    assert {f["ok"] for f in data["files"]} == {True, False}


def test_json_to_stdout(tmp_path, capsys):
    main([_sample(), "--outdir", str(tmp_path), "--json", "-"])
    assert json.loads(capsys.readouterr().out)["counts"]["converted"] == 1


def test_verbose_reports_each_file_and_a_summary(tmp_path, capsys):
    main(["-v", _sample(), "--outdir", str(tmp_path)])
    err = capsys.readouterr().err
    assert "converted 1" in err


def test_version_prints_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() != ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: many failures — the current `main` requires `-o`, rejects multiple inputs, and knows nothing about `--outdir`, `--force`, `--json`, `-q`, `-v`, or `--version`.

- [ ] **Step 3: Write the CLI**

Replace the entire contents of `hwp2hwpx/cli.py` with:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: 15 passed.

- [ ] **Step 5: Verify no sample filename leaked into committed files**

Sample filenames must never appear in committed files, so check for the shape of
the mistake rather than for the names themselves: any `samples/...` path that is
a literal filename instead of a prefix glob.

Run: `rg -n 'samples/[^"'"'"'*]*\.hwp' tests/test_cli.py hwp2hwpx/ ; echo "exit=$?"`

Expected: `exit=1` (no matches). Every legitimate reference looks like
`glob.glob("samples/3.*.hwp")[0]` and contains a `*`, so it will not match.

The check is deliberately scoped to the files this plan touches. Roughly twenty
*other* test modules hardcode sample filenames the same way — a pre-existing,
repo-wide breach that predates this work and is tracked separately. Do not widen
this gate to `tests/`; it will fail on files you did not touch.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q` (timeout 420000 ms)
Expected: all pass. `tests/test_parse_once.py::test_output_matches_golden` must pass, not skip.

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/cli.py tests/test_cli.py
git commit -m "feat: batch inputs, outdir, force, JSON report and exit codes in the CLI

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Document the CLI in the README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the finished CLI surface from Task 3.
- Produces: nothing other tasks depend on. This is the last task.

- [ ] **Step 1: Read the current README**

Run: `cat README.md`

Note its existing heading style, tone, and whether a usage section already exists. Match that style rather than imposing a new one.

- [ ] **Step 2: Add or replace the usage section**

Add a `## Usage` section (replacing any existing one) containing exactly this synopsis, exit-code table, and examples. Do not invent flags beyond these.

````markdown
## Usage

```
hwp2hwpx [-o FILE | --outdir DIR] [--force] [--json FILE]
         [-q | -v] [--version] INPUT [INPUT ...]
```

Convert one document, naming the output:

```
hwp2hwpx report.hwp -o report.hwpx
```

Convert many, writing them beside their inputs (existing outputs are skipped):

```
hwp2hwpx docs/*.hwp
```

Convert many into one directory, overwriting what is already there:

```
hwp2hwpx docs/*.hwp --outdir out/ --force
```

Options:

- `-o FILE` — output path; valid with exactly one input.
- `--outdir DIR` — directory to write outputs into; created if absent.
- With neither, each output lands beside its input as `<name>.hwpx`.
- `--force` — overwrite existing outputs. Requires `-o` or `--outdir`, so that
  overwriting a directory of documents in place has to be asked for by name.
- `--json FILE` — write a machine-readable report (`-` for stdout) with per-file
  status and counts.
- `-q` — suppress per-failure messages; `-v` — report every file and a summary.

Existing outputs are skipped rather than overwritten, so a large batch can be
re-run cheaply. Failures do not stop the run: every input is attempted.

Exit codes:

| code | meaning |
|------|---------|
| 0 | no failures (skipped files are not failures) |
| 1 | one or more files failed to convert |
| 2 | usage error |
````

- [ ] **Step 3: Verify the documented surface matches the implementation**

Run: `.venv/bin/python -m hwp2hwpx.cli --help 2>&1 || .venv/bin/python -c "from hwp2hwpx.cli import _build_parser; _build_parser().print_help()"`

Expected: every flag in the README section above appears in the help output, and the help output contains no flag the README omits.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document the batch CLI surface and exit codes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage.** Command surface → Task 3. `--json` mandatory value (V3) → Task 3 Steps 1/3, gated by `test_json_flag_does_not_swallow_a_positional_input`. Atomic writes (V2) → Task 1. Overwrite policy and `--force` requiring an explicit destination (V1) → Task 2 (`plan_jobs`) with the CLI gate in Task 3. Exit contract 0/1/2 → Task 3, including "all skipped exits 0". Architecture (`runner.py` + thin `cli.py`) → Tasks 2 and 3. Error handling (usage errors before any conversion; per-file isolation; missing input is a per-file failure; no traceback) → Tasks 2 and 3. JSON report shape → Task 3. Samples-privacy fix → Task 3, verified by the grep in Step 5. README → Task 4. Non-goals (parallelism, directory walking, progress bars) have no tasks, correctly.

**Placeholder scan.** No TBDs; every code step carries complete code; every command has an expected result.

**Type consistency.** `Result` is constructed in Task 2 with six fields in the order `input output action ok error error_type` and consumed in Task 3 by those same names. `plan_jobs`'s keyword names (`out_file`, `outdir`, `force`) match the call in Task 3. `action` values `{"convert", "skip", "overwrite"}` are produced in Task 2 and branched on in `_counts` in Task 3. `UsageError` is raised in Task 2 and caught in Task 3.
