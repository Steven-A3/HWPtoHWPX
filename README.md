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

- **Reader** (`hwp2hwpx/hwpmodel/`) — Parses the `.hwp` binary via pyhwp's
  `hwp5proc` CLI (invoked as a subprocess to dump an XML representation of
  the CFB/record structure, plus `hwp5proc ls`/`cat` for embedded binary
  data and `hwp5proc summaryinfo` for document metadata) and builds a
  normalized in-memory **HWP model** (`hwpmodel/model.py`): fonts, character
  and paragraph shapes, styles, border/fills, numbering, sections,
  paragraphs, runs, tables, drawings, and controls.
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

- [`pyhwp`](https://pypi.org/project/pyhwp/) — provides the `hwp5proc` CLI
  the Reader shells out to, for parsing the HWP binary format.
- [`lxml`](https://pypi.org/project/lxml/) — XML construction and parsing.
- `six` — an undeclared runtime dependency of pyhwp's `hwp5proc`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the `hwp2hwpx` package in editable mode along with its
dependencies, and puts both the `hwp2hwpx` and `hwp5proc` executables on
`PATH` inside the virtualenv.

## Usage

### Command line

```bash
hwp2hwpx input.hwp -o output.hwpx
```

(`hwp2hwpx/cli.py` — `-o`/`--output` is required; the input path must exist.)

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

`hwp5proc` (from pyhwp) must be resolvable on `PATH` — the Reader looks for
it next to the current Python interpreter first, then falls back to `PATH`.
The suite currently has around 400 tests, covering the Reader, each Mapper
module, the Writer/packaging layer, and fidelity scoring against sample
document pairs. Sample `.hwp`/Hancom-produced `.hwpx` pairs used as
ground truth for fidelity tests live under `samples/`, which is git-ignored
and not included in this repository (they are private test documents, not
required to run the non-fidelity-comparison parts of the suite).

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

GPL v3 — see `LICENSE`. This project depends on `pyhwp`, which is licensed
under the GNU GPL v3, so this project is distributed under the same license.

## Status

Actively developed, feature by feature. Implemented or in progress: text
runs and character formatting, paragraph properties, tables, styles, tabs,
bullets/numbering, border/fills, drawing objects (lines, pictures), page and
section settings, document/package metadata, and highlight ("mark pen")
formatting. See `docs/` for design notes and implementation plans per
feature area.
