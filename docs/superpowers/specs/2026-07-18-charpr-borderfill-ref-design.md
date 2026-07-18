# Real charPr borderFillIDRef — Design

**Goal:** Emit each character shape's true border/fill reference (from the
`HWPTAG_CHAR_SHAPE` record) instead of the hardcoded `1`, so
`charPr/@borderFillIDRef` matches Hancom and character borders/backgrounds
resolve to the correct `borderFill`.

**Status:** design derived and verified against all four sample documents.

---

## Problem

The mapper hardcodes `border_fill_id=1` for every character shape
(`hwp2hwpx/mapper/char_pr.py:39`), so every `charPr` in `header.xml` emits
`borderFillIDRef="1"` regardless of the shape's real border/shade. Hancom's
values vary per shape (e.g. sample 3: `1, 2, 1, 1, 1, 2, ...`). The divergence is
score-neutral (it is an attribute value, not an element count) but is a genuine
rendering-fidelity defect: a character shape with a background shade should
reference the `borderFill` carrying that shade, not the null fill at id 1.

## Root cause & derivation (verified)

The character shape's border/fill id is a `UINT16` at **payload offset 68** of
the `HWPTAG_CHAR_SHAPE` record — the spec position immediately after the four
`COLORREF` fields (text/underline/shade/shadow colors occupy bytes 52–67).
pyhwp parses the record but does not surface this field in either `hwp5proc xml`
(no border attribute on `CharShape`) or the named keys of `hwp5proc models`.
It is present in the record's raw `payload` bytes, reachable via
`hwp5proc models DocInfo`.

Verified against Hancom's `charPr/@borderFillIDRef`, in CharShape index order,
on all four samples:

| Doc | offset-68 vs Hancom | CharShape payload length |
|-----|---------------------|--------------------------|
| sample 3 | **== direct** (103/103) | 74 |
| sample 4 | **== direct** (172/172) | 74 |
| ★131008 | **== direct** (154/154) | 74 |
| 2013 | **+1** (327/327) | 70 |

The `+1` on 2013 is exactly the shift that `normalize_borderfill_null` already
applies to `char_prs` when it prepends the canonical null (2013 is a null-insert
doc). So reading the raw field and letting the existing pass do the +1 yields a
Hancom-faithful result on **all four** samples. Offset 68 is stable across the
two record-length variants observed (70 and 74) because the field sits in the
mandatory part of the record, before the version-specific trailing fields.

## Architecture

Mirrors the segmentation milestone's correlation pattern (`hwp5proc models`
records read in document order, correlated by index with a length-equality
guard that falls back on mismatch — never misaligns).

- **`hwp2hwpx/hwpmodel/reader.py`**
  - New `_payload_bytes(rec)` — flattens a models record's `payload` (a list of
    space-separated hex strings) to `bytes`.
  - New `hwp5_char_shape_border_fills(hwp_path) -> list[int]` — runs
    `hwp5proc models DocInfo`; for each `CharShape` record in order, reads the
    `UINT16` little-endian at payload offset 68, or `1` if the payload is shorter
    than 70 bytes. Returns the list in CharShape index order.
  - `read_docinfo(xml_bytes, char_border_fills=None)` — new optional parameter
    (backward compatible: existing callers/tests that pass only `xml_bytes` are
    unaffected). After the `char_shapes` list is built, if `char_border_fills` is
    provided **and** `len(char_border_fills) == len(char_shapes)`, assign each
    `char_shapes[i].border_fill_id`; otherwise leave the model default.
  - `read_document(xml_bytes, char_shapes=None, char_border_fills=None)` — new
    optional parameter, forwarded to `read_docinfo`.

- **`hwp2hwpx/hwpmodel/model.py`** — `HwpCharShape` gains
  `border_fill_id: int = 1`.

- **`hwp2hwpx/mapper/char_pr.py`** — use `cs.border_fill_id` in place of the
  literal `1`.

- **`hwp2hwpx/convert.py`** — compute `hwp5_char_shape_border_fills(hwp_path)` and
  pass it to `read_document`.

- **`hwp2hwpx/mapper/borderfill_null.py`** — unchanged. Its existing `+1` on
  `char_prs` supplies the shift for null-insert documents.

## Scope

**In:** the header `charPr/@borderFillIDRef` value, derived from the CharShape
record. Section0 `borderFillIDRef`s (para/table/cell/page) are untouched, so the
borderFill-null-insert milestone's section0 gates remain valid.

**Out (non-goals):**
- `substFont` (standing project non-goal).
- The pre-existing `paraPr` sentinel divergence, `diagonal` over-emission, and
  fillBrush distribution (all 2013-related, score-neutral, separate).

## Testing & gates

- **Unit (reader):** `_payload_bytes` decodes a synthetic payload; the offset-68
  reader returns the expected id for a ≥70-byte payload and the `1` fallback for a
  short payload.
- **Correlation guard:** `read_docinfo` assigns border-fill ids when the list
  length matches the char-shape count and leaves defaults (all `1`) on mismatch.
- **Fidelity (primary):** for samples 3, 4, and ★131008, every
  `charPr/@borderFillIDRef` in `header.xml` is **byte-identical to Hancom's**
  reference (they were uniformly `1` before this change).
- **Score-floor:** no per-part fidelity score decreases on any sample (this is an
  attribute-value change; element counts are unchanged).
- **Full suite green** via `.venv/bin/python -m pytest`, updating any existing
  test that asserted the hardcoded `1`.

## Value

Score-neutral (attribute value), but corrects a real rendering defect —
character borders/backgrounds now reference the correct `borderFill` — and makes
`charPr/@borderFillIDRef` byte-faithful to Hancom across every sample, closing
the most legitimate remaining derivable divergence outside `substFont`.
