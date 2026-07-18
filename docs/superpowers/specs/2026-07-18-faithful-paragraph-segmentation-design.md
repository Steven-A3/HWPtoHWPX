# Faithful Paragraph Segmentation — Design

**Goal:** Rebuild the reader's paragraph run/`<t>` segmentation from the raw
`HWPTAG_PARA_CHAR_SHAPE` char-position array so that every paragraph's run
grouping, char-shape assignment, and `<t>` structure matches Hancom's own
`.hwpx` export.

**Status:** design derived and de-risked through a Phase-0 baseline and a Phase-1
ground-truth census (all rules, char-widths, and the correlation mechanism are
verified against the three sample documents).

---

## Problem

`hwp5proc xml` (the reader's current sole data source) attributes a
`charshape-id` to every `Text` and `ControlChar`, but reports **`cs=None`** for
table/drawing controls (`TableControl`, `GShapeObjectControl`) and never surfaces
the char-shape at object or paragraph-break positions. The current
`parse_paragraph` therefore:

- puts every inline object in its own run with `char_shape_id=0`, and
- emits ad-hoc trailing empty `<t/>` "anchors" (`_run_has_inline_object`).

Hancom instead groups objects into the run defined by the **char-shape stored at
their char position**, and its `<t>` structure falls out of a char-position walk.
This mismatch produces both the 2013 sample's missing runs/`<t>` and samples 3 &
4's score-neutral *over*-emission.

## Root cause (verified)

The char-shape at every position — text, control, object, paragraph-break — is in
the `HWPTAG_PARA_CHAR_SHAPE` record, exposed cleanly by `hwp5proc models
<path> BodyText/SectionN` as a parsed `charshapes` array of `[position,
charshape-id]` pairs. Hancom uses exactly this array. Examples (verified to
reproduce Hancom's exact run/`<t>` structure):

| Para | Raw char-shape array | Faithful output = Hancom |
|------|---------------------|--------------------------|
| 2013 #192 | `[[0,46],[8,141]]` | `[46: tbl][141: <t/>]` |
| S4 #336 | `[[0,157],[16,19]]` | `[157: tbl,line][19: <t/>]` |
| S4 #337 | `[[0,79],[71,19]]` | `[79: tbl,tbl,line×5,<t>][19: <t/>]` |
| 2013 #361 | `[[0,106]]` | `[106: rect,rect,rect,pic,<t/>]` |

## Char-width model (verified: 0 mismatches / 1,856 items on samples 3 & 4)

To map array positions onto `LineSeg` items, each item's char-width in WCHARs:

- **Text:** UTF-16 code-unit count — `sum(2 if ord(c) > 0xFFFF else 1 for c in s)`.
- **ControlChar** (TAB, LINE_BREAK, PARAGRAPH_BREAK, FIXWIDTH_SPACE, …): **1**.
- **Objects / extended controls** (`TableControl`, `GShapeObjectControl`,
  `ColumnsDef`, `PageNumberPosition`, `PageHide`, `NewNumbering`,
  `BookmarkControl`): **8**.

A per-paragraph **consistency check** validates alignment: for each Text/CC item
(which carries a known `charshape-id`), the char-shape looked up in the array at
the item's computed position MUST equal that `charshape-id`. This holds for every
item in samples 3 & 4 and every item in 2013 except the 7 category-A items below.

## The segmentation rule (the HWP binary model)

1. Reconstruct the paragraph as an ordered char-position stream; assign every
   item its char-shape — Text/CC from `hwp5proc`, **objects from the array** at
   the item's computed position.
2. **Runs** = maximal consecutive spans of items sharing a char-shape (objects
   included). The paragraph-break's position char-shape terminates the stream;
   when it differs from the preceding span it forms its own run.
3. **Within a run**, serialize a `<t>` for each maximal span of text/inline-
   controls; emit objects inline between `<t>` segments. An empty span (a
   trailing object with no following text, or a break-only run) yields an empty
   `<t/>`. The empty-`<t/>` is *not* a special anchor — it is an empty text span.

## Scope

**In (all score-visible deltas):** object char-shape assignment and run grouping
(categories B/C of the census — ~20 of 24 divergent paragraphs; every
score-affecting `run`/`t` delta).

**Out — category A** (2013 paras 145, 149, 153, 215, 259, 279; bullet-glyph
`3…` paragraphs): `hwp5proc`'s xml char-shape attribution itself diverges
from the raw array here (the 7 consistency-check mismatches). Rebuilding from the
array *may* incidentally move these toward Hancom, but the effect is
**score-neutral** (same total `<t>` count) and not a target. The score-floor gate
governs; no special-casing.

**Out — para-751 drawing internals** (`scaMatrix`/`rotMatrix`/`shapeComment`): a
separate drawing-mapping issue, unrelated to char-shape segmentation.

## Architecture

- **`hwp2hwpx/hwpmodel/reader.py`**
  - New: `hwp5_char_shapes(hwp_path)` runs `hwp5proc models <path>
    BodyText/SectionN` for each section, parses the JSON array, and returns the
    per-paragraph `charshapes` arrays in document (depth-first pre-order) order —
    the same order `parse_paragraph` is invoked (top-level then nested cell/textbox
    paragraphs).
  - New: a char-position resolver that, given a paragraph's `LineSeg` items and
    its char-shape array, computes item positions (width model) and returns each
    item's resolved char-shape, running the consistency check.
  - Rewrite `parse_paragraph` to build runs from the resolved char-position
    stream per the segmentation rule. It now takes the paragraph's char-shape
    array as a parameter.
  - `read_document` threads the document-order array list into every
    `parse_paragraph` call (top-level via `ColumnSet`, nested via table cells and
    textbox paragraph lists), by a shared sequential cursor.

- **`hwp2hwpx/hwpmodel/model.py` — the key model change:** an `HwpRun` must hold
  an **ordered, interleaved list of items** (text segments, inline controls, and
  **multiple** objects) rather than the current single `table`/`drawing` fields.
  Para #361 requires one run containing 3 rects + 1 pic + a text segment.

- **`hwp2hwpx/mapper/body.py`:** `map_paragraph` maps the new interleaved run
  contents to OWPML `Run` contents (text/control/object items in order).

- **`hwp2hwpx/owpml/section_writer.py`:** `_write_run` emits the interleaved
  structure directly (text spans as `<t>`, objects inline, empty spans as `<t/>`);
  the `_run_has_inline_object` anchor heuristic is removed — the empty `<t/>` now
  comes from the model.

## Testing & gates (both mandatory, per Phase-0/1 discipline)

- **Structural regression harness** (`tests/`): for every top-level paragraph in
  all three samples, assert our run / `<t>` (empty vs non-empty) / object-sequence
  structure matches Hancom's reference `.hwpx`. Target: zero divergence on the
  score-visible categories; category-A residuals explicitly listed and allowed.
- **Score-floor gate** (Invariant 1): no per-part fidelity score may decrease on
  any sample. Samples 3 & 4 section0 stay ≥ 1.0000; 2013 section0 must not drop.
- **Width-model consistency test:** the per-item char-shape check across all
  samples (0 mismatches on 3 & 4; exactly the 7 known category-A items on 2013).
- **Exact-serialization unit tests** for representative paragraphs (#192, #336,
  #337, #361) — byte-exact run/`<t>` structure vs Hancom.

## Non-goals

- Category-A bullet-glyph `<t>` emptying (score-neutral, unexplained Hancom quirk).
- Para-751 drawing internals (`scaMatrix`/`shapeComment`).
- `substFont` (documented project non-goal).

## Value (stated plainly)

Score-visible gain is ~2013 section0 0.9982 → ~0.999 (sub-0.2% on one file);
samples 3 & 4 stay 1.0000, now *structurally* faithful rather than green via
score-neutral slack. The durable value is a correct, general segmentation model
robust on unseen documents.
