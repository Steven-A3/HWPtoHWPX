# HWP → HWPX Converter — Real Named Styles Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestone 1 (text/char/para) + tables + paraPr + charPr, all merged to `main`.

## Goal

Replace the single placeholder `<hh:style id="0">` in `header.xml` with the document's **real named styles** (63 in sample 3: 바탕글/Normal, 본문, 개요 1–N, …), and have body paragraphs reference their **real** style id instead of the hardcoded `0`. This raises `header.xml` fidelity from 87.4% — `style`×62 is the second-largest remaining header miss.

Success = all real styles emitted with correct names/refs; every paragraph's `styleIDRef` and every style's `paraPrIDRef`/`charPrIDRef`/`nextStyleIDRef` resolves (no dangling); `style` leaves the header miss list; header.xml match rises materially; output still opens in Hancom Office.

## Background — verified ground truth (sample 3)

HWP `IdMappings` holds **63 `Style`** elements (positional index == id):
```
<Style kind="paragraph" local-name="바탕글" name="Normal"
       charshape-id="17" parashape-id="3" next-style-id="0"
       lang-id="1042" flags="00" unknown="0"/>
```
Hancom emits, in `header.xml` `refList` under `<hh:styles>`:
```
<hh:style id="0" type="PARA" name="바탕글" engName="Normal"
          paraPrIDRef="3" charPrIDRef="17" nextStyleIDRef="0"
          langID="1042" lockForm="0"/>
```

**Transform (verified 1:1):**
- `id` = positional index (0-based).
- `kind="paragraph"` → `type="PARA"`; `kind="char"`/`"character"` → `type="CHAR"`; anything else → `PARA`.
- **`local-name` → `name`** (the Korean display name) and **`name` → `engName`** (the English name) — the two fields swap.
- `parashape-id` → `paraPrIDRef`.
- `charshape-id` → `charPrIDRef`.
- `next-style-id` → `nextStyleIDRef`.
- `lang-id` → `langID`.
- `lockForm` = `"0"` (constant; `flags="00"` in all samples).

All samples have `kind="paragraph"` only (0 char styles); the `CHAR` branch is defensive.

**Reference integrity.** `paraPrIDRef` indexes our 126 emitted paraPr (ids 0..125), `charPrIDRef` our 103 charPr (ids 0..102), `nextStyleIDRef` the 63 styles (ids 0..62). Body paragraphs' `styleIDRef` indexes the 63 styles. Each ref is clamped into its valid range as a no-dangling guard, consistent with prior milestones (borderFill, styleIDRef).

**Paragraph style id.** The reader already parses `HwpParagraph.style_id` from `Paragraph/@style-id`. Today `mapper/body.py` overrides it to `0` (because only the default style existed) and `section_writer` emits `styleIDRef=para.style_id`. With real styles present, `body.py` will pass the real `style_id` through (clamped to `[0, styleCount-1]`).

## Decisions

- Emit the full `<hh:styles itemCnt=N>` block (replacing the current single-default block) at the existing `refList` position (styles is last, after paraProperties — unchanged).
- `local-name`/`name` swap to `name`/`engName` per verified samples.
- Clamp all four ref kinds (`paraPrIDRef`, `charPrIDRef`, `nextStyleIDRef`, paragraph `styleIDRef`) into range; a missing/out-of-range value falls back to `0`.
- `typeInfo` and `substFont` (font-classification metadata *inside `<hh:font>`*) are OUT of scope — a separate fonts-refinement milestone.
- Outline numbering for `개요 N` levels is out of scope (heading/numbering deferred, as before).

## Architecture (extends existing layers)

**Model (`hwpmodel/model.py`, `owpml/model.py`):**
- `HwpStyle(index, kind, local_name, eng_name, para_shape_id, char_shape_id, next_style_id, lang_id)`.
- `HwpDocInfo` gains `styles: list`.
- OWPML `Style(id, type, name, eng_name, para_pr_id, char_pr_id, next_style_id, lang_id, lock_form)`.
- `Header` gains `styles: list`.

**Reader (`hwpmodel/reader.py`):** parse `IdMappings/Style` → `HwpDocInfo.styles`. Add a clamp pass: paragraph `style_id` → `[0, styleCount-1]`, and (once counts are known) style `para_shape_id`/`char_shape_id`/`next_style_id` into their respective ranges. Missing/malformed attrs fall back to `0`/`"paragraph"`.

**Mapper (`mapper/style.py` — new, plus `body.py`):** `map_styles(list[HwpStyle]) -> list[Style]` applies the transform (kind→type, name swap, ref passthrough, lockForm=0). `map_document` builds `Header.styles = map_styles(docinfo.styles)`. `body.py` maps the real `style_id` (clamped) instead of `0`.

**Writer (`owpml/header_writer.py`):** replace the default-style block with a loop emitting every `Header.styles` entry as `<hh:style>` with the 9 attributes. If `Header.styles` is empty, keep emitting a single default style id 0 (so an empty-styles document still resolves `styleIDRef="0"`).

**Fidelity harness:** existing; confirm `style` leaves the header miss list and no ref dangles.

## Error handling
- No `Style` elements → emit the single default style id 0 (current behavior preserved); paragraphs keep `styleIDRef="0"`.
- Missing `kind` → `PARA`; missing name fields → empty strings; missing/negative ref → `0`.
- Any ref past the end of its target list is clamped to the last valid id (or `0` if the target list is empty).

## Testing strategy (TDD)
- **Reader:** `HwpDocInfo.styles` has 63 entries; style 0 has `local_name="바탕글"`, `eng_name="Normal"`, `char_shape_id=17`, `para_shape_id=3`; a known paragraph carries its real (non-zero) `style_id`.
- **Mapper:** `map_styles` yields `type="PARA"`, `name="바탕글"`, `eng_name="Normal"`, `para_pr_id=3`, `char_pr_id=17`, `lock_form="0"`; `kind="char"`→`type="CHAR"`; out-of-range refs clamp to `0`/last valid; `body.py` emits the real clamped `style_id`.
- **Writer:** `header_xml` emits `<hh:styles itemCnt=63>` with each `<hh:style>` carrying the 9 attributes; empty-styles header still emits the single default id 0.
- **End-to-end / fidelity:** convert real samples; assert `style` count == Hancom's (63) and gone from top-missing; every `styleIDRef`/`paraPrIDRef`/`charPrIDRef`/`nextStyleIDRef` resolves; header.xml match up materially; regression suite green; smoke opens in Hancom.

## Non-goals (this milestone)
- `typeInfo`/`substFont` font-classification metadata (fonts milestone).
- Real tab definitions; `linesegarray`/`lineseg` layout metadata; images.
- Outline numbering/bullets for `개요 N` heading styles.

## Key risks
- **name/engName swap** — mitigated by the verified sample transform and a mapper test asserting `name="바탕글"`/`engName="Normal"`.
- **styleIDRef now non-zero can dangle** — mitigated by the clamp pass and an end-to-end no-dangling assertion across all four ref kinds.
- **refList placement/attribute completeness** — mitigated by matching the real sample `<hh:style>` and the harness miss-list check.
