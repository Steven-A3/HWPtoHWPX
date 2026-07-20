# HWPtoHWPX

A pure-Python converter from **HWP 5.0** (Hancom's legacy binary word-processor
format) to **HWPX** (the OWPML XML-in-ZIP format), targeting high structural
fidelity to the `.hwpx` that Hancom Office itself produces when exporting the
same document.

## Overview

- **HWP 5.0** is Hancom's binary document format: an OLE2/CFB compound file
  whose streams hold zlib-compressed record sequences. It's the native format
  written by older versions of Hancom Office (한글) and remains common for
  Korean government and institutional documents.
- **HWPX** is the modern successor: a ZIP archive of XML parts following the
  OWPML standard (KS X 6101) — conceptually similar to OOXML (`.docx`) or
  ODF (`.odt`).
- This project reads a `.hwp` file, builds an in-memory model of its content
  and formatting, maps that model to the OWPML equivalent, and writes out a
  well-formed `.hwpx` package — without going through Hancom Office itself.

## Architecture

Conversion is a four-layer pipeline plus a fidelity harness used to drive
development and measure output quality:

```
.hwp ─▶ [Reader] ─▶ HWP model ─▶ [Mapper] ─▶ OWPML model ─▶ [Writer] ─▶ .hwpx
                                                                 │
                                    [Fidelity harness] ◀── diff ─┘  vs Hancom .hwpx
```

- **Reader** (`hwp2hwpx/hwpmodel/`) — Parses the `.hwp` binary in-process via
  pyhwp's `Hwp5File` API: `hwpmodel/source.py`'s `HwpSource` opens the file
  once and memoizes the XML representation of the CFB/record structure,
  embedded binary data, and summary info as each is first requested, with no
  subprocess spawned. Builds a normalized in-memory **HWP model**
  (`hwpmodel/model.py`): fonts, character and paragraph shapes, styles,
  border/fills, numbering, sections, paragraphs, runs, tables, drawings, and
  controls.
- **Mapper** (`hwp2hwpx/mapper/`) — Pure model-to-model translation from the
  HWP model to an **OWPML model** (`owpml/model.py`), with one module per
  concern: `char_pr`, `para_pr`, `border_fill`, `style`, `tab`, `bullet`,
  `numbering`, `section`, `table`, `drawing`, `fonts`, `markpen`,
  `docsettings`, orchestrated by `mapper/body.py`. This layer does no I/O and
  is unit-tested independently of the Reader and Writer.
- **Writer** (`hwp2hwpx/owpml/`) — Serializes the OWPML model into the full
  `.hwpx` ZIP package: `mimetype` (written first and stored uncompressed, as
  Hancom requires), `version.xml`, `settings.xml`,
  `Contents/content.hpf`, `Contents/header.xml`, `Contents/section*.xml`,
  `Preview/PrvText.txt`, `META-INF/container.xml`, `container.rdf`, and
  `manifest.xml`, plus any embedded `BinData/*` items.
- **Fidelity harness** (`hwp2hwpx/fidelity/`) — For a `.hwp`/Hancom-produced
  `.hwpx` pair, unzips both packages, normalizes the XML (`xmlnorm.py`), and
  scores each part by element-tag counts (`diff.py`): the fraction of the
  reference document's elements that our output reproduces, plus a report of
  the most-frequent missing tags. This turns "fidelity" into a measurable,
  prioritizable number that drives development order rather than a
  subjective judgment.

The two in-memory models (HWP model, OWPML model) are the stable interface
between layers — the Reader and Writer can change internally as long as the
model contract holds.

## Installation

Requires **Python 3.9+**. Dependencies (see `pyproject.toml`):

- [`pyhwp`](https://pypi.org/project/pyhwp/) — provides the `Hwp5File` API
  the Reader uses in-process to parse the HWP binary format, and the
  `hwp5proc` CLI used by a handful of test fixtures (not by the Reader).
- [`lxml`](https://pypi.org/project/lxml/) — XML construction and parsing.
- `six` — an undeclared runtime dependency of pyhwp.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the `hwp2hwpx` package in editable mode along with its
dependencies, and puts both the `hwp2hwpx` and `hwp5proc` executables on
`PATH` inside the virtualenv.

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

### As a library

```python
from hwp2hwpx.convert import convert

convert("input.hwp", "output.hwpx")
```

`convert()` runs the full Reader → Mapper → Writer pipeline and writes the
resulting `.hwpx` package to `out_path`.

## Testing

```bash
pip install -e ".[dev]"
python -m pytest
```

`hwp5proc` (from pyhwp) must be resolvable on `PATH` to run the **tests** —
several of them compare the in-process reader against the `hwp5proc` CLI as an
independent oracle. Conversion itself never invokes it; the Reader works
entirely in-process. Tests look for the binary next to the current Python
interpreter first, then fall back to `PATH`.
The suite currently has around 560 tests, covering the Reader, each Mapper
module, the Writer/packaging layer, and fidelity scoring against sample
document pairs. `.hwp`/Hancom-produced `.hwpx` pairs used as ground truth
for fidelity tests live under `samples/`. One pair, `samples/test_document.*`,
is a document authored for this project with no confidential content, and is
committed to the repository; it backs the public-fixture tests
(`tests/test_public_fixture.py`) and is the only sample CI can see. The rest
of `samples/` is a private corpus of real government documents, is
git-ignored, and is not included in this repository; tests that need it skip
automatically when it's absent (see `tests/conftest.py`), so it is not
required to run the non-fidelity-comparison parts of the suite.

## Fidelity approach and limitations

Fidelity is measured structurally, not visually: for each `.hwpx` part
(`header.xml`, each `section*.xml`), the harness counts occurrences of each
XML element tag in our output versus Hancom's own export of the same source
document, and reports the fraction matched plus the top missing tags. This
prioritizes development on the highest-impact gaps rather than chasing
perfect byte-for-byte output.

Known, deliberate non-goals (documented in the project's design notes):

- **`substFont`** — Hancom's runtime font-substitution metadata, computed by
  the installed font environment at export time. It cannot be reconstructed
  purely from the source `.hwp` file and is not attempted.
- A handful of other narrow, low-frequency elements are tracked as
  out-of-scope per milestone as they're identified; see the fidelity report
  output and `docs/` for the current state of each area.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).

This project reads HWP files with [pyhwp](https://github.com/mete0r/pyhwp),
which is AGPL-3.0-or-later, and imports it in-process rather than invoking it
as a separate program. The combined work is therefore distributed under the
same terms. Note that the AGPL's section 13 obliges you to offer source to
users who interact with a modified version over a network.

## Status

Actively developed, feature by feature. Implemented or in progress: text
runs and character formatting, paragraph properties, tables, styles, tabs,
bullets/numbering, border/fills, drawing objects (lines, pictures), page and
section settings, document/package metadata, and highlight ("mark pen")
formatting. See `docs/` for design notes and implementation plans per
feature area.

## Releasing

Not yet published to PyPI. When it is, a release is:

```bash
# 1. bump `version` in pyproject.toml (semantic; 0.x = output format may shift)
# 2. commit the bump, then:
git tag v$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```
