# CLI: batch conversion and a scripting contract — Design

**Goal:** Make `hwp2hwpx` usable from shell scripts, Makefiles, and CI over many
documents at once: multiple inputs, predictable exit codes, quiet-by-default
output, an opt-in machine-readable report, and defaults that cannot destroy data.

**Status:** design derived and adversarially reviewed. Three vulnerabilities were
identified and empirically confirmed against this repo; the design below is the
revision that addresses each (V1/V2/V3, recorded in full).

Sub-project 2 of 3 in the CLI → performance → packaging track. Performance
shipped (see `2026-07-20-parse-once-performance-design.md`); packaging follows.

---

## Problem

`hwp2hwpx/cli.py` today accepts exactly one input and requires `-o`:

```
hwp2hwpx INPUT -o OUTPUT      # exit 0 on success, 1 on any failure
```

Converting a directory means a shell loop, and the caller has no way to learn
which documents failed short of parsing prose from stderr. The primary intended
use is **scripted / piped from other tools**, so exit codes and output discipline
matter more than interactive polish or progress rendering.

## Command surface

```
hwp2hwpx [-o FILE | --outdir DIR] [--force] [--json FILE]
         [-q | -v] [--version] INPUT [INPUT ...]
```

- `INPUT` — one or more `.hwp` paths. The shell performs globbing; the tool does
  not walk directories (no traversal, filtering, or symlink questions).
- `-o FILE` — valid only with exactly one input; a usage error otherwise.
  Backward compatible with today's invocation, but no longer required.
- `--outdir DIR` — output directory for any number of inputs; created if absent.
- Neither given — each output lands beside its input as `<stem>.hwpx`.
- `--force` — overwrite existing outputs. **Only honored together with `-o` or
  `--outdir`** (see V1); with default beside-input naming it is a usage error.
- `--json FILE` — write the machine-readable report to `FILE`; `-` means stdout.
  The value is **mandatory** (see V3).
- `-q` — suppress per-failure messages; the exit code is the only signal.
- `-v` — one line per file (converted / skipped / failed) plus a summary, and the
  exception type on failures. Never a traceback.
- `--version` — print the installed package version and exit 0.

Default verbosity is silent on success: one `error: <input>: <message>` line per
failure on stderr, nothing on stdout. `-q` and `-v` are mutually exclusive, and
neither affects `--json` — the report is written whenever it is requested, so a
quiet run can still be fully machine-readable.

## Overwrite policy and the exit contract

An existing output is **skipped**, not overwritten, unless `--force` is given.
Re-running a large batch therefore resumes cheaply and never destroys data by
accident.

Per-file outcomes are `converted`, `skipped`, `failed`, and — under `--force` —
`overwritten`. The four counts are reported separately so a `--force` run that
clobbered files says so out loud rather than being invisible.

Exit codes:

| code | meaning |
|------|---------|
| 0 | no failures (**skips are not failures**) |
| 1 | one or more files failed to convert |
| 2 | usage error (argparse's own convention; not fought) |

Failures do not stop the run — every input is attempted. A caller needing to
distinguish "everything was skipped" from "everything converted" reads the counts
or `--json`; the exit code deliberately does not encode that distinction.

## Adversarial review (the three most vulnerable points, tested)

### V1 — "`<stem>.hwpx` beside the input is a safe default" — FALSE, REVISED
`.hwp` and `.hwpx` are not a distinct namespace in practice. This repo's
`samples/` holds each source document *and* Hancom's own `.hwpx` export of it
under the same stem — the reference every fidelity test scores against. The
proposed default naming resolves to exactly those reference paths, so
`hwp2hwpx samples/*.hwp --force` would overwrite all four references with our own
output. `samples/` is git-ignored, making the loss unrecoverable, and the fidelity
tests would keep passing while silently comparing our output to itself. This is
the same class of failure as the parse-once milestone's golden-file collision:
derived output landing in a reference namespace. Pairing `X.hwp` with `X.hwpx` is
the natural way any user stores a source beside its reference, so the risk is not
specific to this repo.

**Revision:** skip-existing is the default, and `--force` is honored **only with
an explicit `-o` or `--outdir`**. Overwriting a folder of documents in place now
requires naming that folder deliberately; it cannot happen from a bare glob.

### V2 — "skip-existing is free" — FALSE, REVISED (writer change)
Skipping an existing output is only safe if an existing output implies a
*completed* conversion. It does not: `owpml/writer.py` opens
`zipfile.ZipFile(out_path, "w")` directly on the destination, and mode `"w"`
truncates immediately. An interruption (Ctrl-C in a long batch, disk full, OOM)
leaves a truncated `.hwpx` at the final path, which skip-existing then treats as
done in **every** future run, silently and permanently.

**Revision:** `write_package` builds the zip at a temporary path in the *same
directory* and `os.replace()`s it into position on success, removing the temp on
failure. `os.replace` is atomic within a filesystem, so the destination holds
either a complete document or its previous contents — never a truncated one. This
is a writer change that also benefits the library API. It cannot alter output
bytes (identical zip content, different destination path); the existing
byte-identical golden gate confirms that.

### V3 — "`--json [FILE]` is a tidy optional-value flag" — FALSE, REVISED
argparse resolves an optional-value flag greedily against `nargs="+"`
positionals. Measured:

```
hwp2hwpx --json a.hwp b.hwp  ->  json='a.hwp', input=['b.hwp']   # input silently dropped
hwp2hwpx --json a.hwp        ->  error: the following arguments are required: input
```

The first case is silent: one document vanishes from the run and `a.hwp` is
overwritten with a JSON report. A tool whose premise is trustworthy scripted
behavior cannot silently discard inputs.

**Revision:** `--json` takes a mandatory value, with `-` for stdout. No argv can
then absorb an input.

## Architecture

Two units with a clean seam:

- **`hwp2hwpx/runner.py` (new)**
  - `plan_jobs(inputs, out_file, outdir, force) -> list[Job]` — a **pure function
    over paths**. Resolves each input to its output path, decides
    `convert` / `skip` / `overwrite`, and touches no files beyond existence
    checks. Every naming, arity, and overwrite rule is testable here without
    converting a document.
  - `run_jobs(jobs, on_result) -> list[Result]` — executes each job, isolating
    failures, and reports each `Result` (input, output, action, ok, error) as it
    completes.
- **`hwp2hwpx/cli.py`** — argparse, validation, rendering (text and JSON), exit
  code. Stays thin; holds no conversion or naming logic.

The text summary and the JSON report are rendered from the same `Result` records,
so the two views cannot drift.

- **`hwp2hwpx/owpml/writer.py`** — `write_package` becomes atomic (V2).

## Error handling

- **Usage errors are caught before any conversion begins** (`-o` with multiple
  inputs, `--force` without an explicit destination, an unusable `--outdir`), so
  a bad invocation never half-converts a batch. Exit 2.
- **Per-file failures are isolated.** `convert()` runs inside a try; the exception
  becomes one stderr line and a `failed` record, and the run continues. No
  traceback — under `-v` the exception type is included, which is what a batch log
  needs.
- **A missing input file is a per-file failure, not a usage error**, so one typo
  in a 500-path list does not abort the run.

## JSON report

A single object: the four counts plus a `files` array of per-file records
(`input`, `output`, `action`, `ok`, `error`). Written to the path given, or
stdout for `-`. Stable field names — this is the machine-readable contract.

## Testing

- **Job planning** — default naming, `--outdir`, `-o` arity, skip vs overwrite,
  and `--force` validation, all asserted on paths alone with no conversions.
- **Atomicity (V2 gate)** — force a failure mid-write and assert the destination
  is either absent or still holds its previous content, never truncated.
- **Argparse (V3 gate)** — `--json a.hwp b.hwp` keeps both inputs.
- **Exit codes** — 0, 1, and 2 each asserted, including "all skipped exits 0".
- **`--force` without an explicit destination** is a usage error (V1 gate).
- **Output unchanged** — the existing byte-identical golden gate guards the
  writer change.
- Real conversions appear in only a couple of end-to-end tests: the suite runs in
  ~81 s and each conversion costs ~0.4 s.
- **Samples privacy fix:** `tests/test_cli.py` currently hardcodes one sample's
  full filename in a module-level constant, breaking the rule that committed code
  must not name sample files. It moves to the `glob.glob("samples/3.*.hwp")[0]`
  convention used by the rest of the suite.

## Non-goals

- **Parallelism (`--jobs N`).** Per-conversion cost was just cut ~3×, and a
  process pool would reopen the file-handle and error-attribution questions the
  parse-once review closed. Its own sub-project if throughput still matters.
- **Directory walking / `--recursive`.** The shell globs.
- **Progress bars or spinners.** The use case is scripted; `-v` gives per-file
  lines, which is what a log wants.
- **Config files, `--dry-run`, output templating.** No demonstrated need.
- Any change to conversion output or fidelity behavior.

## Value

Turns a single-file utility into something a script can drive over a corpus: one
invocation for many documents, failures isolated and attributable, an exit code
that means what a caller expects, and defaults that cannot silently destroy a
reference document or resurrect a truncated one.
