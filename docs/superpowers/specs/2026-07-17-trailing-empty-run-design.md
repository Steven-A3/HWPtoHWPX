# HWP → HWPX Converter — Trailing Empty Run (paragraph-mark char shape) Design

**Date:** 2026-07-17
**Status:** Approved (design confirmed by user)
**Builds on:** milestones 1..14 (through markpen), all merged to `main`.

## Goal

Emit the trailing empty `<hp:run>` Hancom writes for a paragraph's *mark* (the
paragraph-break) character shape, when that shape differs from the last visible
run's shape. Our reader groups runs by the char shape of visible text and drops
the paragraph break, so we never produce this final empty run — leaving us short
~36 runs on sample 4 (and ~4 on sample 3) in `section0.xml`.

**Success** = for every non-empty paragraph whose paragraph-mark char shape
differs from its last visible run, we append one empty `<hp:run charPrIDRef=X/>`
(bare, no `<hp:t>`), matching Hancom; `section0.xml` `run`-count gap closes on
both samples; output still opens in Hancom Office.

## Verified ground truth

Hancom emits **one `<hp:run>` per `ParaCharShape` segment**. Validated across all
950 sample-4 paragraphs: for text paragraphs, `run count == charshape-segment
count` in **564/565** (the one exception is the section's first paragraph, which
carries an extra `secPr` run — out of scope, already handled).

The last `ParaCharShape` entry is the paragraph mark's char shape, at the mark
character position (after all text). When it differs from the preceding
(last-visible) segment's shape it forms a distinct trailing segment → an **empty**
run (the mark carries no visible text). This shape equals the `PARAGRAPH_BREAK`
control char's `charshape-id` in pyhwp's XML dump (verified: a known
single-word paragraph in sample 4 has
`<ControlChar name="PARAGRAPH_BREAK" charshape-id="34"/>` and Hancom emits a
trailing `<hp:run charPrIDRef="34"/>`). So the mark shape is reachable from the
XML the reader already parses — **no binmodel path required**.

Hancom's trailing empty run serializes as a **bare** `<hp:run charPrIDRef="34"/>`
with no `<hp:t>` child (measured: 398 bare empty runs vs 4 with an empty `<hp:t>`
across sample 4). Our writer already serializes a texts-less run as exactly that
bare form.

### Measured effect (end-to-end prototype of the rule)

| | before | after | note |
|---|---|---|---|
| sample 4 `section0` match | 0.9924 | **0.9963** | empty-run gap 36 → −2 |
| sample 3 `section0` match | 0.9932 | **0.9937** | empty-run gap 4 → 0 |

The sample-4 −2 is a harmless 2-paragraph over-emission (we append a trailing
empty run where Hancom did not, in 2 of 950 paragraphs). It is **score-neutral**
(fidelity scores `min(ours, theirs)` per tag, so extra runs never lower the
score) and left as a documented edge; chasing 2 paragraphs is not worth added
complexity.

## The rule

For each parsed paragraph, after building its runs the normal way:
- Let `break_cs` = the `PARAGRAPH_BREAK` control char's `charshape-id` (int), or
  `None` if the paragraph has no paragraph-break char shape.
- Let `last_cs` = the char shape of the **last run that has visible contents**
  (a run whose `contents` is non-empty), or `None` if the paragraph has no such
  run (e.g. an empty paragraph, or one ending in a table/drawing run).
- If `break_cs is not None and last_cs is not None and break_cs != last_cs`,
  append one empty run `HwpRun(char_shape_id=break_cs, contents=[])`.

This is exactly the "run-per-charshape-segment" rule for the trailing mark
segment, and never fires for empty paragraphs (which already emit their single
run via the existing fallback) or table/drawing-terminated paragraphs.

## Architecture (extends the reader only)

**Reader (`hwpmodel/reader.py`, `parse_paragraph`):** while walking
`LineSeg/*`, capture the `PARAGRAPH_BREAK` child's `charshape-id` (currently the
break is dropped via the `kind is None → continue` branch — read its
`charshape-id` before continuing). After the final `flush()`, apply *the rule*:
if `break_cs` differs from the last contents-bearing run's `char_shape_id`,
append `HwpRun(char_shape_id=break_cs, contents=[])`.

No model, mapper, or writer change is needed:
- Mapper `map_paragraph` already maps any `HwpRun` with empty `contents` to
  `Run(char_pr_id=r.char_shape_id, texts=[])`.
- Writer `_write_run` already serializes a texts-less, table-less, drawing-less
  run as a bare `<hp:run charPrIDRef="X"/>`.
- `apply_markpens` (markpen milestone) treats an empty run as width 0 with no
  items and `_has_non_text_run` sees no table/drawing on it, so appending the
  trailing empty run does not disturb markpen offset accounting.

## Char-shape id → charPrIDRef

The mapper passes `HwpRun.char_shape_id` straight to `Run.char_pr_id`
(`charPrIDRef`), and charPr definitions are emitted in document order so the id
is stable. The trailing run therefore carries the mark shape's id verbatim
(verified: id 34 on a known single-word paragraph in sample 4).

## Error handling

- Paragraph with no `PARAGRAPH_BREAK` char shape (`break_cs is None`, e.g. the
  last paragraph of a stream, or a malformed paragraph) → no trailing run.
- Empty paragraph or table/drawing-terminated paragraph (`last_cs is None`) →
  no trailing run (existing behavior preserved; the empty-paragraph fallback run
  is untouched).
- `break_cs == last_cs` → no trailing run (mark shares the last segment).

## Testing strategy (TDD)

- **Reader unit tests** (synthetic `<Paragraph>` XML fed to `parse_paragraph`):
  - text run cs=40 + `PARAGRAPH_BREAK` charshape-id 34 (differs) → a trailing
    `HwpRun(char_shape_id=34, contents=[])` is appended (run count 2).
  - text run cs=40 + `PARAGRAPH_BREAK` charshape-id 40 (same) → no trailing run
    (run count 1).
  - `PARAGRAPH_BREAK` with no `charshape-id` → no trailing run.
  - a paragraph whose only run is a table/drawing run → no trailing run
    (`last_cs is None`).
- **End-to-end / fidelity:**
  - Sample 4: `section0.xml` `run` count matches Hancom to within the documented
    over-emission (`missing.get("run", 0) == 0`; i.e. no *missing* runs); at
    least one known single-word paragraph gains its trailing
    `<hp:run charPrIDRef="34"/>`; `section0.xml` match rises to ≥ 0.996.
  - Sample 3: `section0.xml` `run` miss count is 0; match rises (≥ 0.9937).
- **Regression:** the markpen-era sample-3 byte-identical guard
  (`tests/test_convert_markpen.py::test_sample3_section_unchanged`) must be
  updated — this milestone legitimately changes sample 3's `section0.xml` (adds
  ~4 empty runs). Re-baseline its `len`/`sha256` to the post-milestone bytes, or
  narrow it to assert markpen-specific invariance. The markpen `markpenBegin`/
  `markpenEnd` counts and exact-serialization assertions must remain green.

## Non-goals

- The `t`-element gap (sample 3 ×33, sample 4 ×25) — a *separate* mechanism
  (visible-text runs carrying extra `<hp:t>`), not empty runs. Different
  milestone.
- Leading/mid empty runs (the section's first `secPr` paragraph; rare zero-width
  mid segments) — ≤3 paragraphs, already matched or negligible.
- Eliminating the 2-paragraph sample-4 over-emission — score-neutral, not worth
  the complexity.
- Rebuilding runs from the full `ParaCharShape` segment array (binmodel) — the
  XML `PARAGRAPH_BREAK` char shape captures the only missing (trailing) segment;
  a full rewrite is unnecessary.

## Key risks

- **Over-emission on other documents** — the rule matched Hancom in 564/565
  validated paragraphs; the 2-paragraph sample-4 overshoot is score-neutral. If a
  future document over-emits materially it remains score-neutral (never lowers
  match) and visually harmless (an empty run renders nothing).
- **Interaction with markpen** — the appended empty run has width 0 and no
  table/drawing, so it does not perturb markpen char-offset accounting; the
  markpen end-to-end tests are kept in the regression gate.
- **Sample-3 regression guard churn** — explicitly handled by re-baselining the
  markpen no-change test (documented above), not by weakening it.
