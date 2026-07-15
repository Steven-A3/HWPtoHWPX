# HWP → HWPX Converter — Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)

## Goal

Build a **pure-Python** command-line tool that converts legacy **HWP** (Hancom Word Processor binary, v5.0) files into **HWPX** (OWPML, KS X 6101) files, targeting **maximum fidelity** to the output Hancom Office itself produces.

Success = for a given `.hwp`, our `.hwpx` structurally matches the `.hwpx` Hancom produces from the same file as closely as possible, and opens cleanly in Hancom Office.

## Background

- **HWP 5.0** is a *binary* format: an OLE2/CFB compound file whose streams are zlib-compressed record sequences. Publicly documented ("한글문서파일형식 5.0"); **pyhwp** implements a working reader.
- **HWPX** is a *ZIP + XML* package following the OWPML standard (KS X 6101). Documented; **hwpxlib** (Java) and the `HWPX-CLAUDE-SKILL` repo are concrete references for the exact XML and packaging rules.
- **hwp2hwpx** (neolord0, Apache-2.0, Java) is the canonical open-source converter, built on `hwplib` (read HWP) + `hwpxlib` (write HWPX). Its element-by-element mapping is our reference to port.

The linked `Steven-A3/HWPX-CLAUDE-SKILL` **generates** HWPX from JSON and edits existing HWPX byte-for-byte; it has no HWP-binary reader, so it is a reference for OWPML/packaging only, not for conversion.

## Decisions

- **Language/stack:** Python 3.9+, `lxml` (XML), `pytest` (tests), **`pyhwp`** as the HWP reader dependency.
- **Reader strategy:** Depend on pyhwp first; write our own record parsers only for records pyhwp covers poorly. ("maximum fidelity" will force some of this.)
- **Mapping strategy:** Systematically **port hwp2hwpx's element mappings to Python** as the baseline, then verify/correct against real `.hwp`/`.hwpx` pairs.
- **Test data:** User-provided `.hwp` + Hancom-produced `.hwpx` **pairs** are the ground truth (planned location: `samples/<name>.hwp` + `samples/<name>.hwpx`).

## Architecture

A four-layer pipeline plus a fidelity harness. Each layer has one clear responsibility and a well-defined model boundary.

```
.hwp ─▶ [1 Reader] ─▶ HWP model ─▶ [2 Mapper] ─▶ OWPML model ─▶ [3 Writer] ─▶ .hwpx
                                                                      │
                                    [4 Fidelity harness] ◀── diff ────┘  vs Hancom .hwpx
```

### 1. Reader — `.hwp` → HWP model
- Parse CFB container + zlib record streams (via pyhwp; supplement where needed).
- Produce a normalized in-memory **HWP model** mirroring HWP structure:
  - `DocInfo`: fonts, char shapes, para shapes, styles, border/fills, numbering, bin-data list.
  - `BodyText`: sections → paragraphs → text runs + line segments + controls (tables, pictures, shapes, etc.).
- Depends on: pyhwp, the HWP 5.0 spec.

### 2. Mapper — HWP model → OWPML model
- One module per element type, each independently testable:
  `text`, `charPr`, `paraPr`, `table`, `picture`, `style`, `border_fill`, `numbering`, `header_footer`, `shapes`, …
- Each module ports the corresponding hwp2hwpx mapping and is verified against pairs.
- Depends on: HWP model (in), OWPML model (out). No I/O.

### 3. Writer — OWPML model → `.hwpx` package
- Serialize the OWPML model to the full HWPX ZIP package with correct structure:
  - `mimetype` (`application/hwp+zip`, **STORED/uncompressed, first entry**), `version.xml`,
    `Contents/content.hpf`, `Contents/header.xml`, `Contents/section0.xml…`,
    `BinData/*`, `Preview/*`, `META-INF/container.xml` + `manifest.xml`.
- Follow the ZIP/packaging integrity rules documented in `HWPX-CLAUDE-SKILL` (Hancom verifies package integrity).
- Depends on: OWPML model, `lxml`, `zipfile`.

### 4. Fidelity harness (test tooling)
- For each pair: convert `.hwp` → our `.hwpx`; unzip ours and Hancom's; **normalize** and **structurally diff** the XML per file/element; emit a per-element **match score** and a report of the top mismatches.
- This makes "maximum fidelity" a measurable, prioritizable target and drives TDD order.
- Depends on: Writer output, sample pairs.

### CLI
- `hwp2hwpx input.hwp -o output.hwpx` (single file); directory/batch mode as a later extension.

## Data flow & boundaries

- Reader and Writer are the only layers that touch bytes/files. Mapper is pure model→model (easy to unit-test).
- The two internal models (HWP model, OWPML model) are the stable interfaces; either side can change internals without breaking the other as long as the model contract holds.

## Error handling

- **Unknown/unsupported records:** never abort. Log a structured warning (record id, location), skip or best-effort map, and continue — a partial conversion beats a crash. Track unsupported items so the harness can report coverage.
- **Malformed HWP:** fail fast in the Reader with a clear message (not a stack trace) identifying the offending stream/record.
- **Writer invariants:** assert package rules (mimetype first & stored, required parts present) before finalizing the ZIP; a violation is a hard error.

## Testing strategy (TDD)

- **Unit tests** per Mapper module: hand-built HWP-model fragment → assert expected OWPML fragment.
- **Writer tests:** OWPML model → assert ZIP structure, mimetype rules, well-formed XML.
- **Golden/fidelity tests:** run the harness over `samples/` pairs; track per-element match scores; each fidelity improvement is a new/greener test.
- **Round-trip sanity:** converted `.hwpx` parses back cleanly (well-formed, schema-plausible).

## Scope & sequencing

Maximum fidelity is the asymptote; we approach it in order of document impact:
1. End-to-end skeleton: Reader → empty-ish OWPML → valid `.hwpx` that opens in Hancom.
2. Text runs + char shapes + para shapes (the readable core).
3. Tables (borders, backgrounds, merged cells).
4. Images / bin-data.
5. Styles, numbering, border/fills.
6. Headers/footers, shapes, and long-tail elements — driven by harness scores.

## Non-goals (for now)

- HWPX → HWP (reverse) conversion.
- HWP v3 / older binary formats.
- Lossy bridges (PDF/DOCX/ODT).
- GUI. (CLI first; API/service is a possible later layer.)

## Key risks

- **pyhwp coverage gaps** for full-fidelity records → mitigated by "extend as needed" own-parser strategy.
- **OWPML surface area** is large → mitigated by harness-driven prioritization and porting from a proven mapping (hwp2hwpx).
- **Packaging strictness** (Hancom integrity checks) → mitigated by explicit Writer invariants and testing that output opens in Hancom.
