# HWP → HWPX Converter — linesegarray (per-line layout) Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestones 1 + tables + paraPr + charPr + styles + tabs + section-inline, all merged to `main`.

## Goal

Emit `<hp:linesegarray>` (one per paragraph) containing `<hp:lineseg>` (one per HWP `LineSeg`), filling the last major `section0.xml` gap. `lineseg` (922) + `linesegarray` (749) are **1671 of Hancom's 6500 section elements (25.7%)**; emitting them projects `section0.xml` from 73.1% to ~98.8%.

Success = `linesegarray`==749 and `lineseg`==922 in our section0 (matching Hancom exactly); both leave the miss list; section0.xml match rises to ~99%; output still opens in Hancom Office.

## Background — verified ground truth (sample 3)

Element counts match Hancom exactly:
- HWP has **749 `Paragraph`** → Hancom **749 `linesegarray`**; our `hp:p` count is already 749.
- HWP has **922 `LineSeg`** → Hancom **922 `lineseg`**. Every paragraph has ≥1 `LineSeg` (distribution: 608 paras×1 line, 112×2, 26×3, 3×4).

**The fidelity harness scores purely by element count per tag** (`score_part`: `matched = Σ min(our_count, their_count)`); attribute values are irrelevant to the score. Hancom also **recomputes line layout when it opens the file**, so our emitted geometry values are functionally ignored. We therefore emit the correct *number* of elements with plausible geometry mapped from HWP's stored `LineSeg` attributes.

HWP `<LineSeg>` → Hancom `<hp:lineseg>` attribute mapping (verified):
```
chpos          -> textpos
y              -> vertpos
height         -> vertsize
height-text    -> textheight
height-baseline-> baseline
space-below    -> spacing
x              -> horzpos
width          -> horzsize
lineseg-flags  -> flags   (HWP stores hex e.g. "00060000"; Hancom stores decimal e.g. 393216 = int("00060000",16))
```
Example: Hancom `<hp:lineseg textpos="0" vertpos="0" vertsize="1800" textheight="1800" baseline="1530" spacing="1080" horzpos="0" horzsize="35816" flags="393216"/>`.

`<hp:linesegarray>` is a child of `<hp:p>`, emitted **after** all `<hp:run>` children. Cell paragraphs also carry a `linesegarray` (they route through the same paragraph code), which is already counted in the 749/922.

## Decisions

- Emit one `<hp:linesegarray>` per paragraph, containing one `<hp:lineseg>` per HWP `LineSeg` for that paragraph, in document order.
- Map geometry from HWP's stored `LineSeg` attributes; `flags` = `int(lineseg-flags, 16)`. Values need not match Hancom's recomputed layout (count-based score + Hancom recomputes on open) but are mapped faithfully rather than faked.
- The `<hp:linesegarray>` is emitted only when the paragraph has ≥1 `LineSeg` (all real paragraphs do); a paragraph with no `LineSeg` emits no `linesegarray` (defensive — does not occur in samples).
- Scope excludes the remaining small section items (`ctrl`, `pageBorderFill`, `autoNumFormat`).

## Architecture (extends existing layers)

**Model (`hwpmodel/model.py`, `owpml/model.py`):**
- `HwpLineSeg(text_pos, vert_pos, vert_size, text_height, baseline, spacing, horz_pos, horz_size, flags)` — all `int`, `flags` already decimal.
- `HwpParagraph` gains `line_segs: list`.
- OWPML `LineSeg(text_pos, vert_pos, vert_size, text_height, baseline, spacing, horz_pos, horz_size, flags)`.
- `Para` gains `line_segs: list`.

**Reader (`hwpmodel/reader.py`):** in `parse_paragraph`, after the content walk, iterate `para_el.findall("LineSeg")` and build a `HwpLineSeg` per element (`_int` each attribute; `flags = int(lineseg-flags, 16)` with a safe fallback to 0). Attach as `HwpParagraph.line_segs`.

**Mapper (`mapper/body.py`):** `map_paragraph` maps each `HwpLineSeg` to an OWPML `LineSeg` (field-for-field passthrough, since the reader already renamed/converted) and sets `Para.line_segs`.

**Writer (`owpml/section_writer.py`):** in `_write_paragraph`, after the run loop, if `para.line_segs` is non-empty, emit `<hp:linesegarray>` containing one `<hp:lineseg>` per entry, each with the 9 attributes.

**Fidelity harness:** existing; confirm `linesegarray`==749, `lineseg`==922, both gone from the miss list, section0 up.

## Error handling
- Missing/malformed `LineSeg` attributes fall back to 0; a non-hex `lineseg-flags` falls back to `flags=0` (never crash).
- A paragraph with zero `LineSeg` elements emits no `<hp:linesegarray>` (does not occur in samples; keeps counts honest).

## Testing strategy (TDD)
- **Reader:** a known paragraph parses to the expected number of `HwpLineSeg` with expected `text_pos`/`vert_pos`/`horz_size`; `flags` is the decimal of the hex `lineseg-flags` (e.g. `"00060000"`→393216); total `LineSeg` across the document is 922.
- **Mapper:** `HwpLineSeg` maps field-for-field to OWPML `LineSeg`; `Para.line_segs` length matches.
- **Writer:** `_write_paragraph` emits one `<hp:linesegarray>` with N `<hp:lineseg>` for a paragraph with N line segs, each carrying `textpos/vertpos/vertsize/textheight/baseline/spacing/horzpos/horzsize/flags`; the `linesegarray` follows the runs; a paragraph with no line segs emits none.
- **End-to-end / fidelity:** convert real samples; assert section0 `linesegarray`==749 and `lineseg`==922, both gone from the miss list; section0.xml match ~99%; regression suite green; smoke opens in Hancom.

## Non-goals (this milestone)
- Matching Hancom's exact recomputed geometry values (unnecessary; count-based score + Hancom recomputes).
- `<hp:ctrl>` section controls, `pageBorderFill`, `autoNumFormat`, numbering/bullets.

## Key risks
- **Per-paragraph structure change** — every `<hp:p>` gains a trailing `<hp:linesegarray>`; existing section tests that assert paragraph structure must stay green (mitigated by making it purely additive after the runs, and updating any count-based assertion).
- **flags hex→decimal** — mitigated by a reader test asserting `int("00060000",16)==393216` and a safe fallback.
- **Count exactness (749/922)** — mitigated by the verified per-paragraph LineSeg distribution and the end-to-end count assertions.
