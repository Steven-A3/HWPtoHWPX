# HWP → HWPX Converter — Drawing Objects (Slice A: GSO container + lines) Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestones 1..10 (through section-properties), all merged to `main`.

## Scope

Drawing-object support decomposes into two sub-milestones (the whole subsystem is
too large for one plan):

- **Slice A (this spec): GSO common container + lines.** Build the drawing-object
  infrastructure once — reader/model/mapper/writer for the shared `GShapeObject`
  container — and use it to emit `hp:line`. No binary data.
- **Slice B (next): pictures + binary BinData.** Reuses Slice A's container; adds
  `hp:pic`, image-binary extraction → `BinData/` ZIP entries + manifest registration,
  `img`/`imgRect`/`imgClip`/`imgDim`/`effects`, `shapeComment`.

## Goal (Slice A)

Emit `<hp:line>` (one per HWP line drawing) with its full common-container + line
subtree. On sample 4: `hp:line` == 6, and the shared container tags
(`offset`/`orgSz`/`curSz`/`flip`/`rotationInfo`/`renderingInfo` + `transMatrix`/
`scaMatrix`/`rotMatrix`, `sz`/`pos`/`outMargin`, `lineShape`/`fillBrush`/`winBrush`/
`shadow`/`startPt`/`endPt`) drop from `x9`/`x6` toward parity for the 6 line objects.
On sample 3 (zero drawing objects): **nothing new is emitted** — a hard regression
guard.

**Success** = `hp:line` == 6 on sample 4; the line/container tags leave or shrink in
the section0 miss list; sample 4 section0 match rises; sample 3 output is byte-for-
byte unchanged; output still opens in Hancom Office.

## Correctness gate (differs from secPr — read this)

Unlike `secPr` (stored settings, exact-subtree equality was the gate), drawing-object
geometry is **partly computed** — e.g. `scaMatrix e5="15.04"` is a derived scale, and
Hancom recomputes shape layout when it opens the file. So the gate here is
**count-based (element presence per tag) + structural validity + the sample-3
no-change guard**, exactly like the linesegarray milestone — **not** exact-subtree
equality. Stored values (line endpoints, colors, widths, sizes, z-order, margins) are
mapped faithfully; a few unstored/derived attributes (`instid`, `fillBrush` colors,
some `pos` flags, matrix float formatting) get schema-valid defaults, documented as
such.

## Verified ground truth (sample 4)

Sample 4 contains 9 drawing objects: **6 lines** (`ShapeLine`) + **3 pictures**
(`ShapePicture`), each anchored by a `GShapeObjectControl` (chid `gso `) carrying a
`ShapeComponent`. Slice A handles the 6 lines.

### HWP source (one line, verified)

```
<GShapeObjectControl chid="gso " flags="046A2000" flow="front" halign="left"
  height="1504" height-relto="absolute" hrelto="paper" inline="0"
  instance-id="1111203675" margin-bottom="0" margin-left="0" margin-right="0"
  margin-top="0" number-category="figure" text-side="both" valign="top"
  vrelto="paper" width="0" width-relto="absolute" x="29344" y="24972" z-order="29">
  <ShapeComponent angle="0" chid="$lin" chid0="$lin" flip="0" height="1504"
    initial-height="100" initial-width="100" width="0" x-in-group="0" y-in-group="0">
    <Coord attribute-name="rotation_center" x="0" y="752"/>
    <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
    <Array name="scalerotations"><ScaleRotationMatrix>
      <Matrix attribute-name="scaler"  a="0.0" b="0.0" c="0.0" d="15.04" e="0.0" f="0.0"/>
      <Matrix attribute-name="rotator" a="1.0" b="0.0" c="-0.0" d="1.0"  e="0.0" f="0.0"/>
    </ScaleRotationMatrix></Array>
    <BorderLine attribute-name="line" color="#000000" width="200" stroke="solid"
      line-end="flat" arrow-start="none" arrow-end="none" arrow-start-fill="1"
      arrow-end-fill="1" arrow-start-size="smallest" arrow-end-size="smallest"/>
    <ShapeLine attr="0">
      <Coord attribute-name="p0" x="0" y="0"/>
      <Coord attribute-name="p1" x="100" y="100"/>
    </ShapeLine>
  </ShapeComponent>
</GShapeObjectControl>
```

### Target OWPML (the same line, verified — full child order)

```
<hp:line id="1111203675" zOrder="29" numberingType="PICTURE"
  textWrap="IN_FRONT_OF_TEXT" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None"
  href="" groupLevel="0" instid="37461852" isReverseHV="0">
  <hp:offset x="0" y="0"/>
  <hp:orgSz width="100" height="100"/>
  <hp:curSz width="0" height="1504"/>
  <hp:flip horizontal="0" vertical="0"/>
  <hp:rotationInfo angle="0" centerX="0" centerY="752" rotateimage="0"/>
  <hp:renderingInfo>
    <hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>
    <hc:scaMatrix  e1="0" e2="0" e3="0" e4="0" e5="15.04" e6="0"/>
    <hc:rotMatrix  e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>
  </hp:renderingInfo>
  <hp:lineShape color="#000000" width="200" style="SOLID" endCap="FLAT"
    headStyle="NORMAL" tailStyle="NORMAL" headfill="1" tailfill="1"
    headSz="SMALL_SMALL" tailSz="SMALL_SMALL" outlineStyle="NORMAL" alpha="0"/>
  <hc:fillBrush><hc:winBrush faceColor="#FFFF00" hatchColor="#000000" alpha="0"/></hc:fillBrush>
  <hp:shadow type="NONE" color="#000000" offsetX="0" offsetY="0" alpha="0"/>
  <hc:startPt x="0" y="0"/>
  <hc:endPt x="100" y="100"/>
  <hp:sz width="0" widthRelTo="ABSOLUTE" height="1504" heightRelTo="ABSOLUTE" protect="0"/>
  <hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="1" allowOverlap="0"
    holdAnchorAndSO="0" vertRelTo="PAPER" horzRelTo="PAPER" vertAlign="TOP"
    horzAlign="LEFT" vertOffset="24972" horzOffset="29344"/>
  <hp:outMargin left="0" right="0" top="0" bottom="0"/>
</hp:line>
```

Note the **two namespaces**: `hc:` (core) for `transMatrix`/`scaMatrix`/`rotMatrix`/
`fillBrush`/`winBrush`/`startPt`/`endPt`; `hp:` for the rest. The writer needs both.

### Attribute mapping

**`hp:line` element** (from `GShapeObjectControl`): `id` ← instance-id;
`zOrder` ← z-order; `numberingType="PICTURE"` (const, number-category=figure);
`textWrap` ← flow (`front`→`IN_FRONT_OF_TEXT`, `block`→`TOP_AND_BOTTOM`, default
`TOP_AND_BOTTOM`); `textFlow="BOTH_SIDES"` (text-side=both);
`lock="0"`/`dropcapstyle="None"`/`href=""`/`groupLevel="0"`/`isReverseHV="0"` (const);
`instid` ← default/derived (unstored — see risks).

**`offset`** = `x-in-group`,`y-in-group` (0,0). **`orgSz`** = ShapeComponent
initial-width/height. **`curSz`** = ShapeComponent width/height. **`flip`**:
`horizontal`/`vertical` from ShapeComponent flip bits (flip=0 → 0,0).
**`rotationInfo`**: `angle` ← angle; `centerX`/`centerY` ← `Coord rotation_center`;
`rotateimage="0"` (const for lines).

**`renderingInfo`** three matrices from the three `Matrix` records
(translation→transMatrix, scaler→scaMatrix, rotator→rotMatrix). Matrix mapping:
`e1←a, e2←c, e3←e, e4←b, e5←d, e6←f` (verified: translation a=1,d=1 → e1=1,e5=1;
scaler d=15.04 → e5=15.04). Whole floats emit without trailing `.0` (`"1.0"`→`"1"`);
values are irrelevant to the count-based score.

**`lineShape`** (from `BorderLine`): `color` ← color; `width` ← width;
`style` ← stroke (`solid`→`SOLID`); `endCap` ← line-end (`flat`→`FLAT`);
`headStyle`/`tailStyle` ← arrow-start/end (`none`→`NORMAL`);
`headfill`/`tailfill` ← arrow-start/end-fill; `headSz`/`tailSz` ← arrow sizes
(`smallest`→`SMALL_SMALL`); `outlineStyle="NORMAL"`/`alpha="0"` (const).

**`fillBrush`›`winBrush`** and **`shadow`**: schema-valid defaults
(`winBrush faceColor="#FFFFFF"` unless a Fill record is present; `shadow type="NONE"`).
Exact fill color is unstored for a plain line and count-neutral.

**`startPt`/`endPt`** (from `ShapeLine`): `Coord p0` / `Coord p1` x,y.

**`sz`** = GSO width/height + `widthRelTo`/`heightRelTo` (width-relto=absolute→
`ABSOLUTE`), `protect="0"`. **`pos`** (from GSO): `treatAsChar` ← inline;
`vertRelTo`/`horzRelTo` ← vrelto/hrelto (`paper`→`PAPER`, `paragraph`→`PARA`,
`column`→`COLUMN`); `vertAlign`/`horzAlign` ← valign/halign; `vertOffset`/`horzOffset`
← y/x; the boolean flags (`affectLSpacing`/`flowWithText`/`allowOverlap`/
`holdAnchorAndSO`) from GSO flags with schema-valid defaults. **`outMargin`** = GSO
margin-left/right/top/bottom.

## Architecture (extends the 4 layers; mirrors table handling)

**Model (`hwpmodel/model.py`):**
- `HwpShapeComponent(angle, flip, initial_width, initial_height, width, height,
  center_x, center_y, trans_matrix, scaler_matrix, rotator_matrix)` where each matrix
  is a 6-tuple/list `[a,b,c,d,e,f]`.
- `HwpLineShape(color, width, stroke, line_end, arrow_start, arrow_end,
  arrow_start_fill, arrow_end_fill, arrow_start_size, arrow_end_size, p0, p1)`
  (`p0`/`p1` are `(x,y)` tuples).
- `HwpDrawing(kind, instance_id, z_order, flow, text_side, x, y, width, height,
  hrelto, vrelto, halign, valign, inline, margin_left, margin_right, margin_top,
  margin_bottom, width_relto, height_relto, component: "HwpShapeComponent" = None,
  line: "HwpLineShape" = None)`.
- `HwpRun` gains `drawing: "HwpDrawing" = None` (parallel to `table`).

**OWPML model (`owpml/model.py`):** a `Line` dataclass plus child dataclasses
(`Offset`, `OrgSz`, `CurSz`, `Flip`, `RotationInfo`, `Matrix`, `RenderingInfo`,
`LineShape`, `WinBrush`, `Shadow`, `Pt`, `ShapeSz`, `ShapePos`, `ShapeOutMargin`).
`Run` gains `drawing: "Line" = None`. (Distinct names from the table `Sz`/`Pos` usage,
which the table writer sets inline; drawing uses its own dataclasses.)

**Reader (`hwpmodel/reader.py`):** `parse_paragraph` gains a `GShapeObjectControl`
branch (sibling to `TableControl`): flush the current run, then append a run whose
`drawing` is built by `_parse_drawing(gso_el)`. `_parse_drawing` reads the GSO attrs,
the nested `ShapeComponent` (matrices, rotation center, orgSz/curSz/flip), the
`BorderLine`, and the `ShapeLine` points. Only `chid0="$lin"` components produce a
`line`; other component kinds are skipped in Slice A (defensive — produce no drawing,
so pictures don't crash before Slice B).

**Mapper (`mapper/drawing.py`, new):** `map_drawing(hd) -> Line`; faithful passthrough
+ enum tables + documented defaults. `map_paragraph` (in `mapper/body.py`) routes a
run with `drawing` set to `Run(..., drawing=map_drawing(r.drawing))`, mirroring the
existing table routing.

**Writer (`owpml/section_writer.py`):** add `_hc(tag)` helper for the core namespace;
`_write_line(run_el, line)` emits the full subtree in child order; `_write_run` emits
the drawing when `run.drawing` is set (mirrors the `run.table` branch).

## Error handling / regression safety

- Sample 3 has no `GShapeObjectControl` → no drawing runs → byte-identical output.
  This is asserted directly (convert sample 3 before/after; drawing tags absent).
- A `GShapeObjectControl` whose `ShapeComponent` is a non-line kind (`$pic`, `$rec`,
  `$con`…) produces **no** drawing in Slice A (returns `None`; the run is skipped) —
  so picture-bearing docs don't crash or emit malformed lines before Slice B.
- Missing/malformed matrices, points, or border → schema-valid defaults (identity
  matrix, 0 points, black solid line); never crash.

## Testing strategy (TDD)

- **Reader:** a known line `GShapeObjectControl` in sample 4 parses to an `HwpDrawing`
  with `kind="line"`, expected `instance_id`/`z_order`/points/`width`/`height`;
  total line drawings across sample 4 == 6; a `$pic` component yields no line drawing.
- **Mapper:** `map_drawing` maps a constructed `HwpDrawing` to a `Line` with expected
  child values; matrix mapping `a/b/c/d/e/f → e1..e6`; enum maps
  (`front→IN_FRONT_OF_TEXT`, `solid→SOLID`, `flat→FLAT`, `paper→PAPER`).
- **Writer:** `_write_line` emits `hp:line` with the exact child order and both
  namespaces (`hc:transMatrix`, `hp:lineShape`, etc.); a run with `drawing` set emits
  one `hp:line`; a run without stays unchanged.
- **End-to-end / fidelity:** convert sample 4 → `hp:line` == 6; line/container tags
  leave-or-shrink in the section0 miss list; section0 match rises. Convert sample 3 →
  output unchanged, zero `hp:line`. Full regression suite green.

## Non-goals (Slice A)

- Pictures (`hp:pic`), binary `BinData`, `img`/`imgRect`/`imgClip`/`imgDim`/`effects`,
  `shapeComment` — all Slice B.
- Rectangles, ellipses, arcs, polygons, curves, text boxes, grouped/container shapes,
  OLE — not present in the samples; out of scope.
- Exact geometry/matrix values matching Hancom's recomputed layout (unnecessary;
  count-based + Hancom recomputes on open).

## Key risks

- **Two-namespace writer** — `hc:` vs `hp:` must be exact or the file won't open;
  mitigated by a writer test asserting the namespace of each child and by mirroring
  Hancom's verified structure.
- **`instid` unstored** — Hancom's `instid` (37461852) has no clear HWP source and
  differs from `instance-id`; emitted as a documented default. Count-neutral.
- **Non-line component kinds** — must be silently skipped in Slice A, not crash;
  mitigated by the `chid0=="$lin"` guard and a reader test that a `$pic` yields no line.
- **Sample-3 regression** — the paragraph-walk change must not alter non-drawing
  paragraphs; mitigated by the byte-identical sample-3 assertion and the existing
  section-writer regression suite.
- **Single-sample validation** — only sample 4 exercises lines; mitigated by unit
  tests on constructed inputs for the mapper/writer and by the count-based (not
  exact) gate.
