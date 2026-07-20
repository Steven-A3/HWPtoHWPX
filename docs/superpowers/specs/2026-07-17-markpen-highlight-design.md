# HWP → HWPX Converter — Text Highlighter (markpen) Design

**Date:** 2026-07-17
**Status:** Approved (design confirmed by user)
**Builds on:** milestones 1..13 (through header doc-settings), all merged to `main`.

## Goal

Emit the text-highlighter (형광펜 / markpen) inline markers Hancom writes as
`<hp:markpenBegin color="…"/>` … `<hp:markpenEnd/>` inside `<hp:t>`. These are
stored in HWP as paragraph **range-tag** records; today the reader (which is
100% `hwp5proc xml`-driven) never sees them, so both samples miss every markpen.

**Success** = the markpen markers appear in `section0.xml` on sample 4 at the
correct character offsets and colors, matching Hancom's export element-for-element
(`markpenBegin`×5, `markpenEnd`×5); sample 3 (no markpen) is byte-unchanged;
output still opens in Hancom Office.

## Verified ground truth

Markpen is an HWP **RangeTag** (`HWPTAG_PARA_RANGE_TAG`, pyhwp `ParaRangeTag`).
Each `RangeTag` struct carries `start`, `end` (UINT32 paragraph-relative char
positions) and a `tag` flags field splitting into `kind` (bits 24–31) and `data`
(bits 0–23).

Measured on sample 4, section 0 (10 range tags total):

| kind | count | meaning | Hancom emits |
|---|---|---|---|
| `2` | 5 | **markpen highlight**; `data` = RGB color (`0xFFFFFF` = white) | `markpenBegin`/`markpenEnd` |
| `0` | 5 | other range tag, whole-paragraph spans (`start=0`, `end=len`) | nothing → **non-goal** |

Sample 3, section 0: **zero** `kind=2` range tags (verified) → no markpen output.

OWPML shape (verified in Hancom's `section0.xml`), markers **inside** one `<hp:t>`:
```xml
<hp:run charPrIDRef="96"><hp:t>(body text), <hp:markpenBegin color="#FFFFFF"/>(highlighted body text)<hp:markpenEnd/></hp:t></hp:run>
```
`start=16` was verified to land exactly before the highlighted text by
counting UTF-16 code units from the paragraph start (the preceding text,
including its numbered-list marker, is 16 units).

### Paragraph correlation (binmodel ↔ parsed tree)

The binmodel stream (`Hwp5File.bodytext[section]`) yields 950 `Paragraph`
records in **depth-first document order** — `level=0` for section paragraphs,
`level≥2` for table-cell paragraphs — the *same* order the reader already parses
paragraphs (top-level, recursing into table cells inside `parse_paragraph`). A
`ParaRangeTag` record belongs to the most-recent `Paragraph` record and precedes
that paragraph's nested cell paragraphs. So a **global depth-first paragraph
index** links range tags to parsed `HwpParagraph`s with no fuzzy/text matching.

## Architecture (extends the 4 layers)

**Model (`hwpmodel/model.py`):**
- `HwpRangeTag(start: int, end: int, color: str)` — one `kind=2` markpen span;
  `color` is `"#RRGGBB"` upper-hex from `data`.
- `HwpParagraph` gains `markpens: list = field(default_factory=list)` (empty for
  the overwhelming majority of paragraphs).

**OWPML model (`owpml/model.py`):**
- `MarkpenBegin(color: str)` and `MarkpenEnd()` — inline items that live in
  `Run.texts` alongside `Text` and `Control`.

**Reader (`hwpmodel/rangetags.py`, NEW; wired from `convert.py`):**
- `attach_range_tags(hwp_path, hwp_doc)` opens `Hwp5File(hwp_path)`, and for each
  bodytext section walks `stream.models()` in order, maintaining a per-section
  DFS paragraph counter (incremented on each `Paragraph` record). For every
  `ParaRangeTag`, keeps only `kind==2` entries as `HwpRangeTag(start, end,
  color)`, bucketed by the current paragraph index.
- A per-section DFS flattening of the parsed `hwp_doc.sections[i].paragraphs`
  (recursing into table cells, in `parse_paragraph`'s recursion order) yields the
  parsed paragraphs in the same index order; assign each paragraph's markpens.
- Defensive: if binmodel read fails, or counts disagree, attach nothing and leave
  every `markpens` empty (never crash, never mis-assign). Called from `convert`
  after `read_document`, mirroring `extract_bin_items`.

**Mapper (`mapper/markpen.py`, NEW; called from `mapper/body.py`):**
- After a paragraph's OWPML `Run`s are built, `apply_markpens(runs, markpens)`
  injects `MarkpenBegin`/`MarkpenEnd` items into the runs' `texts`, tracking a
  cumulative char offset across runs (a `Text`'s content contributes its
  code-unit length; a `Control` contributes 1). A `MarkpenBegin(color)` is
  inserted at offset `start`, a `MarkpenEnd()` at offset `end`, splitting the
  containing `Text` item when a boundary falls mid-string.
- Scope guard: `apply_markpens` is a **no-op for any paragraph that contains a
  non-text run** (a run carrying a `table` or `drawing`), because such runs have
  empty OWPML `texts` and their true HWP char-width is not reliably known — so
  offsets past them cannot be trusted. Both samples' markpen paragraphs are pure
  text, so this loses nothing. The marker-placement rule at run boundaries is
  **begin→start of the following run, end→end of the preceding run** (verified
  against Hancom: span2's begin at offset 35 leads the next run rather than
  trailing the previous one); at a same-offset gap, ends precede begins.

**Writer (`owpml/section_writer.py`):**
- In `_write_run`, handle `MarkpenBegin`/`MarkpenEnd` in the `run.texts` loop
  exactly like `Control`: create the `SubElement` (`hp:markpenBegin` with a
  `color` attribute, or `hp:markpenEnd`), and route following text to its `.tail`.

## Character-offset model

HWP range-tag positions count paragraph characters. For markpen paragraphs (text
plus at most simple inline control chars — tab/lineBreak/fwSpace), the offset of
each item = the running sum of prior items' widths, where a `Text` item's width
is `len(content)` (UTF-16 code units; equal to Python `len` for BMP text) and a
`Control` item's width is `1`. Verified against the observed `start=16`.

**Color:** `color = "#%06X" % data`. Both samples' markpen `data` is `0xFFFFFF`
(white), which is byte-order-symmetric, so the RGB-vs-BGR byte order for a
non-white highlight is **unverified**; `data` is passed straight through (matches
every observed case). If a future colored sample reveals a swap, it is a
one-line fix isolated here.

## Error handling

- Missing / unreadable range-tag records → all `markpens` empty → no markers
  emitted, output identical to today. Never crash.
- Paragraph-count mismatch between binmodel and parsed tree for a section → skip
  that section's range tags entirely (fail safe, not partial mis-assignment).
- Unknown `kind` (≠2) → ignored.
- Markpen span whose boundary falls inside a table/drawing run, or outside the
  paragraph's text length → skip that span, record it; never emit a marker at the
  wrong place.

## Testing strategy (TDD)

- **Model:** `HwpRangeTag` holds start/end/color; `HwpParagraph.markpens`
  defaults to an independent empty list (mutable-default check).
- **Reader (`rangetags`):** a synthetic/binmodel-backed check that sample 4 yields
  exactly 5 `kind=2` spans with color `#FFFFFF`, attached to the paragraphs whose
  assembled run text contains the highlighted phrases; `kind=0` tags are dropped;
  sample 3 yields zero. A paragraph-count-mismatch input attaches nothing.
- **Mapper (`apply_markpens`):** unit tests on hand-built runs — a boundary
  mid-`Text` splits it and inserts the marker at the exact position; a boundary at
  a run edge inserts between runs; a `Control` counts as width 1; a span crossing
  a table/drawing run is skipped (no marker emitted).
- **Writer:** `_write_run` emits `<hp:markpenBegin color="#FFFFFF"/>` and
  `<hp:markpenEnd/>` as `hp`-namespaced children of `hp:t`, with text correctly
  landing on `.text`/`.tail` around them.
- **End-to-end / fidelity:**
  - Sample 4: the six markpen phrases each carry `markpenBegin`/`markpenEnd`;
    `markpenBegin`×5 and `markpenEnd`×5 leave the `section0.xml` miss list;
    an **exact** assertion that at least one known highlighted `<hp:t>` matches
    Hancom's serialization for that run (marker at the right offset, right color)
    — counts alone can't catch a misplaced marker; `section0.xml` match rises to
    ≥ 0.992.
  - Sample 3: `section0.xml` **byte-identical** to pre-milestone output
    (no-change guard); full regression green.

## Non-goals

- `kind=0` (and any non-2) range tags — Hancom emits nothing for them here.
- Markpen spans crossing table/drawing runs — none in the samples; skipped safely.
- The separate `run`/`t` split gap (charPr-driven, ~57 elements) — different cause,
  separate milestone.
- Reproducing markpen when the color is a non-`#FFFFFF` value beyond passing
  `data` through — the pass-through handles any color; no special-casing.

## Key risks

- **Char-offset counting must match HWP's position model** — mitigated by scoping
  to text + simple inline-control runs (the only samples' case), the width model
  above, and the exact-offset end-to-end assertion (not just element counts).
- **Binmodel↔tree paragraph correlation** — mitigated by the DFS index alignment
  (both sources are DFS, both count 950), a per-section count-equality guard that
  fails safe, and reader tests asserting attachment to the right paragraphs.
- **New binmodel data path** — first reader code not driven by `hwp5proc xml`;
  isolated in its own module, called defensively from `convert`, and a no-op when
  a document has no `kind=2` range tags (so sample 3 and every prior test are
  unaffected).
