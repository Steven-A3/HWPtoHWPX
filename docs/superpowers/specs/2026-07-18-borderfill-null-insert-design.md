# Canonical Null-BorderFill Normalization — Design

**Goal:** Reproduce Hancom's reserved null `borderFill` at id=1 so that a document
whose source first borderFill is not the canonical null (e.g. the 2013 sample)
gains the prepended null and the +1 `borderFillIDRef` shift Hancom applies —
without disturbing documents that already match Hancom exactly.

**Status:** design derived and de-risked through a read-only investigation and a
4-document validation of the rule (all rules, the canonical-null shape, the
detection test, and the exhaustive ref-site set are verified against the four
sample documents).

---

## Problem

Hancom guarantees the `borderFill` at id=1 is a *canonical null*: four side
borders `type="NONE"`, a `diagonal` `type="SOLID" width="0.1 mm" color="#000000"`,
and no `fillBrush`. If a document's first source borderFill is not exactly that,
Hancom **prepends** the canonical null at id=1, renumbers the source borderFills
to ids 2..N+1, and offsets **every** `borderFillIDRef` in the document by +1.

Our converter maps the source borderFills 1:1 (ids 1..N) and never prepends. On
the 2013 sample this leaves us one borderFill short (67 vs Hancom's 68) — dragging
its six mandatory child tags (`slash`, `backSlash`, `left/right/top/bottomBorder`)
down by one each in the count score — and every `borderFillIDRef` off by one
versus Hancom.

## Validation (4 documents)

The rule is strictly **position-0** (about slot 0 specifically, not the existence
of a null anywhere): 2013 has canonical nulls at source indices 3/18/40 yet its
`source[0]` is non-null, and Hancom still prepended.

| Doc | `border_fills[0]` | Action | section0 refs |
|-----|-------------------|--------|---------------|
| 2013 | not canonical (has a fillBrush) | **insert** | all `+1` (379/379 match Hancom) |
| sample 3 | canonical null | none | byte-identical (389/389) |
| sample 4 | canonical null | none | byte-identical (474/474) |
| ★131008 | canonical null | none | byte-identical |

Detection was verified directly on the mapped model: 3/4/★131008 `border_fills[0]`
is structurally equal to the canonical null; 2013's differs *only* by carrying a
fillBrush. Residual caveat: only 2013 exercises the insert path (n=1 on the
positive direction), but the mechanism is mechanically exact there and the rule
is unambiguous; the three negatives cover the regression-critical direction.

## The canonical null (byte-exact)

```
BorderFill(
    id=1,
    borders=[
        Border(kind="left",     type="NONE",  width="0.1 mm", color="#000000"),
        Border(kind="right",    type="NONE",  width="0.1 mm", color="#000000"),
        Border(kind="top",      type="NONE",  width="0.1 mm", color="#000000"),
        Border(kind="bottom",   type="NONE",  width="0.1 mm", color="#000000"),
        Border(kind="diagonal", type="SOLID", width="0.1 mm", color="#000000"),
    ],
    fill_color=None,
    gradation=None,
)
```

Fed through the existing `header_writer._write_border_fills` this serializes
byte-identically to Hancom's inserted id=1: `slash`/`backSlash` are always emitted
as `type="NONE"`; the four side borders and the SOLID diagonal come from
`borders`; `fill_color=None` + `gradation=None` yields no `fillBrush`.

## Architecture — one document-level normalization pass

A single pass `normalize_borderfill_null(doc)` in a new module
`hwp2hwpx/mapper/borderfill_null.py`, called at the **tail of `map_document`**
once the whole `OwpmlDocument` (header + all sections) is assembled.

1. **Detect:** if `doc.header.border_fills` is non-empty and `border_fills[0]` is
   **not** structurally equal to the canonical null, perform the insert; otherwise
   return unchanged. Structural equality compares: the four side-border types are
   all `NONE`, the `diagonal` border is `SOLID`/`0.1 mm`/`#000000`, and there is no
   fill (`fill_color` falsy and `gradation is None`). `slash`/`backSlash` are
   always-NONE in the writer, so they need not be compared. (Verified on all four
   samples: the three no-insert docs match on every field including diagonal-SOLID;
   2013 fails only the no-fill condition.)
2. **Insert:** prepend the canonical null; increment the `id` of every existing
   `BorderFill` by 1.
3. **Offset every `borderFillIDRef` by +1.** The set of ref-carrying fields is
   exhaustive, derived from the five `borderFillIDRef` writer emission sites:
   - `doc.header.char_prs[].border_fill_id` (header_writer.py:131)
   - `doc.header.para_prs[].border_fill_id` (header_writer.py:285)
   - each section's `page_border_fills[].border_fill_id` (section_writer.py:198)
   - each section's tables' `table.border_fill_id` (section_writer.py:592)
   - each table's cells' `cell.border_fill_id` (section_writer.py:625)

   All five index the single `header.border_fills` list; a `ref` of 0 (our
   "none" sentinel) maps to 1 (the null) under +1, matching Hancom's convention.
   Missing any one site corrupts rendering — the byte-identical gates on three
   documents verify the set is complete.

## Scope

**In:** the conditional canonical-null insert and the exhaustive +1
`borderFillIDRef` offset.

**Out (score-neutral, separate, untouched):**
- `<hc:diagonal>` over-emission (we emit on all fills; Hancom omits on ~9).
- The 8-fill `fillBrush` distribution difference on 2013 (equal total count).

## Testing & gates (all mandatory)

- **Detection unit test:** the canonical-null structural test returns True for a
  canonical-null `BorderFill` and False for one with a fillBrush / a non-NONE side
  border.
- **No-op regression (samples 3, 4, ★131008):** `borderFill` count unchanged, and
  every `borderFillIDRef` in `header.xml` and `section0.xml` stays **byte-identical**
  to Hancom's reference. This is the primary proof the pass never misfires and the
  offset set is complete.
- **Insert case (2013):** `borderFill` count 67→68; the id=1 null serializes
  byte-exact to Hancom's; every `borderFillIDRef` in header.xml and section0.xml
  equals the pre-pass value +1 and matches Hancom (379/379 in section0).
- **Score-floor:** no per-part fidelity score decreases on any sample; 2013 header
  rises (~99.67% → ~99.9%).
- **Full suite green** (currently 437) via `.venv/bin/python -m pytest`.

## Non-goals

- Diagonal over-emission and fillBrush distribution (score-neutral).
- Any change to documents whose `border_fills[0]` is already the canonical null.
- `substFont` (standing project non-goal).

## Value (stated plainly)

Closes the only remaining *derivable* score-visible gap: 2013 header ~99.67% →
~99.9% (~7 element counts on one file), and makes 2013's `borderFillIDRef`s
faithful to Hancom. The durable value is a correct, general model of Hancom's
reserved-null-borderFill convention, validated to leave conforming documents
untouched.
