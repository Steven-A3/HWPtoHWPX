# HWP → HWPX Converter — Tail Cleanup Design (typeInfo + inline tab)

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestones 1 + tables + paraPr + charPr + styles + tabs + section-inline + linesegarray, all merged to `main`.

## Goal

Close the two clean, real-data, generalizing items in the fidelity tail:
1. **`<hh:typeInfo>`** — font PANOSE classification (header's largest remaining miss: 32 on sample 1, 62 on sample 2).
2. **inline `<hp:tab>`** — the HWP `TAB` control character (section's `tab`×24 on sample 2).

Success = every `<hh:font>` carries a `<hh:typeInfo>` from HWP's `Panose1`; inline `TAB` characters emit `<hp:tab>` as mixed content; `typeInfo` and `tab` leave the miss lists; header.xml and section0.xml match rise on **both** samples; output still opens in Hancom Office.

Out of scope (documented non-goals): `substFont` (Hancom runtime substitution, not derivable from HWP), `subscript`, images/shapes.

## Background — verified ground truth

**typeInfo.** Every HWP `FaceName` (all 65 in sample 1) has a `Panose1` child:
```
<Panose1 family-type="2" serif-style="11" weight="6" proportion="9" contrast="0"
         stroke-variation="1" arm-style="1" letterform="1" midline="1" x-height="1"/>
```
Hancom emits, as a child of `<hh:font>`:
```
<hh:typeInfo familyType="FCAT_GOTHIC" weight="6" proportion="0" contrast="0"
             strokeVariation="1" armStyle="1" letterform="1" midline="1" xHeight="1"/>
```
Mapping: `family-type` (int) → `familyType` (string) via `{1: "FCAT_MYUNGJO", 2: "FCAT_GOTHIC"}`, default `"FCAT_GOTHIC"`; `weight`→`weight`, `proportion`→`proportion`, `contrast`→`contrast`, `stroke-variation`→`strokeVariation`, `arm-style`→`armStyle`, `letterform`→`letterform`, `midline`→`midline`, `x-height`→`xHeight`. `serif-style` is dropped (Hancom's `typeInfo` has no `serifStyle`).

Note: Hancom emits `typeInfo` on only *some* fonts (32/65), but our fonts layer replicates the flat font list into all 7 language buckets, so we emit `typeInfo` on every font element. The count-based harness (`matched = Σ min(our, their)`) gives full credit either way (`min(ours, 32) = 32`), and `typeInfo` is valid schema on any font, so the file still opens. This over-emission is a documented, score-neutral consequence of the existing font-bucket simplification.

**inline tab.** HWP has an inline `ControlChar name="TAB" code="9"` in paragraph text. Hancom emits `<hp:tab width="4000" leader="0" type="1"/>` as mixed content inside `<hp:t>`, exactly like `<hp:fwSpace/>`/`<hp:lineBreak/>` (which the section-inline milestone already handles). The `width`/`leader`/`type` are layout-computed by Hancom (recomputed on open) and are not carried by the HWP control char; we emit schema-valid defaults (`width="0" leader="0" type="0"`). The count-based score and Hancom's re-layout make the exact values irrelevant.

## Decisions

- Emit `<hh:typeInfo>` on **every** `<hh:font>` (from its `Panose1`); accept the over-emission vs Hancom's selective 32 (score-neutral, schema-valid).
- Map `family-type`→`familyType` via `{1: MYUNGJO, 2: GOTHIC}`, default GOTHIC; pass the other 8 Panose fields through numerically; drop `serif-style`.
- Extend the section-inline control map with `TAB` → `tab`; the writer emits `<hp:tab>` with default `width`/`leader`/`type` (the only control kind that carries attributes).
- A `FaceName` with no `Panose1` emits no `typeInfo` (defensive; does not occur in samples).

## Architecture (extends existing layers)

**Model (`hwpmodel/model.py`, `owpml/model.py`):**
- `HwpPanose(family_type:int=0, weight:int=0, proportion:int=0, contrast:int=0, stroke_variation:int=0, arm_style:int=0, letterform:int=0, midline:int=0, x_height:int=0)`; `HwpFont` gains `panose: HwpPanose = None`.
- `TypeInfo(family_type:str="FCAT_GOTHIC", weight:int=0, proportion:int=0, contrast:int=0, stroke_variation:int=0, arm_style:int=0, letterform:int=0, midline:int=0, x_height:int=0)`; `Font` gains `type_info: TypeInfo = None`.
- No model change for the tab (reuses `HwpControl`/`Control` with `kind="tab"`).

**Reader (`hwpmodel/reader.py`):**
- Parse each `FaceName`'s `Panose1` child into `HwpFont.panose`.
- Add `"TAB": "tab"` to `_CONTROL_KIND` so an inline `TAB` control char becomes `HwpControl("tab")` in the run's `contents`.

**Mapper (`mapper/fonts.py`):** for each `HwpFont`, build `Font.type_info = TypeInfo(...)` from `panose` (family-type→FCAT string, others passthrough). Buckets are still the replicated flat list, now each font carrying its `type_info`.

**Writer (`owpml/header_writer.py`, `owpml/section_writer.py`):**
- `header_writer`: `<hh:font>` becomes a container; when `f.type_info` is set, emit a `<hh:typeInfo>` child with the 9 attributes.
- `section_writer`: in the mixed-content run emitter, when a `Control.kind == "tab"`, set `width`/`leader`/`type` defaults on the `<hp:tab>` element (other kinds stay empty).

**Fidelity harness:** existing; confirm `typeInfo` and `tab` leave the miss lists on both samples and both parts' match rise.

## Error handling
- Missing `Panose1` → `HwpFont.panose = None` → no `typeInfo` emitted (never crash).
- Unknown `family-type` → `"FCAT_GOTHIC"`; missing Panose attrs → 0.
- The `tab` control emits fixed valid defaults; unknown control names are still skipped (unchanged).

## Testing strategy (TDD)
- **Reader:** a known `FaceName` parses to a `HwpFont.panose` with the expected `family_type`/`weight`/`x_height`; an inline `TAB` control char parses to `HwpControl("tab")` in the run contents (sample 2).
- **Mapper:** `family-type` 2→`"FCAT_GOTHIC"`, 1→`"FCAT_MYUNGJO"`, unknown→`"FCAT_GOTHIC"`; the other 8 fields pass through; every `Font` gets a `type_info`.
- **Writer:** `<hh:font>` emits a `<hh:typeInfo>` child with the 9 attributes; a `Control("tab")` emits `<hp:tab width leader type>` inside `<hp:t>` while `Control("fwSpace")` stays empty.
- **End-to-end / fidelity (BOTH samples):** convert samples 3 and 4; assert `typeInfo` gone from the header miss list and `tab` gone from the section miss list; header.xml and section0.xml match rise on both; regression suite green; smoke opens in Hancom.

## Non-goals (this milestone)
- `substFont` (Hancom runtime font substitution — not derivable from HWP), `subscript`, images/shapes, remaining small section items (`ctrl`, `pageBorderFill`, `noteLine`/`noteSpacing`, `autoNumFormat`).
- Fixing the font-bucket replication (per-language buckets) — a separate font-architecture refactor.

## Key risks
- **family-type→FCAT mapping** — mitigated by a mapper test correlating a known gothic font (family-type 2 → GOTHIC) and a known myungjo font (family-type 1 → MYUNGJO) against the fixture.
- **`<hh:font>` becoming a container** — every existing font test must stay green (mitigated by making `typeInfo` an additive child, keeping the existing attributes).
- **tab as attributed control** — mitigated by the writer special-casing only `kind=="tab"` and a writer test asserting `fwSpace`/`lineBreak` stay empty.
- **Generality** — validated on both sample pairs, not just sample 3.
