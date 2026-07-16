# HWP → HWPX Converter — Section Properties (`<hp:secPr>`) Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestones 1 + tables + paraPr + charPr + styles + tabs + section-inline + linesegarray + tail-cleanup, all merged to `main`.

## Goal

Emit the `<hp:secPr>` cluster at the start of `section0.xml` — the ~30-element
block that is entirely absent from our output on **both** samples. Every value
is derived from real HWP section records (not recomputed by Hancom).

The block:
`secPr` + `grid`, `startNum`, `visibility`, `lineNumberShape`, `pagePr`/`margin`,
`footNotePr`, `endNotePr`, three `pageBorderFill`/`offset`, plus the
`ctrl`-wrapped `colPr` and `pageNum`.

**Success** = our `secPr` subtree is **structurally identical** (tag, attributes,
text, ordered children — recursively) to Hancom's on **both** samples;
`colPr` and `pageNum` are emitted `ctrl`-wrapped in paragraph 0; the header
count-based match rises on both; output still opens in Hancom Office.

Projected: s3 section0 98.85% → ~99.8%; s4 section0 96.40% → ~97.6% (the rest of
s4's gap is drawing objects, a separate milestone).

## Why this design is shaped the way it is (the correctness problem)

This environment has **no Hancom Office and no OWPML schema** to validate against.
`secPr` is the element that *defines the section*, so a malformed one is the most
likely thing to make Hancom refuse to open the file. The existing fidelity harness
scores purely by **element count** (`matched = Σ min(our, their)`) — which means it
would report a *higher* score at the exact moment a broken `secPr` made the file
unopenable. The count metric is blind to structural breakage.

Therefore the **primary correctness gate for this milestone is exact subtree
equality against Hancom's own `secPr`**, not the count. Imitating Hancom's output
byte-for-structure is the strongest available proxy for "it opens." The count-based
harness is demoted to a secondary sanity check.

A consequence: every attribute value must match Hancom exactly, so there is **no**
"map enums pragmatically because the count doesn't care" latitude here. Values HWP
carries are mapped from HWP; values Hancom injects that HWP does not store are
emitted as the observed constant and commented as such.

## Verified ground truth (both samples)

Both HWP files contain exactly: 1 `SectionDef`, 1 `PageDef`, 2 `FootnoteShape`,
3 `PageBorderFill`, 1 `ColumnsDef`, 1 `PageNumberPosition`; each produces a single
`section0.xml`. Crucially the two samples **diverge** in secPr values (proving the
mapping is derived, not a copied template constant):

| field | HWP source | sample 3 | sample 4 |
|---|---|---|---|
| `margin left` | `PageDef left-offset` | 7088 | 6000 |
| `margin header` | `PageDef header-offset` | 4252 | 1964 |
| `margin footer` | `PageDef footer-offset` | 4252 | 1436 |
| `margin right` | `PageDef right-offset` | 7088 | 5528 |
| `margin top` | `PageDef top-offset` | 5668 | 4536 |
| `visibility hideFirstEmptyLine` | `SectionDef hide-blank-line` | 0 | 1 |

The exact-subtree gate passes on both only if these are mapped from each file's own
`PageDef`/`SectionDef` — which was confirmed against `hwp5proc xml` output.

### Attribute mapping (verified)

**`secPr`** (from `SectionDef`):
`id=""` (const), `textDirection="HORIZONTAL"` (`text-direction=0`),
`spaceColumns` ← `columnspacing`, `tabStop` ← `defaultTabStops`,
`tabStopVal="4000"` (const — HWP does not store it), `tabStopUnit="HWPUNIT"` (const),
`outlineShapeIDRef` ← `numbering-shape-id`, `memoShapeIDRef="0"` (const),
`textVerticalWidthHead="0"` (const), `masterPageCnt="0"` (const).

**`grid`** (from `SectionDef`): `lineGrid` ← `grid-vertical`,
`charGrid` ← `grid-horizontal`, `wonggojiFormat` ← `squared-manuscript-paper`.

**`startNum`** (from `SectionDef`): `pageStartsOn` ← `pagenum-on-split-section`
(0 → `BOTH`), `page` ← `starting-pagenum`, `pic` ← `starting-picturenum`,
`tbl` ← `starting-tablenum`, `equation` ← `starting-equationnum`.

**`visibility`** (from `SectionDef`): `hideFirstHeader` ← `hide-header`,
`hideFirstFooter` ← `hide-footer`,
`hideFirstMasterPage` ← `show-background-on-first-page-only`,
`border="SHOW_ALL"` (from `hide-border=0`; 1 → `HIDE`),
`fill="SHOW_ALL"` (const in samples), `hideFirstPageNum` ← `hide-pagenumber`,
`hideFirstEmptyLine` ← `hide-blank-line`, `showLineNumber="0"` (const).

**`lineNumberShape`**: `restartType/countBy/distance/startNumber="0"` (const —
no line numbering in samples).

**`pagePr`** (from `PageDef`): `landscape="WIDELY"` (`orientation=portrait`;
`landscape` → `NARROWLY`), `width` ← `width`, `height` ← `height`,
`gutterType="LEFT_ONLY"` (`bookbinding=left`).
**`margin`** (child, from `PageDef`): `header` ← `header-offset`,
`footer` ← `footer-offset`, `gutter` ← `bookbinding-offset`, `left` ← `left-offset`,
`right` ← `right-offset`, `top` ← `top-offset`, `bottom` ← `bottom-offset`.

**`footNotePr` / `endNotePr`** (from the 1st / 2nd `FootnoteShape`), each containing:
- `autoNumFormat`: `type="DIGIT"` (const in samples), `userChar` ← `usersymbol`,
  `prefixChar` ← `prefix`, `suffixChar` ← `suffix`, `supscript="0"` (const).
- `noteLine`: `length` ← `splitter-length`, `type` ← `stroke-type`
  (`solid` → `SOLID`, `none` → `NONE`), `width` ← `width` (`"0.12mm"` → `"0.12 mm"`),
  `color` ← `splitter-color`.
- `noteSpacing`: `betweenNotes` ← `notes-spacing`,
  `belowLine` ← `splitter-margin-bottom`, `aboveLine` ← `splitter-margin-top`.
- `numbering`: `type="CONTINUOUS"` (const in samples), `newNum` ← `starting-number`.
- `placement`: `place` — footnote `EACH_COLUMN`, endnote `END_OF_DOCUMENT`
  (const per note kind in samples), `beneathText="0"` (const).

**`pageBorderFill`** ×3 (from the 3 `PageBorderFill` records):
`type` = `BOTH`/`EVEN`/`ODD` **by index 0/1/2** (see risk below),
`borderFillIDRef` ← `borderfill-id`, `textBorder` ← `relative-to` (`paper` → `PAPER`),
`headerInside` ← `include-header`, `footerInside` ← `include-footer`,
`fillArea` ← `fill` (`paper` → `PAPER`); child **`offset`**: `left/right/top/bottom`
← `margin-left/right/top/bottom`.

**`colPr`** (from `ColumnsDef`, `ctrl`-wrapped): `id=""`, `type="NEWSPAPER"`
(`kind=normal`), `layout="LEFT"` (`direction=l2r`), `colCount` ← `count`,
`sameSz` ← `same-widths`, `sameGap="0"` (const).

**`pageNum`** (from `PageNumberPosition`, `ctrl`-wrapped): `pos="BOTTOM_CENTER"`
(`position=bottom_center`), `formatType="DIGIT"` (`shape=0`), `sideChar` ← `dash`.

## Source locations (verified)

- `SectionDef` is a child of `<BodyText>`; `PageDef`, the two `FootnoteShape`, and
  the three `PageBorderFill` are its direct children; the paragraphs live under
  `SectionDef/ColumnSet/Paragraph`.
- `ColumnsDef` and `PageNumberPosition` are **inside that section's first
  paragraph** (nested under its first `LineSeg` in pyhwp's dump). They are read by
  scanning the first paragraph of **that `SectionDef`'s** subtree — never a global
  `.//` document scan, so controls cannot be pulled from another section.

## Architecture (extends the existing 4 layers)

**Model (`hwpmodel/model.py`):**
- `HwpPageDef(width, height, orientation, bookbinding, bookbinding_offset,
  left_offset, right_offset, top_offset, bottom_offset, header_offset,
  footer_offset)` — ints except `orientation`/`bookbinding` (str).
- `HwpNoteShape(notes_spacing, prefix, suffix, usersymbol, stroke_type,
  line_width, splitter_length, splitter_color, splitter_margin_top,
  splitter_margin_bottom, starting_number)` — `stroke_type` (HWP `stroke-type`,
  e.g. `solid`/`none`) feeds `noteLine type`; `line_width` (HWP `width`, e.g.
  `"0.12mm"`) feeds `noteLine width`; `splitter_length` feeds `noteLine length`.
- `HwpPageBorder(borderfill_id, relative_to, fill, include_header, include_footer,
  margin_left, margin_right, margin_top, margin_bottom)`.
- `HwpColumnsDef(count, kind, direction, same_widths)`.
- `HwpPageNum(position, shape, dash)`.
- `HwpSectionDef(column_spacing, default_tab_stops, text_direction, grid_horizontal,
  grid_vertical, squared_manuscript_paper, numbering_shape_id,
  starting_pagenum, starting_picturenum, starting_tablenum, starting_equationnum,
  pagenum_on_split_section, hide_header, hide_footer, hide_border, hide_pagenumber,
  hide_blank_line, show_background_on_first_page_only,
  page: "HwpPageDef" = None, footnote: "HwpNoteShape" = None,
  endnote: "HwpNoteShape" = None, page_borders: list = field(default_factory=list),
  columns: "HwpColumnsDef" = None, page_num: "HwpPageNum" = None)`.
- `HwpSection` gains `sec_def: "HwpSectionDef" = None`.

**OWPML model (`owpml/model.py`)** — mirrors the target XML with dedicated
dataclasses: `SecPr`, `Grid`, `StartNum`, `Visibility`, `LineNumberShape`,
`PagePr`, `Margin`, `NotePr` (holds `AutoNumFormat`, `NoteLine`, `NoteSpacing`,
`Numbering`, `Placement`), `PageBorderFill` (holds `Offset`), `ColPr`, `PageNum`.
`SecPr` aggregates: `grid`, `start_num`, `visibility`, `line_number_shape`,
`page_pr`, `foot_note_pr`, `end_note_pr`, `page_border_fills: list`, `col_pr`,
`page_num`. `Section` gains `sec_pr: "SecPr" = None`.

(Python 3.9 floor: no `X | None`; use forward-ref-string defaults / `field(default_factory=...)`.)

**Reader (`hwpmodel/reader.py`):** add `_parse_section_def(sec_el)` — parse
`SectionDef` attributes, its child `PageDef`/`FootnoteShape`/`PageBorderFill`, and
scope-scan `sec_el`'s first `ColumnSet/Paragraph` for `ColumnsDef` /
`PageNumberPosition`. Attach as `HwpSection.sec_def`. All fields tolerate absence
(missing record → `None`/empty list, never crash). Wire into `read_document`.

**Mapper (`mapper/section.py`, new):** `map_section_def(hwp_section_def) -> SecPr`.
Maps HWP-derived values to match Hancom exactly (proven by the subtree-diff test);
Hancom-injected constants are emitted verbatim with an inline comment naming them as
constants. `map_section` (in `mapper/body.py` or a thin wrapper) sets `Section.sec_pr`.

**Writer (`owpml/section_writer.py`):** in `section_xml`, when `section.sec_pr` is
set, emit — **for paragraph 0 only** — a leading `<hp:run>` whose first child is the
full `secPr` subtree, followed by `ctrl>colPr` and `ctrl>pageNum` (each emitted only
when present). The normal paragraph runs follow. A dedicated `_write_sec_pr(run_el,
sec_pr)` builds the subtree.

## Structural placement — and why the run layout is NOT asserted exactly

`secPr` must be the first child of the first `<hp:run>` of paragraph 0 (OWPML
requires the section definition to lead the section). That much **is** asserted.

The surrounding run/ctrl arrangement is **content-dependent and differs between the
samples** (verified): sample 3's paragraph 0 splits into `run[secPr, ctrl>colPr]` /
`run[ctrl>pageNum, tbl]`; sample 4's has an extra `run[ctrl>pageHiding]` and carries
text instead of a table. Asserting one exact layout would fail the other sample.
Therefore the milestone asserts:
1. the `secPr` **subtree** is deep-equal to Hancom's (primary gate), and
2. `secPr` is the first run's first child; `colPr` and `pageNum` are present,
   `ctrl`-wrapped, within paragraph 0 —

but **not** the exact number/split of surrounding runs. Emitting `colPr`/`pageNum` in
the same leading run as `secPr` is valid and score-neutral (count is `min(our, their)`).

## Scope and explicit limitations

- **`pageHiding`** (a `ctrl`-wrapped control, `x2` in both miss lists) is a near
  neighbor derived from the same `SectionDef` first-page flags, but it lives in its
  own run with content-dependent placement. It is **out of scope** here to keep the
  subtree-equality gate clean; documented for a follow-up.
- **Multi-section is handled naturally, not silently dropped.** The pipeline
  already supports N sections end to end: `read_document` produces one `HwpSection`
  per `SectionDef`, and `write_hwpx` already loops `for i, section in
  enumerate(doc.sections)` writing `section{i}.xml` (header/manifest/content.hpf
  carry `sec_cnt`). This milestone attaches `sec_def`/`sec_pr` **per section**, so
  each section emits its own `secPr` — multi-section `secPr` falls out for free. The
  earlier "single-section limitation" framing was based on a misread of the writer;
  no warning/guard is needed. The only per-section requirement is that the
  `ColumnsDef`/`PageNumberPosition` scan is scoped to **that section's own** first
  paragraph (never a global `.//` scan), which the reader design already specifies.
- **`substFont`, `subscript`, drawing objects/images, remaining small section items**
  (`autoNumFormat`/`noteLine`/`noteSpacing` already covered inside secPr; `ctrl`
  bodies for header/footer/footnote text) remain out of scope.

## Error handling

- Any missing record (`PageDef`, either `FootnoteShape`, `PageBorderFill`,
  `ColumnsDef`, `PageNumberPosition`) → corresponding model field `None`/empty; the
  writer emits nothing for it (no crash, no fabricated element).
- `pageBorderFill` `type` is assigned by index (`0→BOTH,1→EVEN,2→ODD`) and the writer
  emits **only as many as exist** — it never assumes exactly 3. If a future document
  has 0/1/2 records, it emits 0/1/2 elements with the leading types; correct
  flag-decoding of border page-scope is deferred (cannot be verified without varied
  fixtures — see risks).
- Unknown enum inputs fall back to the Hancom default for that attribute
  (e.g. unknown `orientation` → `WIDELY`), never crash.

## Testing strategy (TDD)

**Primary — exact subtree equality (both samples).** A helper parses Hancom's and
our `secPr` element from each sample's `section0.xml` and asserts deep equality:
tag, attribute dict, text, and **ordered** children, recursively (canonical compare,
not raw string, to avoid attribute-ordering false negatives). This is the correctness
definition for the milestone and stands in for the Hancom open-test we cannot run.

**Structure.** `secPr` is the first child of paragraph 0's first run; `colPr` and
`pageNum` are emitted `ctrl`-wrapped within paragraph 0. (No assertion on the exact
count/split of surrounding runs.)

**Reader (unit).** A known `SectionDef` parses to `HwpSectionDef` with expected
`column_spacing`/`default_tab_stops`/`hide_blank_line`; its `PageDef` yields the
expected `left_offset`; the two `FootnoteShape` map to `footnote`/`endnote`; three
`HwpPageBorder`; `columns`/`page_num` populated from the first paragraph.

**Mapper (unit).** `map_section_def` produces a `SecPr` whose fields equal the
verified target for a constructed `HwpSectionDef`; enum mappings
(`portrait→WIDELY`, `l2r→LEFT`, `normal→NEWSPAPER`, `solid→SOLID`, `none→NONE`,
`bottom_center→BOTTOM_CENTER`) each covered.

**Synthetic absence/breadth (unit) — the paths the two samples cannot reach:**
- 0 `PageBorderFill` records → zero `pageBorderFill` elements (no crash).
- missing `PageNumberPosition` → no `pageNum` emitted.
- `ColumnsDef count=2` → `colPr colCount="2"`.

**Regression + secondary count check.** Full suite green; the count-based harness
`match` rises on both samples' section0 and header (sanity only, not the gate);
`secPr`, `grid`, `pagePr`, `footNotePr`, `endNotePr`, `pageBorderFill`, `colPr`,
`pageNum` leave the miss lists.

**Multi-section correctness.** A test constructs a two-section `HwpDocument`, maps
it, and asserts each `Section` gets its own `sec_pr` from its own `sec_def` (the
pipeline already writes `section0.xml`/`section1.xml`).

## Key risks

- **File-open correctness is unverifiable directly** (no Hancom/schema in this env).
  Mitigated by the exact-subtree-equality gate — imitating Hancom's own output is the
  strongest proxy — plus pinning `secPr` as the first run's first child.
- **`pageBorderFill` type-by-index** is a template-specific assumption (both samples
  have 3 identical records). Mitigated by emitting only as many as exist and
  documenting that page-scope flag-decoding is deferred; a real doc with non-3 records
  gets correct *counts* and leading types, wrong page-scope labels at worst — and
  cannot be validated without a varied fixture.
- **Two-sample generalization** — mitigated by the confirmed value divergence between
  the samples (margins, `hide-blank-line`), which forces genuine derivation, plus the
  synthetic unit tests for absence/breadth.
- **Per-section correctness** — the pipeline already emits N `section{i}.xml`;
  mitigated by per-section-scoped control scanning and per-section `sec_def`/`sec_pr`
  attachment, verified by a two-section mapper test.
- **`secPr` as first run's first child** must not break existing paragraph-0 tests
  (table emission). Mitigated by making the secPr run purely additive (a new leading
  run) and keeping the existing runs unchanged.
