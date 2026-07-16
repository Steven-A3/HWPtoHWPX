# HWP → HWPX Converter — Real Tab Definitions Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestone 1 (text/char/para) + tables + paraPr + charPr + real styles, all merged to `main`.

## Goal

Emit the document's real tab definitions in `header.xml` — a full `<hh:tabProperties itemCnt=7>` with per-tab-stop content — and make each paraPr reference its **real** `tabPrIDRef` (0–6) instead of the hardcoded `0`. This is the largest remaining single header gain: it clears the `tabItem`×212, `switch`×106, and `tabPr`×6 misses at once.

Success = `<hh:tabProperties>` matches Hancom's structure (7 tabPr, 106 switches, 212 tabItems); every paraPr `tabPrIDRef` resolves (no dangling); `tabItem`/`switch`/`tabPr` leave the header miss list; header.xml match rises materially; output still opens in Hancom Office.

## Background — verified ground truth (sample 3)

HWP `IdMappings` holds **7 `TabDef`** (matching `tabdefs="7"`):
```
<TabDef autotab-left="0" autotab-right="0" flags="00000000">
  <Array name="tabs">
    <Tab fill-type="0" flags="…" kind="left" pos="8064"/>
    …
  </Array>
</TabDef>
```
Tab counts across the 7 TabDefs are `0, 31, 2, 39, 1, 33, 0` (total **106**). `kind`∈{left,right}, `fill-type`∈{0,3} in samples. TabDef 0 and 6 are empty; TabDef 6 has `autotab-left="1"`.

Hancom emits `<hh:tabProperties itemCnt="7">` with 7 `<hh:tabPr>` (ids 0–6):
- An **empty** TabDef → self-closing `<hh:tabPr id="N" autoTabLeft=… autoTabRight=…/>`.
- A **non-empty** TabDef → `<hh:tabPr id=… autoTabLeft=… autoTabRight=…>` containing **one `<hp:switch>` per Tab**:
```
<hp:switch>
  <hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">
    <hh:tabItem pos="{raw/2}" type="LEFT" leader="NONE" unit="HWPUNIT"/>
  </hp:case>
  <hp:default>
    <hh:tabItem pos="{raw}" type="LEFT" leader="NONE"/>
  </hp:default>
</hp:switch>
```

**Verified transforms:**
- `Tab@pos` → `case` `tabItem/@pos` = **raw ÷ 2**; `default` `tabItem/@pos` = **raw** (e.g. 3216 → case 1608, default 3216).
- `Tab@kind` → `tabItem/@type`: left→`LEFT`, right→`RIGHT`, center→`CENTER`, decimal→`DECIMAL` (samples: left, right).
- `Tab@fill-type` → `tabItem/@leader`: `0`→`NONE`, `3`→`DASH` (confirmed); a small best-effort table (`1`→`DOT`, `2`→`DASH`, `4`→`DASHDOT`) for the rest; unknown → `NONE`.
- `TabDef@autotab-left`/`autotab-right` → `tabPr/@autoTabLeft`/`autoTabRight` (passthrough).
- `unit="HWPUNIT"` appears only on the `case` tabItem, not the `default`.
- HWP `ParaShape@tabdef-id` (0–6) → paraPr `tabPrIDRef`.

Count check: 106 tabs → 106 switches → 212 tabItems, exactly matching Hancom.

## Decisions

- Emit both `<hp:case>` (unit=HWPUNIT, pos÷2) and `<hp:default>` (pos raw) per tab, mirroring the paraPr switch idiom already in `header_writer`.
- Empty TabDef → self-closing `<hh:tabPr>` carrying only id + autoTab attrs.
- `tabPrIDRef` becomes the real `ParaShape@tabdef-id`, clamped to `[0, tabDefCount-1]` (no dangling); a document with zero TabDefs keeps the current single default `<hh:tabPr id="0">` and `tabPrIDRef="0"`.
- `fill-type`→`leader` uses a small table with `NONE` fallback; only `0`/`3` are exercised by samples and must match byte-for-byte.
- Out of scope: `typeInfo`/`substFont`; `linesegarray`; leaders/types not present in samples beyond the fallback table.

## Architecture (extends existing layers)

**Model (`hwpmodel/model.py`, `owpml/model.py`):**
- `HwpTab(pos:int, kind:str="left", fill_type:int=0)`; `HwpTabDef(index:int, auto_tab_left:int=0, auto_tab_right:int=0, tabs:list)`.
- `HwpDocInfo` gains `tab_defs:list`. `HwpParaShape` gains `tab_def_id:int=0`.
- OWPML `TabItem(pos:int, type:str="LEFT", leader:str="NONE")`; `TabDef(id:int, auto_tab_left:int=0, auto_tab_right:int=0, tabs:list)`.
- `Header` gains `tab_defs:list`. `ParaPr.tab_pr_id` already exists.

**Reader (`hwpmodel/reader.py`):** parse `IdMappings/TabDef` (with nested `Array/Tab`) → `HwpDocInfo.tab_defs`. Parse `ParaShape@tabdef-id` → `HwpParaShape.tab_def_id`. Clamp each `tab_def_id` into `[0, tabDefCount-1]` (new clamp pass, mirroring the style/borderFill clamps).

**Mapper (`mapper/tab.py` — new, plus `para_pr.py`, `body.py`):** `map_tab_defs(list[HwpTabDef]) -> list[TabDef]` (kind→type, fill-type→leader, pos passthrough — the ÷2 for the case happens in the writer, since both raw and halved are needed). `para_pr.py` emits the real `tab_pr_id=ps.tab_def_id`. `map_document` builds `Header.tab_defs = map_tab_defs(di.tab_defs)`.

**Writer (`owpml/header_writer.py`):** replace the minimal single-tabPr block with a loop over `Header.tab_defs`: empty → self-closing tabPr; else per-tab `<hp:switch>` (case pos÷2 + unit, default pos raw). If `Header.tab_defs` is empty, keep the current single default `<hh:tabPr id="0">` so `tabPrIDRef="0"` resolves.

**Fidelity harness:** existing; confirm `tabItem`/`switch`/`tabPr` leave the miss list and no `tabPrIDRef` dangles.

## Error handling
- No `TabDef` elements → single default `<hh:tabPr id="0">` (current behavior); `tabPrIDRef` clamped to 0.
- Missing `Array`/`Tab` → empty (self-closing) tabPr.
- Missing/malformed `pos`/`kind`/`fill-type` → 0/`LEFT`/`NONE`.
- `tabdef-id` out of range → clamped to last valid id (or 0 if none).
- Odd `pos` halves with integer floor toward zero (sign preserved).

## Testing strategy (TDD)
- **Reader:** `HwpDocInfo.tab_defs` has 7 entries with tab counts `[0,31,2,39,1,33,0]`; TabDef 6 has `auto_tab_left==1`; a known Tab has expected `pos`/`kind`/`fill_type`; a paragraph's `ParaShape.tab_def_id` is parsed and in range.
- **Mapper:** `map_tab_defs` yields `type="LEFT"`/`"RIGHT"`, `leader="NONE"`/`"DASH"` (fill-type 0/3); `para_pr` emits the real `tab_pr_id`.
- **Writer:** `header_xml` emits `<hh:tabProperties itemCnt=7>`; an empty TabDef → self-closing tabPr; a non-empty one → N `<hp:switch>` with case(pos÷2, unit=HWPUNIT)+default(pos raw); empty-tab_defs header still emits the single default id 0.
- **End-to-end / fidelity:** convert real samples; assert `switch`==232, `tabItem`==212, tabPr==7, gone from top-missing; every paraPr `tabPrIDRef` ∈ emitted tabPr ids (no dangling); header.xml match up materially; regression suite green; smoke opens in Hancom.

## Non-goals (this milestone)
- `typeInfo`/`substFont` font-classification metadata (fonts milestone).
- `linesegarray`/`lineseg` layout metadata; images.
- Leader/type values beyond the mapped table (revisited when a sample exercises them).

## Key risks
- **pos ÷2 (case vs default)** — mitigated by the verified transform (3216 → case 1608 / default 3216) and per-value fidelity comparison.
- **Empty vs non-empty tabPr shape** — mitigated by matching the real sample (self-closing when 0 tabs) and the harness element counts.
- **tabPrIDRef now non-zero can dangle** — mitigated by the clamp pass and the end-to-end no-dangling assertion.
- **switch/case nesting completeness** — mitigated by reusing the paraPr switch idiom and asserting exact `switch`/`tabItem` counts (232/212).
