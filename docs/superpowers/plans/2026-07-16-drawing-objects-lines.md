# Drawing Objects — Slice A (GSO container + lines) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `<hp:line>` (one per HWP line drawing) with its full common-container + line subtree, from `GShapeObjectControl`/`ShapeComponent`/`ShapeLine`. On sample 4: `hp:line` == 6. On sample 3 (no drawings): output byte-identical.

**Architecture:** Extends the 4-layer pipeline exactly as tables are handled. Reader gains a `GShapeObjectControl` branch in `parse_paragraph` (sibling of the `TableControl` branch) → `HwpRun.drawing`. Mapper `mapper/drawing.py` → `Run.drawing`. Writer `_write_line` emits the subtree (two namespaces: `hp:` and `hc:`).

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc xml`), pytest.

## Global Constraints

- **Python 3.9 floor:** NO PEP 604 `X | None`. Forward-ref-string defaults (`x: "T" = None`), `field(default_factory=...)`.
- **Run tests with `.venv/bin/python -m pytest`** — plain `python`/`python3` lacks `hwp5proc` (~13 spurious failures).
- **Correctness gate is count-based, NOT exact-subtree** (line geometry is computed/recomputed by Hancom): `hp:line`==6 on sample 4, container/line tags leave-or-shrink in the section0 miss list, file stays valid. Stored values mapped faithfully; unstored/computed attrs (`instid`, `fillBrush` colors, matrix float formatting, some `pos` flags) use documented schema-valid defaults.
- **Sample-3 regression guard:** sample 3 has zero `GShapeObjectControl`; its converted output must be byte-identical to before this milestone. Non-line component kinds (`$pic`, `$rec`, …) must be silently skipped (return `None`), never crash — pictures are Slice B.
- **Two namespaces:** `hc:` (core) for `transMatrix`/`scaMatrix`/`rotMatrix`/`fillBrush`/`winBrush`/`startPt`/`endPt`; `hp:` for the rest. `NS["hc"]` exists in `hwp2hwpx/constants.py`.
- Samples at `samples/4.*.hwp[x]` (present locally). Reader unit tests use synthetic XML snippets (sample-independent); the sample-4 count lives in the end-to-end task.

### Verified matrix mapping (source `Matrix a/b/c/d/e/f` → target `e1..e6`)

`e1←a, e2←c, e3←e, e4←b, e5←d, e6←f`. (Verified: translation a=1,d=1 → e1=1,e5=1; scaler d=15.04 → e5=15.04.) Whole floats emit without trailing `.0`.

---

### Task 1: HWP-side drawing dataclasses

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py`
- Test: `tests/test_model_drawing.py`

**Interfaces:**
- Produces: `HwpShapeComponent`, `HwpLineShape`, `HwpDrawing`; `HwpRun.drawing` field. Consumed by reader (Task 3) and mapper (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_drawing.py
from hwp2hwpx.hwpmodel.model import (
    HwpShapeComponent, HwpLineShape, HwpDrawing, HwpRun,
)


def test_drawing_defaults():
    c = HwpShapeComponent()
    assert c.trans_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert HwpLineShape().stroke == "solid"
    assert HwpLineShape().p0 == (0, 0)
    d = HwpDrawing()
    assert d.kind == "line" and d.component is None and d.line is None


def test_hwprun_carries_drawing():
    r = HwpRun(char_shape_id=0, drawing=HwpDrawing(instance_id=42))
    assert r.drawing.instance_id == 42
    assert r.table is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_drawing.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add the dataclasses**

Add to `hwp2hwpx/hwpmodel/model.py` (after `HwpTable`, near the other content dataclasses; `field` already imported):

```python
@dataclass
class HwpShapeComponent:
    angle: int = 0
    flip: int = 0
    initial_width: int = 0
    initial_height: int = 0
    width: int = 0
    height: int = 0
    center_x: int = 0
    center_y: int = 0
    trans_matrix: list = field(default_factory=lambda: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    scaler_matrix: list = field(default_factory=lambda: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    rotator_matrix: list = field(default_factory=lambda: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])


@dataclass
class HwpLineShape:
    color: str = "#000000"
    width: int = 0
    stroke: str = "solid"
    line_end: str = "flat"
    arrow_start: str = "none"
    arrow_end: str = "none"
    arrow_start_fill: int = 1
    arrow_end_fill: int = 1
    arrow_start_size: str = "smallest"
    arrow_end_size: str = "smallest"
    p0: tuple = (0, 0)
    p1: tuple = (0, 0)


@dataclass
class HwpDrawing:
    kind: str = "line"
    instance_id: int = 0
    z_order: int = 0
    flow: str = "block"
    text_side: str = "both"
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    hrelto: str = "paper"
    vrelto: str = "paper"
    halign: str = "left"
    valign: str = "top"
    inline: int = 0
    margin_left: int = 0
    margin_right: int = 0
    margin_top: int = 0
    margin_bottom: int = 0
    width_relto: str = "absolute"
    height_relto: str = "absolute"
    component: "HwpShapeComponent" = None
    line: "HwpLineShape" = None
```

Modify `HwpRun` to add a `drawing` field (keep existing fields and the `text` property):

```python
@dataclass
class HwpRun:
    char_shape_id: int
    contents: list = field(default_factory=list)
    table: "HwpTable" = None
    drawing: "HwpDrawing" = None

    @property
    def text(self):
        return "".join(c for c in self.contents if isinstance(c, str))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_drawing.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py tests/test_model_drawing.py
git commit -m "feat: HWP-side drawing (GSO line) dataclasses"
```

---

### Task 2: OWPML-side Line dataclasses

**Files:**
- Modify: `hwp2hwpx/owpml/model.py`
- Test: `tests/test_owpml_model_line.py`

**Interfaces:**
- Produces: `Line` + children (`Offset`, `OrgSz`, `CurSz`, `Flip`, `RotationInfo`, `Matrix`, `RenderingInfo`, `LineShape`, `WinBrush`, `Shadow`, `Pt`, `ShapeSz`, `ShapePos`, `ShapeOutMargin`); `Run.drawing`. Field names are the contract for mapper (Task 4) and writer (Task 5).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_owpml_model_line.py
from hwp2hwpx.owpml.model import (
    Line, Offset, OrgSz, CurSz, Flip, RotationInfo, Matrix, RenderingInfo,
    LineShape, WinBrush, Shadow, Pt, ShapeSz, ShapePos, ShapeOutMargin, Run,
)


def test_line_and_children_defaults():
    assert Matrix().e1 == "1" and Matrix().e5 == "1"
    assert LineShape().style == "SOLID"
    assert WinBrush().face_color == "#FFFFFF"
    assert Shadow().type == "NONE"
    assert ShapeSz().width_rel_to == "ABSOLUTE"
    assert ShapePos().horz_rel_to == "PAPER"
    ln = Line(id=7)
    assert ln.id == 7 and ln.text_wrap == "TOP_AND_BOTTOM"
    assert ln.line_shape is None and ln.start_pt is None


def test_run_carries_drawing():
    r = Run(char_pr_id=0, drawing=Line(id=9))
    assert r.drawing.id == 9 and r.table is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_owpml_model_line.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add the dataclasses**

Add to `hwp2hwpx/owpml/model.py` (after `Table`, near the end; `field` already imported):

```python
@dataclass
class Offset:
    x: int = 0
    y: int = 0


@dataclass
class OrgSz:
    width: int = 0
    height: int = 0


@dataclass
class CurSz:
    width: int = 0
    height: int = 0


@dataclass
class Flip:
    horizontal: int = 0
    vertical: int = 0


@dataclass
class RotationInfo:
    angle: int = 0
    center_x: int = 0
    center_y: int = 0
    rotate_image: int = 0


@dataclass
class Matrix:
    e1: str = "1"
    e2: str = "0"
    e3: str = "0"
    e4: str = "0"
    e5: str = "1"
    e6: str = "0"


@dataclass
class RenderingInfo:
    trans: "Matrix" = None
    sca: "Matrix" = None
    rot: "Matrix" = None


@dataclass
class LineShape:
    color: str = "#000000"
    width: int = 0
    style: str = "SOLID"
    end_cap: str = "FLAT"
    head_style: str = "NORMAL"
    tail_style: str = "NORMAL"
    head_fill: int = 1
    tail_fill: int = 1
    head_sz: str = "SMALL_SMALL"
    tail_sz: str = "SMALL_SMALL"
    outline_style: str = "NORMAL"
    alpha: int = 0


@dataclass
class WinBrush:
    face_color: str = "#FFFFFF"
    hatch_color: str = "#000000"
    alpha: int = 0


@dataclass
class Shadow:
    type: str = "NONE"
    color: str = "#000000"
    offset_x: int = 0
    offset_y: int = 0
    alpha: int = 0


@dataclass
class Pt:
    x: int = 0
    y: int = 0


@dataclass
class ShapeSz:
    width: int = 0
    width_rel_to: str = "ABSOLUTE"
    height: int = 0
    height_rel_to: str = "ABSOLUTE"
    protect: int = 0


@dataclass
class ShapePos:
    treat_as_char: int = 0
    affect_lspacing: int = 0
    flow_with_text: int = 1
    allow_overlap: int = 0
    hold_anchor_and_so: int = 0
    vert_rel_to: str = "PAPER"
    horz_rel_to: str = "PAPER"
    vert_align: str = "TOP"
    horz_align: str = "LEFT"
    vert_offset: int = 0
    horz_offset: int = 0


@dataclass
class ShapeOutMargin:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class Line:
    id: int = 0
    z_order: int = 0
    text_wrap: str = "TOP_AND_BOTTOM"
    text_flow: str = "BOTH_SIDES"
    instid: int = 0
    offset: "Offset" = None
    org_sz: "OrgSz" = None
    cur_sz: "CurSz" = None
    flip: "Flip" = None
    rotation_info: "RotationInfo" = None
    rendering_info: "RenderingInfo" = None
    line_shape: "LineShape" = None
    win_brush: "WinBrush" = None
    shadow: "Shadow" = None
    start_pt: "Pt" = None
    end_pt: "Pt" = None
    sz: "ShapeSz" = None
    pos: "ShapePos" = None
    out_margin: "ShapeOutMargin" = None
```

Modify `Run` to add `drawing`:

```python
@dataclass
class Run:
    char_pr_id: int
    texts: list = field(default_factory=list)
    table: "Table" = None
    drawing: "Line" = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_owpml_model_line.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/model.py tests/test_owpml_model_line.py
git commit -m "feat: OWPML-side Line dataclasses"
```

---

### Task 3: Reader parses `GShapeObjectControl`

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`
- Test: `tests/test_reader_drawing.py`

**Interfaces:**
- Consumes: `HwpShapeComponent`, `HwpLineShape`, `HwpDrawing` (Task 1); existing `_int`.
- Produces: `_parse_drawing(gso_el) -> HwpDrawing | None`; a `GShapeObjectControl` branch in `parse_paragraph` that appends a run with `drawing` set.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader_drawing.py
from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing, parse_paragraph

LINE_GSO = '''
<GShapeObjectControl chid="gso " flow="front" halign="left" height="1504"
  height-relto="absolute" hrelto="paper" inline="0" instance-id="1111203675"
  margin-bottom="0" margin-left="0" margin-right="0" margin-top="0"
  number-category="figure" text-side="both" valign="top" vrelto="paper"
  width="0" width-relto="absolute" x="29344" y="24972" z-order="29">
  <ShapeComponent angle="0" chid="$lin" chid0="$lin" flip="0" height="1504"
    initial-height="100" initial-width="100" width="0" x-in-group="0" y-in-group="0">
    <Coord attribute-name="rotation_center" x="0" y="752"/>
    <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
    <Array name="scalerotations"><ScaleRotationMatrix>
      <Matrix attribute-name="scaler" a="0.0" b="0.0" c="0.0" d="15.04" e="0.0" f="0.0"/>
      <Matrix attribute-name="rotator" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
    </ScaleRotationMatrix></Array>
    <BorderLine attribute-name="line" color="#000000" width="200" stroke="solid"
      line-end="flat" arrow-start="none" arrow-end="none" arrow-start-fill="1"
      arrow-end-fill="1" arrow-start-size="smallest" arrow-end-size="smallest"/>
    <ShapeLine attr="0">
      <Coord attribute-name="p0" x="0" y="0"/>
      <Coord attribute-name="p1" x="100" y="100"/>
    </ShapeLine>
  </ShapeComponent>
</GShapeObjectControl>'''

PIC_GSO = '''
<GShapeObjectControl chid="gso " instance-id="5" z-order="1">
  <ShapeComponent chid="$pic" chid0="$pic" width="10" height="10"
    initial-width="10" initial-height="10"/>
</GShapeObjectControl>'''


def test_parse_line_drawing():
    d = _parse_drawing(etree.fromstring(LINE_GSO))
    assert d is not None and d.kind == "line"
    assert d.instance_id == 1111203675 and d.z_order == 29
    assert d.x == 29344 and d.y == 24972
    assert d.flow == "front" and d.inline == 0
    c = d.component
    assert c.initial_width == 100 and c.width == 0 and c.height == 1504
    assert c.center_x == 0 and c.center_y == 752
    assert c.trans_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert c.scaler_matrix[3] == 15.04     # d position
    assert d.line.color == "#000000" and d.line.width == 200
    assert d.line.p0 == (0, 0) and d.line.p1 == (100, 100)


def test_non_line_component_yields_none():
    assert _parse_drawing(etree.fromstring(PIC_GSO)) is None


def test_parse_paragraph_puts_drawing_in_its_own_run():
    para = etree.fromstring(
        '<Paragraph parashape-id="0" style-id="0"><LineSeg>' + LINE_GSO +
        '</LineSeg></Paragraph>')
    p = parse_paragraph(para)
    drawing_runs = [r for r in p.runs if r.drawing is not None]
    assert len(drawing_runs) == 1
    assert drawing_runs[0].drawing.instance_id == 1111203675
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reader_drawing.py -v`
Expected: FAIL (`ImportError: _parse_drawing`).

- [ ] **Step 3: Add the parser helpers and the parse_paragraph branch**

In `hwp2hwpx/hwpmodel/reader.py`, extend the `.model` import to include `HwpShapeComponent, HwpLineShape, HwpDrawing`. Add a float helper next to `_int`:

```python
def _float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
```

Add the drawing parsers (place above `parse_paragraph`):

```python
def _matrix_values(m_el):
    if m_el is None:
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    return [_float(m_el.get(k)) for k in ("a", "b", "c", "d", "e", "f")]


def _parse_shape_component(comp_el):
    center = comp_el.find("Coord[@attribute-name='rotation_center']")
    trans = comp_el.find("Matrix[@attribute-name='translation']")
    scaler = comp_el.find(".//Matrix[@attribute-name='scaler']")
    rotator = comp_el.find(".//Matrix[@attribute-name='rotator']")
    return HwpShapeComponent(
        angle=_int(comp_el.get("angle")),
        flip=_int(comp_el.get("flip")),
        initial_width=_int(comp_el.get("initial-width")),
        initial_height=_int(comp_el.get("initial-height")),
        width=_int(comp_el.get("width")),
        height=_int(comp_el.get("height")),
        center_x=_int(center.get("x")) if center is not None else 0,
        center_y=_int(center.get("y")) if center is not None else 0,
        trans_matrix=_matrix_values(trans),
        scaler_matrix=_matrix_values(scaler),
        rotator_matrix=_matrix_values(rotator),
    )


def _parse_line_shape(comp_el):
    bl = comp_el.find("BorderLine[@attribute-name='line']")
    if bl is None:
        bl = etree.Element("BorderLine")
    sl = comp_el.find("ShapeLine")
    p0 = sl.find("Coord[@attribute-name='p0']") if sl is not None else None
    p1 = sl.find("Coord[@attribute-name='p1']") if sl is not None else None
    return HwpLineShape(
        color=bl.get("color") or "#000000",
        width=_int(bl.get("width")),
        stroke=bl.get("stroke") or "solid",
        line_end=bl.get("line-end") or "flat",
        arrow_start=bl.get("arrow-start") or "none",
        arrow_end=bl.get("arrow-end") or "none",
        arrow_start_fill=_int(bl.get("arrow-start-fill"), 1),
        arrow_end_fill=_int(bl.get("arrow-end-fill"), 1),
        arrow_start_size=bl.get("arrow-start-size") or "smallest",
        arrow_end_size=bl.get("arrow-end-size") or "smallest",
        p0=(_int(p0.get("x")), _int(p0.get("y"))) if p0 is not None else (0, 0),
        p1=(_int(p1.get("x")), _int(p1.get("y"))) if p1 is not None else (0, 0),
    )


def _parse_drawing(gso_el):
    """GShapeObjectControl -> HwpDrawing. Slice A: only line ($lin) components;
    other kinds ($pic, $rec, ...) return None (skipped until Slice B)."""
    comp = gso_el.find("ShapeComponent")
    if comp is None:
        return None
    chid0 = (comp.get("chid0") or comp.get("chid") or "").strip()
    if chid0 != "$lin":
        return None
    return HwpDrawing(
        kind="line",
        instance_id=_int(gso_el.get("instance-id")),
        z_order=_int(gso_el.get("z-order")),
        flow=gso_el.get("flow") or "block",
        text_side=gso_el.get("text-side") or "both",
        x=_int(gso_el.get("x")),
        y=_int(gso_el.get("y")),
        width=_int(gso_el.get("width")),
        height=_int(gso_el.get("height")),
        hrelto=gso_el.get("hrelto") or "paper",
        vrelto=gso_el.get("vrelto") or "paper",
        halign=gso_el.get("halign") or "left",
        valign=gso_el.get("valign") or "top",
        inline=_int(gso_el.get("inline")),
        margin_left=_int(gso_el.get("margin-left")),
        margin_right=_int(gso_el.get("margin-right")),
        margin_top=_int(gso_el.get("margin-top")),
        margin_bottom=_int(gso_el.get("margin-bottom")),
        width_relto=gso_el.get("width-relto") or "absolute",
        height_relto=gso_el.get("height-relto") or "absolute",
        component=_parse_shape_component(comp),
        line=_parse_line_shape(comp),
    )
```

In `parse_paragraph`, add a branch to the `for child in para_el.findall("LineSeg/*")` loop, after the existing `elif child.tag == "TableControl":` block:

```python
        elif child.tag == "GShapeObjectControl":
            drawing = _parse_drawing(child)
            if drawing is not None:
                flush()
                runs.append(HwpRun(
                    char_shape_id=_int(child.get("charshape-id")),
                    contents=[],
                    drawing=drawing,
                ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_reader_drawing.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run reader regression subset**

Run: `.venv/bin/python -m pytest tests/test_reader_body.py tests/test_reader_tables.py tests/test_reader_inline.py -v`
Expected: PASS (the new branch is additive; non-drawing paragraphs unaffected).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_drawing.py
git commit -m "feat: reader parses GShapeObjectControl line drawings"
```

---

### Task 4: Mapper `map_drawing`

**Files:**
- Create: `hwp2hwpx/mapper/drawing.py`
- Modify: `hwp2hwpx/mapper/body.py`
- Test: `tests/test_mapper_drawing.py`

**Interfaces:**
- Consumes: `HwpDrawing` (Task 1), OWPML `Line` + children (Task 2).
- Produces: `map_drawing(hd) -> Line | None`; `map_paragraph` routes a run with `drawing` set.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mapper_drawing.py
from hwp2hwpx.hwpmodel.model import (
    HwpDrawing, HwpShapeComponent, HwpLineShape, HwpRun, HwpParagraph,
)
from hwp2hwpx.mapper.drawing import map_drawing
from hwp2hwpx.mapper.body import map_paragraph


def _line_drawing():
    return HwpDrawing(
        kind="line", instance_id=111, z_order=29, flow="front", inline=0,
        x=29344, y=24972, width=0, height=1504, hrelto="paper", vrelto="paper",
        halign="left", valign="top", width_relto="absolute",
        component=HwpShapeComponent(
            initial_width=100, initial_height=100, width=0, height=1504,
            center_x=0, center_y=752,
            trans_matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            scaler_matrix=[0.0, 0.0, 0.0, 15.04, 0.0, 0.0],
            rotator_matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
        line=HwpLineShape(color="#000000", width=200, stroke="solid",
                          line_end="flat", p0=(0, 0), p1=(100, 100)),
    )


def test_map_line_container_and_geometry():
    ln = map_drawing(_line_drawing())
    assert ln.id == 111 and ln.z_order == 29
    assert ln.text_wrap == "IN_FRONT_OF_TEXT"
    assert ln.org_sz.width == 100 and ln.cur_sz.height == 1504
    assert ln.rotation_info.center_y == 752
    assert ln.pos.horz_rel_to == "PAPER" and ln.pos.horz_offset == 29344
    assert ln.pos.vert_offset == 24972
    assert ln.sz.width_rel_to == "ABSOLUTE"
    assert ln.out_margin.left == 0


def test_matrix_mapping_abcdef_to_e1e6():
    ln = map_drawing(_line_drawing())
    # translation identity -> e1=1,e5=1
    assert (ln.rendering_info.trans.e1, ln.rendering_info.trans.e5) == ("1", "1")
    # scaler d=15.04 -> e5
    assert ln.rendering_info.sca.e5 == "15.04"
    assert ln.rendering_info.sca.e1 == "0"


def test_line_shape_and_points():
    ln = map_drawing(_line_drawing())
    assert ln.line_shape.style == "SOLID" and ln.line_shape.end_cap == "FLAT"
    assert ln.line_shape.width == 200
    assert (ln.start_pt.x, ln.start_pt.y) == (0, 0)
    assert (ln.end_pt.x, ln.end_pt.y) == (100, 100)


def test_none_and_non_line_map_to_none():
    assert map_drawing(None) is None
    assert map_drawing(HwpDrawing(kind="pic")) is None


def test_map_paragraph_routes_drawing_run():
    hpar = HwpParagraph(para_shape_id=0, style_id=0,
                        runs=[HwpRun(char_shape_id=0, drawing=_line_drawing())])
    para = map_paragraph(hpar, 0)
    assert len(para.runs) == 1
    assert para.runs[0].drawing is not None
    assert para.runs[0].drawing.id == 111
    assert para.runs[0].table is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mapper_drawing.py -v`
Expected: FAIL with `ModuleNotFoundError: hwp2hwpx.mapper.drawing`.

- [ ] **Step 3: Create `hwp2hwpx/mapper/drawing.py`**

```python
"""Map an HWP line drawing (GShapeObjectControl) to an OWPML Line."""
from ..owpml.model import (
    Line, Offset, OrgSz, CurSz, Flip, RotationInfo, Matrix, RenderingInfo,
    LineShape, WinBrush, Shadow, Pt, ShapeSz, ShapePos, ShapeOutMargin,
)

_TEXT_WRAP = {"front": "IN_FRONT_OF_TEXT", "back": "BEHIND_TEXT",
              "block": "TOP_AND_BOTTOM", "square": "SQUARE",
              "tight": "TIGHT", "through": "THROUGH"}
_STROKE = {"solid": "SOLID", "none": "NONE", "dash": "DASH", "dot": "DOT",
           "dash-dot": "DASH_DOT"}
_LINE_END = {"flat": "FLAT", "round": "ROUND", "square": "SQUARE"}
_ARROW_STYLE = {"none": "NORMAL", "arrow": "ARROW", "spear": "SPEAR",
                "concave_arrow": "CONCAVE_ARROW"}
_ARROW_SIZE = {"smallest": "SMALL_SMALL", "small": "SMALL_SMALL",
               "medium": "MEDIUM_MEDIUM", "large": "LARGE_LARGE"}
_SZ_RELTO = {"absolute": "ABSOLUTE", "relative": "RELATIVE"}
_POS_RELTO = {"paper": "PAPER", "page": "PAGE", "paragraph": "PARA",
              "column": "COLUMN", "char": "CHAR"}
_HALIGN = {"left": "LEFT", "center": "CENTER", "right": "RIGHT",
           "inside": "INSIDE", "outside": "OUTSIDE"}
_VALIGN = {"top": "TOP", "center": "CENTER", "bottom": "BOTTOM",
           "inside": "INSIDE", "outside": "OUTSIDE"}


def _fmt(x):
    # matrix floats: 1.0 -> "1", 15.04 -> "15.04". Count-neutral (values ignored
    # by the count-based score); formatted to resemble Hancom's output.
    return str(int(x)) if float(x) == int(x) else ("%g" % float(x))


def _matrix(vals):
    a, b, c, d, e, f = vals
    return Matrix(e1=_fmt(a), e2=_fmt(c), e3=_fmt(e),
                  e4=_fmt(b), e5=_fmt(d), e6=_fmt(f))


def map_drawing(hd):
    if hd is None or hd.kind != "line" or hd.component is None or hd.line is None:
        return None
    comp = hd.component
    ls = hd.line
    return Line(
        id=hd.instance_id,
        z_order=hd.z_order,
        text_wrap=_TEXT_WRAP.get(hd.flow, "TOP_AND_BOTTOM"),
        offset=Offset(0, 0),
        org_sz=OrgSz(comp.initial_width, comp.initial_height),
        cur_sz=CurSz(comp.width, comp.height),
        flip=Flip(comp.flip & 1, (comp.flip >> 1) & 1),
        rotation_info=RotationInfo(angle=comp.angle, center_x=comp.center_x,
                                   center_y=comp.center_y, rotate_image=0),
        rendering_info=RenderingInfo(trans=_matrix(comp.trans_matrix),
                                     sca=_matrix(comp.scaler_matrix),
                                     rot=_matrix(comp.rotator_matrix)),
        line_shape=LineShape(
            color=ls.color, width=ls.width,
            style=_STROKE.get(ls.stroke, "SOLID"),
            end_cap=_LINE_END.get(ls.line_end, "FLAT"),
            head_style=_ARROW_STYLE.get(ls.arrow_start, "NORMAL"),
            tail_style=_ARROW_STYLE.get(ls.arrow_end, "NORMAL"),
            head_fill=ls.arrow_start_fill, tail_fill=ls.arrow_end_fill,
            head_sz=_ARROW_SIZE.get(ls.arrow_start_size, "SMALL_SMALL"),
            tail_sz=_ARROW_SIZE.get(ls.arrow_end_size, "SMALL_SMALL")),
        win_brush=WinBrush(),
        shadow=Shadow(),
        start_pt=Pt(ls.p0[0], ls.p0[1]),
        end_pt=Pt(ls.p1[0], ls.p1[1]),
        sz=ShapeSz(width=hd.width, width_rel_to=_SZ_RELTO.get(hd.width_relto, "ABSOLUTE"),
                   height=hd.height, height_rel_to=_SZ_RELTO.get(hd.height_relto, "ABSOLUTE")),
        pos=ShapePos(treat_as_char=hd.inline,
                     vert_rel_to=_POS_RELTO.get(hd.vrelto, "PAPER"),
                     horz_rel_to=_POS_RELTO.get(hd.hrelto, "PAPER"),
                     vert_align=_VALIGN.get(hd.valign, "TOP"),
                     horz_align=_HALIGN.get(hd.halign, "LEFT"),
                     vert_offset=hd.y, horz_offset=hd.x),
        out_margin=ShapeOutMargin(hd.margin_left, hd.margin_right,
                                  hd.margin_top, hd.margin_bottom),
    )
```

- [ ] **Step 4: Wire into `map_paragraph`**

In `hwp2hwpx/mapper/body.py`, add a `drawing` branch in the `for r in hpar.runs` loop of `map_paragraph`, between the `table` branch and the `else`:

```python
        if getattr(r, "table", None) is not None:
            from .table import map_table
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[],
                            table=map_table(r.table)))
        elif getattr(r, "drawing", None) is not None:
            from .drawing import map_drawing
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[],
                            drawing=map_drawing(r.drawing)))
        else:
            runs.append(Run(char_pr_id=r.char_shape_id,
                            texts=_map_contents(r.contents)))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_mapper_drawing.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Run mapper regression subset**

Run: `.venv/bin/python -m pytest tests/test_mapper_body.py tests/test_mapper_table.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/mapper/drawing.py hwp2hwpx/mapper/body.py tests/test_mapper_drawing.py
git commit -m "feat: map HWP line drawing to OWPML Line"
```

---

### Task 5: Writer emits `hp:line`

**Files:**
- Modify: `hwp2hwpx/owpml/section_writer.py`
- Test: `tests/test_section_writer_line.py`

**Interfaces:**
- Consumes: OWPML `Line` + children (Task 2), `Run.drawing`.
- Produces: `_hc(tag)` helper; `_write_line(run_el, line)`; `_write_run` emits the drawing when `run.drawing` is set.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_section_writer_line.py
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import (
    Section, Para, Run, Line, Offset, OrgSz, CurSz, Flip, RotationInfo, Matrix,
    RenderingInfo, LineShape, WinBrush, Shadow, Pt, ShapeSz, ShapePos,
    ShapeOutMargin,
)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HC = "http://www.hancom.co.kr/hwpml/2011/core"


def _qp(t):
    return "{%s}%s" % (HP, t)


def _qc(t):
    return "{%s}%s" % (HC, t)


def _line():
    return Line(
        id=111, z_order=29, text_wrap="IN_FRONT_OF_TEXT",
        offset=Offset(0, 0), org_sz=OrgSz(100, 100), cur_sz=CurSz(0, 1504),
        flip=Flip(0, 0),
        rotation_info=RotationInfo(0, 0, 752, 0),
        rendering_info=RenderingInfo(trans=Matrix(), sca=Matrix(e5="15.04"),
                                     rot=Matrix()),
        line_shape=LineShape(color="#000000", width=200),
        win_brush=WinBrush(), shadow=Shadow(),
        start_pt=Pt(0, 0), end_pt=Pt(100, 100),
        sz=ShapeSz(width=0, height=1504),
        pos=ShapePos(horz_offset=29344, vert_offset=24972),
        out_margin=ShapeOutMargin(),
    )


def _root(section):
    return etree.fromstring(section_xml(section).split(b"?>", 1)[1])


def test_line_emitted_with_correct_children_and_namespaces():
    sec = Section(paras=[Para(id=0, para_pr_id=0,
                              runs=[Run(char_pr_id=0, drawing=_line())])])
    line = _root(sec).find(".//" + _qp("line"))
    assert line is not None
    assert line.get("id") == "111" and line.get("zOrder") == "29"
    kids = [etree.QName(c).localname for c in line]
    assert kids == ["offset", "orgSz", "curSz", "flip", "rotationInfo",
                    "renderingInfo", "lineShape", "fillBrush", "shadow",
                    "startPt", "endPt", "sz", "pos", "outMargin"]
    # namespace checks: matrices + points + brush are hc:, rest hp:
    ri = line.find(_qp("renderingInfo"))
    assert ri.find(_qc("transMatrix")) is not None
    assert ri.find(_qc("scaMatrix")).get("e5") == "15.04"
    assert line.find(_qc("startPt")).get("x") == "0"
    assert line.find(_qc("endPt")).get("y") == "100"
    assert line.find(_qc("fillBrush")).find(_qc("winBrush")) is not None
    assert line.find(_qp("lineShape")).get("style") == "SOLID"
    assert line.find(_qp("pos")).get("horzOffset") == "29344"


def test_run_without_drawing_emits_no_line():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])])
    assert _root(sec).find(".//" + _qp("line")) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_section_writer_line.py -v`
Expected: FAIL (no `_write_line`; no drawing emission).

- [ ] **Step 3: Add `_hc`, `_write_line`, and the `_write_run` branch**

In `hwp2hwpx/owpml/section_writer.py`, add the core-namespace helper next to `_hp`:

```python
def _hc(tag):
    return "{%s}%s" % (NS["hc"], tag)
```

Add `_write_line` (place near `_write_table`):

```python
def _write_line(run_el, ln):
    e = etree.SubElement(run_el, _hp("line"))
    for k, v in (("id", str(ln.id)), ("zOrder", str(ln.z_order)),
                 ("numberingType", "PICTURE"), ("textWrap", ln.text_wrap),
                 ("textFlow", ln.text_flow), ("lock", "0"),
                 ("dropcapstyle", "None"), ("href", ""), ("groupLevel", "0"),
                 ("instid", str(ln.instid)), ("isReverseHV", "0")):
        e.set(k, v)
    off = etree.SubElement(e, _hp("offset"))
    off.set("x", str(ln.offset.x)); off.set("y", str(ln.offset.y))
    osz = etree.SubElement(e, _hp("orgSz"))
    osz.set("width", str(ln.org_sz.width)); osz.set("height", str(ln.org_sz.height))
    csz = etree.SubElement(e, _hp("curSz"))
    csz.set("width", str(ln.cur_sz.width)); csz.set("height", str(ln.cur_sz.height))
    fl = etree.SubElement(e, _hp("flip"))
    fl.set("horizontal", str(ln.flip.horizontal))
    fl.set("vertical", str(ln.flip.vertical))
    ri = ln.rotation_info
    r = etree.SubElement(e, _hp("rotationInfo"))
    r.set("angle", str(ri.angle)); r.set("centerX", str(ri.center_x))
    r.set("centerY", str(ri.center_y)); r.set("rotateimage", str(ri.rotate_image))
    rend = etree.SubElement(e, _hp("renderingInfo"))
    for tag, m in (("transMatrix", ln.rendering_info.trans),
                   ("scaMatrix", ln.rendering_info.sca),
                   ("rotMatrix", ln.rendering_info.rot)):
        me = etree.SubElement(rend, _hc(tag))
        for i in range(1, 7):
            me.set("e%d" % i, getattr(m, "e%d" % i))
    lsh = ln.line_shape
    lse = etree.SubElement(e, _hp("lineShape"))
    for k, v in (("color", lsh.color), ("width", str(lsh.width)),
                 ("style", lsh.style), ("endCap", lsh.end_cap),
                 ("headStyle", lsh.head_style), ("tailStyle", lsh.tail_style),
                 ("headfill", str(lsh.head_fill)), ("tailfill", str(lsh.tail_fill)),
                 ("headSz", lsh.head_sz), ("tailSz", lsh.tail_sz),
                 ("outlineStyle", lsh.outline_style), ("alpha", str(lsh.alpha))):
        lse.set(k, v)
    fb = etree.SubElement(e, _hc("fillBrush"))
    wb = etree.SubElement(fb, _hc("winBrush"))
    wb.set("faceColor", ln.win_brush.face_color)
    wb.set("hatchColor", ln.win_brush.hatch_color)
    wb.set("alpha", str(ln.win_brush.alpha))
    sh = etree.SubElement(e, _hp("shadow"))
    sh.set("type", ln.shadow.type); sh.set("color", ln.shadow.color)
    sh.set("offsetX", str(ln.shadow.offset_x)); sh.set("offsetY", str(ln.shadow.offset_y))
    sh.set("alpha", str(ln.shadow.alpha))
    sp = etree.SubElement(e, _hc("startPt"))
    sp.set("x", str(ln.start_pt.x)); sp.set("y", str(ln.start_pt.y))
    ep = etree.SubElement(e, _hc("endPt"))
    ep.set("x", str(ln.end_pt.x)); ep.set("y", str(ln.end_pt.y))
    sz = etree.SubElement(e, _hp("sz"))
    sz.set("width", str(ln.sz.width)); sz.set("widthRelTo", ln.sz.width_rel_to)
    sz.set("height", str(ln.sz.height)); sz.set("heightRelTo", ln.sz.height_rel_to)
    sz.set("protect", str(ln.sz.protect))
    po = ln.pos
    pe = etree.SubElement(e, _hp("pos"))
    for k, v in (("treatAsChar", str(po.treat_as_char)),
                 ("affectLSpacing", str(po.affect_lspacing)),
                 ("flowWithText", str(po.flow_with_text)),
                 ("allowOverlap", str(po.allow_overlap)),
                 ("holdAnchorAndSO", str(po.hold_anchor_and_so)),
                 ("vertRelTo", po.vert_rel_to), ("horzRelTo", po.horz_rel_to),
                 ("vertAlign", po.vert_align), ("horzAlign", po.horz_align),
                 ("vertOffset", str(po.vert_offset)),
                 ("horzOffset", str(po.horz_offset))):
        pe.set(k, v)
    om = etree.SubElement(e, _hp("outMargin"))
    for side in ("left", "right", "top", "bottom"):
        om.set(side, str(getattr(ln.out_margin, side)))
```

In `_write_run`, after the existing table branch, add:

```python
    if getattr(run, "drawing", None) is not None:
        _write_line(r, run.drawing)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_section_writer_line.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run writer regression subset**

Run: `.venv/bin/python -m pytest tests/test_section_writer.py tests/test_section_writer_tables.py tests/test_section_writer_secpr.py tests/test_section_writer_inline.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py tests/test_section_writer_line.py
git commit -m "feat: writer emits hp:line drawing subtree"
```

---

### Task 6: End-to-end — sample 4 lines + sample 3 no-change

**Files:**
- Test: `tests/test_convert_line.py`

**Interfaces:**
- Consumes: the whole pipeline via `hwp2hwpx.convert.convert`.

- [ ] **Step 1: Write the test**

```python
# tests/test_convert_line.py
import zipfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S4 = "samples/4.*.hwp"
S4_REF = "samples/4.*.hwpx"
S3 = "samples/3.*.hwp"
S3_REF = "samples/3.*.hwpx"


def _section0(hwp, tmp_path, name):
    out = tmp_path / name
    convert(hwp, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def test_sample4_emits_six_lines(tmp_path):
    sec = _section0(S4, tmp_path, "s4.hwpx")
    assert sec.count("<hp:line ") == 6


def test_sample4_line_container_tags_shrink_in_miss_list(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    # line + its container tags must no longer be fully missing (>=6 each before)
    for tag in ("line", "lineShape", "startPt", "endPt"):
        assert missing.get(tag, 0) == 0, "%s still missing x%d" % (tag, missing.get(tag, 0))
    # common-container tags shared with the 3 pictures drop from x9 to <=3
    for tag in ("curSz", "flip", "rotationInfo", "renderingInfo"):
        assert missing.get(tag, 0) <= 3


def test_sample4_section0_match_rose(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    # baseline before this milestone was 0.9677; lines lift it further
    assert score_part(ours, theirs)["match"] > 0.975


def test_sample3_unchanged_no_line(tmp_path):
    sec = _section0(S3, tmp_path, "s3.hwpx")
    assert sec.count("<hp:line ") == 0
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_convert_line.py -v`
Expected: PASS (4 tests). If `test_sample4_emits_six_lines` reports a count other than 6, diagnose whether a line's `ShapeComponent` uses a `chid0` other than `$lin` (adjust the reader guard) — do NOT relax the count. If `test_sample3_unchanged_no_line` fails, the paragraph-walk change is emitting spurious runs — fix the reader branch (it must only append when `_parse_drawing` returns non-None).

- [ ] **Step 3: Confirm sample 3 emits zero drawing-related tags**

Do NOT switch git branches. The sample-3 no-change property is guaranteed by the reader appending a drawing run only when `_parse_drawing` returns non-None (sample 3 has no `GShapeObjectControl`). The `test_sample3_unchanged_no_line` test already asserts `hp:line`==0; extend confidence with an in-process check that none of the drawing subtree tags leak into sample 3:

Run:
```bash
.venv/bin/python -c "
import zipfile, tempfile, os
from hwp2hwpx.convert import convert
out = tempfile.mktemp(suffix='.hwpx')
convert('samples/3.*.hwp', out)
s = zipfile.ZipFile(out).read('Contents/section0.xml').decode()
os.unlink(out)
tags = ['<hp:line ', '<hp:orgSz', '<hp:curSz', '<hp:rotationInfo', '<hp:renderingInfo', '<hc:startPt', '<hp:lineShape']
hits = {t: s.count(t) for t in tags if s.count(t)}
print('LEAK:', hits) if hits else print('CLEAN — no drawing tags in sample 3')
"
```
Expected: `CLEAN — no drawing tags in sample 3`.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all tests). Confirm `tests/test_convert_inline.py` run/`<hp:t>` count assertions still hold (drawing runs add ≤6 runs on sample 4, well within `runs < 1000`).

- [ ] **Step 5: Commit**

```bash
git add tests/test_convert_line.py
git commit -m "test: end-to-end hp:line on sample 4 + sample 3 no-change guard"
```

---

## Self-Review

**Spec coverage:** Reader parses `GShapeObjectControl`/`ShapeComponent`/`ShapeLine` (Task 3); model both sides (Tasks 1–2); mapper with matrix + enum mapping (Task 4); writer emits the full `hp:line` subtree with `hp:`/`hc:` namespaces in the verified child order (Task 5); count-based gate + sample-3 no-change guard + non-line skip (Tasks 3, 6). Correctness gate is count-based per spec (not exact-subtree).

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every run step has expected output.

**Type consistency:** OWPML field names in Task 2 (`org_sz`, `cur_sz`, `rotation_info`, `rendering_info`, `line_shape`, `win_brush`, `start_pt`, `end_pt`, `out_margin`, `text_wrap`, `width_rel_to`, `horz_offset`, etc.) are used identically by mapper (Task 4) and writer (Task 5). HWP field names in Task 1 (`instance_id`, `z_order`, `initial_width`, `trans_matrix`, `scaler_matrix`, `p0`/`p1`, `component`, `line`) are used identically by reader (Task 3) and mapper (Task 4). `Matrix` fields are strings (`e1`.."e6"); `_matrix` maps `a/b/c/d/e/f → e1/e2/e3/e4/e5/e6` = `a/c/e/b/d/f`. Reader branch appends a drawing run only when `_parse_drawing` is non-None (guards the sample-3 no-change property).
