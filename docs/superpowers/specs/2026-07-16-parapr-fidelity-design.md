# HWP → HWPX Converter — paraPr Fidelity + BorderFill ID Correction Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestone 1 (text/char/para) + tables milestone, both merged to `main`.

## Goal

Raise `header.xml` fidelity by emitting the **full `<hh:paraPr>`** (currently we emit only `id` + `align`), and correct the **BorderFill id base** to match Hancom (1-based), which also fixes an off-by-one introduced by the tables milestone and improves table border fidelity.

Success = `header.xml` match rises materially from the ~17–19% baseline; every `borderFillIDRef` (table, cell, paragraph) equals the value Hancom emits (1..52); output still opens in Hancom Office.

## Background — verified ground truth

**BorderFill ids.** Hancom emits `<hh:borderFill id=…>` with ids **1..52**; HWP `borderfill-id` references are also 1..52. Our tables milestone emitted defs 0..51 and shifted refs −1 (`reader._border_fill_id`, `_clamp_table_border_fill_ids`) to stay internally consistent — no dangling, but every id/ref is off-by-one vs Hancom. Correct base: **def id = positional index + 1**, refs use the **raw** HWP `borderfill-id` (no shift). With defs 1..52, ref 52 resolves (no dangling), so the shift+clamp workaround is removed.

**paraPr.** Hancom `<hh:paraPr id tabPrIDRef condense fontLineHeight snapToGrid suppressLineNumbers checked>` contains, in order:
```
<hh:align horizontal vertical/>
<hh:heading type idRef level/>
<hh:breakSetting breakLatinWord breakNonLatinWord widowOrphan keepWithNext keepLines pageBreakBefore lineWrap/>
<hh:autoSpacing eAsianEng eAsianNum/>
<hp:switch>
  <hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">
    <hh:margin><hc:intent value unit="HWPUNIT"/><hc:left/><hc:right/><hc:prev/><hc:next/></hh:margin>
    <hh:lineSpacing type value unit="HWPUNIT"/>
  </hp:case>
  <hp:default> … identical margin + lineSpacing … </hp:default>
</hp:switch>
<hh:border borderFillIDRef offsetLeft offsetRight offsetTop offsetBottom connect ignoreMargin/>
```

**HWP `ParaShape` attrs → paraPr (verified transforms):**
- `align` (both/center/left/right) → `hh:align/@horizontal` (both→JUSTIFY) — already mapped.
- `indent` → `hc:intent/@value` **÷ 2** (e.g. `-4000` → `-2000`).
- `doubled-margin-left/right/top/bottom` → `hc:left/right/prev/next/@value` **÷ 2** (e.g. `2000` → `1000`).
- `linespacing` + `linespacing-type="ratio"` → `hh:lineSpacing type="PERCENT" value=linespacing unit="HWPUNIT"`.
- `borderfill-id` → `hh:border/@borderFillIDRef` (raw, 1-based).
- `border-left/right/top/bottom` → `hh:border` offsets (0 in samples).
- `level` → `hh:heading/@level`; `head-shape` (none/bullet) → `hh:heading/@type` (none→NONE; bullet→NONE for now, numbering deferred).
- `tabdef-id` (0..6) → `tabPrIDRef` — clamped to `0` this milestone (real tab defs deferred); a minimal `<hh:tabProperties>` with one default id 0 is emitted so the ref resolves.
- break/keep flags (`linebreak-alphabet`, `linebreak-hangul`, `start-new-page`, `with-next-paragraph`, `autospace-alphabet`, `autospace-number`) → `breakSetting`/`autoSpacing` (mapped where a clear correspondence exists; safe Hancom-default values otherwise).

Units are HWPUNIT. Margin/indent values can be negative (hanging indents) — preserve sign.

## Decisions

- Emit BOTH `<hp:case>` and `<hp:default>` inside `<hp:switch>` with identical `margin`+`lineSpacing` (matches Hancom).
- `hh:tabProperties` with a single default `<hh:tab id="0" …>`-style entry (minimal, like the styles default) so `tabPrIDRef="0"` resolves; real tab defs are a follow-up.
- BorderFill id base becomes 1-based; the tables-milestone `_border_fill_id` shift and `_clamp_table_border_fill_ids` are removed and replaced by def-id = index+1 + raw refs (with a guard so a raw id < 1 does not dangle).
- Scope excludes charPr full attributes (next milestone).

## Architecture (extends existing layers)

**Model (`hwpmodel/model.py`, `owpml/model.py`):**
- `HwpParaShape` gains: `indent`, `margin_left`, `margin_right`, `margin_top`, `margin_bottom`, `line_spacing`, `line_spacing_type`, `border_fill_id`, `level`, `heading_type`, `tab_def_id` (+ keep the existing `align`).
- `ParaPr` gains: `intent`, `margin_left`, `margin_right`, `margin_prev`, `margin_next`, `line_spacing`, `line_spacing_type`, `border_fill_id`, `heading_level`, `heading_type`, `tab_pr_id` (+ `align`).

**Reader:** `read_docinfo` parses the full `ParaShape` attribute set into `HwpParaShape` (values halved where noted, or store raw and halve in mapper — see plan). BorderFill def ids become 1-based via the mapper; the reader stores raw `border_fill_id` on tables/cells (remove the shift).

**Mapper:** `map_para_shapes` builds full `ParaPr` (margin ÷2, lineSpacing ratio→PERCENT, border ref raw, tabPrIDRef→0). `map_border_fills` emits `BorderFill.id = index + 1`. `map_table` / body keep raw border refs (no shift).

**Writer:** `header_writer` emits the full `<hh:paraPr>` subtree (align/heading/breakSetting/autoSpacing/switch(case+default: margin+lineSpacing)/border) and a minimal `<hh:tabProperties>` in `refList` (Hancom order: fontfaces → borderFills → charProperties → tabProperties → … → paraProperties → styles).

**Fidelity harness:** existing; used to confirm header.xml gain and that `margin`/`lineSpacing`/`switch`/`border` no longer dominate the miss list.

## Error handling
- Missing/malformed ParaShape attrs fall back to 0 / Hancom-safe defaults (never crash).
- A `borderfill-id` < 1 is clamped to 1 (defs start at 1); ids ≥ count fall back to the last valid id (retain a robustness bound, now against the 1-based range).
- Odd `indent`/margin values halve with integer floor toward zero; sign preserved.

## Testing strategy (TDD)
- **Reader:** `HwpParaShape` for a known id has the expected raw indent/margins/linespacing/borderfill-id (fixture-backed).
- **Mapper:** margin ÷2 (incl. negative), ratio→PERCENT, border ref raw/1-based, tabPrIDRef clamped to 0; `map_border_fills` ids are 1..N.
- **Writer:** `header_xml` paraPr emits align/heading/breakSetting/autoSpacing/switch(case+default with margin+lineSpacing)/border; `<hh:tabProperties>` present; refList order correct.
- **End-to-end / fidelity:** convert real samples; assert `margin`/`lineSpacing`/`switch` gone from top-missing; every `borderFillIDRef` ∈ Hancom's 1..52 and no dangling; header.xml match up materially; tables still 33/cells intact; regression suite green; smoke opens.

## Non-goals (this milestone)
- charPr full attributes (per-language fonts, ratio/spacing/relSz/offset, underline/strikeout/outline/shadow) — next milestone (3b).
- Real tab definitions (tabPrIDRef clamped to 0) and real numbering/bullets (heading type simplified).
- linesegarray/lineseg layout metadata; images; styles beyond the default.

## Key risks
- **Margin ÷2 / unit correctness** — mitigated by the verified transform (indent −4000→−2000, dm-left 2000→1000) and per-value fidelity comparison against the pairs.
- **BorderFill id base change touching tables** — mitigated by regression tests (tables still 33/cells intact, no dangling) and by making refs equal Hancom's exactly.
- **paraPr sub-element completeness/order** — Hancom may be strict; mitigated by matching the real sample paraPr structure and the harness miss-list check.
