# HWP → HWPX Converter — Subscript charPr Design

**Date:** 2026-07-17
**Status:** Approved (design confirmed by user)
**Builds on:** milestones 1..17 (through pageHiding), all merged to `main`.

## Goal

Emit `<hh:subscript/>` in the `<hh:charPr>` definitions whose HWP `CharShape` has
the subscript flag set. We never emit it today: sample 3 `header.xml` misses
`subscript`×3, sample 4 ×4.

**Success** = every charPr whose CharShape has the subscript flag gains a trailing
`<hh:subscript/>`; `header.xml` `subscript` miss count is 0 on both samples;
`header.xml` match rises; output still opens in Hancom Office.

## Verified ground truth

- Subscript is encoded in HWP `CharShape` `charshapeflags` — **bit 16**. Verified:
  sample 3 charPr ids `[58, 59, 60]` and sample 4 `[131, 132, 133, 134]` are
  exactly the CharShapes with `charshapeflags` bit 16 set, and exactly the ones
  Hancom marks `<hh:subscript/>`. No CharShape in either sample has bit 17, and
  neither emits `<hh:supscript/>`.
- `charshapeflags` is exposed by `hwp5proc xml` (e.g. `charshapeflags="00010002"`).
  `bold`/`italic` are separate XML attributes, but subscript lives only in the
  bitfield — so the reader must read `charshapeflags` and test bit 16.
- OWPML placement: `<hh:subscript/>` is an **empty element, the last child** of
  `<hh:charPr>` (child order `fontRef, ratio, spacing, relSz, offset, bold,
  underline, strikeout, outline, shadow, subscript`). Our writer already emits
  through `shadow`; `subscript` appends after it.
- **Header-only:** `subscript` appears only in `header.xml`; runs reference these
  charPrs by `charPrIDRef` and emit no subscript element, so `section0.xml` is
  unchanged (no sample-3 section re-baseline needed).

## Architecture (extends all 4 layers, minimally)

**Model (`hwpmodel/model.py`):** `HwpCharShape` gains `subscript: bool = False`.

**OWPML model (`owpml/model.py`):** `CharPr` gains `subscript: bool = False`.

**Reader (`hwpmodel/reader.py`, CharShape parsing in `read_docinfo`):** set
`subscript=((_hex_int(el.get("charshapeflags")) >> 16) & 1) == 1`.

**Mapper (`mapper/char_pr.py`, `map_char_shapes`):** pass `subscript=cs.subscript`
into `CharPr(...)`.

**Writer (`owpml/header_writer.py`, charPr emission):** after the `shadow`
subelement, `if cp.subscript: etree.SubElement(ce, _hh("subscript"))`.

## Error handling

- Missing/garbage `charshapeflags` → `_hex_int` returns 0 → `subscript=False` (no
  element). Never crash.
- A charPr with `subscript=False` → unchanged output.

## Testing strategy (TDD)

- **Reader:** a synthetic `CharShape charshapeflags="00010000"` → `HwpCharShape.
  subscript is True`; `charshapeflags="00000000"` → `False`; and on sample 3,
  CharShapes 58/59/60 have `subscript is True` while a plain one (e.g. 0) is
  `False`.
- **Mapper:** `HwpCharShape(subscript=True)` → `CharPr.subscript is True`.
- **Writer:** a `CharPr(subscript=True)` serializes a trailing `<hh:subscript/>`
  as the charPr's **last** child (after `<hh:shadow>`); `subscript=False` emits
  none.
- **End-to-end / fidelity:** sample 3 and sample 4 — `header.xml` `subscript` miss
  count is 0; the exact count of `<hh:subscript/>` equals Hancom's (3 / 4);
  `header.xml` match rises; full regression green (`section0.xml` unchanged).

## Non-goals

- Superscript (`<hh:supscript/>`, bit 17) — absent in both samples; the bit-17→
  supscript mapping is unverified, so it is left for a future milestone rather
  than emitted speculatively. This milestone maps only bit 16 → subscript.
- The remaining `header.xml` gaps (`substFont` — a documented non-goal; `bullets`/
  `paraHead` numbering) — separate milestones.

## Key risks

- **Bit index** — mitigated by the verified correlation (bits set exactly on the
  charPrs Hancom marks) and a reader test on a known CharShape; the count-based
  fidelity gate catches an off-by-one bit.
- **Child order** — mitigated by appending `subscript` after `shadow` (the current
  last child) and a writer test asserting it is the charPr's last child.
