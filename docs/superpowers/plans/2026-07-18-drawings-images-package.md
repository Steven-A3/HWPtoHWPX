# Drawings, Images & Package Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover the silently-dropped embedded JPEG, render shape text-boxes, and emit the missing package-metadata parts, closing the fidelity/correctness gaps the 2013 sample exposed.

**Architecture:** Extend the existing 4-layer pipeline (Reader → Mapper → Writer → Fidelity). Generalize the flat pic/line drawing model into a recursive shape tree (container/rect), renumber embedded images by document order, and add a summary-info source for package metadata. All changes are additive.

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc`). Tests: pytest via `.venv/bin/python -m pytest`.

## Global Constraints

- **Python 3.9 floor:** NO `X | None` unions; use `field(default_factory=...)` for mutable dataclass defaults.
- **Run tests with `.venv/bin/python -m pytest`** — plain `python` lacks `hwp5proc` and yields ~13 spurious failures.
- **Fidelity scoring is element-count per tag:** attribute *values* do not affect score. Guard values with exact-serialization unit tests, following the bullets/inline-ctrls pattern.
- **No regression on samples 3 & 4:** sample 4's bindata map is the identity (1→1,2→2,3→3) and its output must stay byte-identical. Sample 3's `tests/test_convert_markpen.py::test_sample3_section_unchanged` is a sha256+len byte-identity guard on `Contents/section0.xml` — re-baseline ONLY if a task provably changes s3 section0 (the package tasks 4/5 do not touch section0).
- **Non-goals (do NOT attempt):** `Preview/PrvImage.png` (rendered thumbnail), exact `ModifiedDate`/`lastsaveby` values (Hancom rewrites at export — emit the elements with best-effort source values), `image/jpeg` spelling (match Hancom's non-standard `image/jpg`).
- **Reuse, don't duplicate:** paragraph content inside a shape reuses `parse_paragraph` (reader), `map_paragraph` (mapper), and `_write_paragraph` (writer). Shape geometry reuses the `_common_container` mapper helper where applicable.

---

## Task 1: Rectangle shapes (`$rec`) with text

Adds the `$rec` drawing kind: a rectangle carrying geometry, line/shadow, and nested paragraph text (`drawText`→`subList`→`hp:p`). Exercised by the 3 top-level `$rec` GShapeObjectControls in the 2013 sample.

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (add `HwpRect`, `HwpDrawText`; extend `HwpShapeComponent` with a second matrix pair; extend `HwpDrawing` with `rect`)
- Modify: `hwp2hwpx/hwpmodel/reader.py` (`_parse_shape_component` second matrix pair; `_parse_rect`; `_parse_drawing` `$rec` branch)
- Modify: `hwp2hwpx/owpml/model.py` (add `Rect`, `DrawText`, `SubList`)
- Modify: `hwp2hwpx/mapper/drawing.py` (`_map_rect`, dispatch in `map_drawing`)
- Modify: `hwp2hwpx/owpml/section_writer.py` (`_write_rect`, `_write_draw_text`; dispatch in `_write_run`)
- Test: `tests/test_convert_rect.py` (new)

**Interfaces:**
- Consumes: existing `_parse_shape_component`, `parse_paragraph`, `map_paragraph`, `_write_paragraph`, `_common_container`, `_matrix`, `RenderingInfo`, `Matrix`.
- Produces:
  - `HwpRect(line_color:str, line_width:int, draw_text:HwpDrawText)` and `HwpDrawText(last_width:int, vert_align:str, paragraphs:list)`.
  - `HwpShapeComponent.scaler_matrix2:list`, `.rotator_matrix2:list` (second pair; default identity; only rects populate them).
  - OWPML `Rect(**shape_object_attrs, ratio:int=0, line_shape:LineShape, shadow:Shadow, sca2:Matrix, rot2:Matrix, draw_text:DrawText)`, `DrawText(last_width:int, sub_list:SubList)`, `SubList(vert_align:str, paras:list)`.
  - Writer emits `<hp:rect>` (see exact structure below).

### Source → target facts (ground truth)

Source `$rec` `ShapeComponent` attrs: `chid="$rec"`, `width`, `height`, `initial-width`, `initial-height`, `angle`, `flip`, `x-in-group`, `y-in-group`, `scalerotations-count="2"`. Children: `Coord[@attribute-name='rotation_center']`, `Matrix[@attribute-name='translation']`, `Array` of 2 `ScaleRotationMatrix` (each with `Matrix[@attribute-name='scaler']` + `Matrix[@attribute-name='rotator']`), `BorderLine[@attribute-name='border']` (`color`, `width`), `TextboxParagraphList` (`maxwidth`, `valign`, holds `Paragraph`s), `ShapeRectangle`.

Target (attribute order matters for byte-exact tests):
```
<hp:rect id="{instid}" zOrder="{z}" numberingType="NONE" textWrap="{wrap}"
    textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" href="" groupLevel="1"
    instid="{instid}" ratio="0">
  <hp:offset x="{x}" y="{y}"/>
  <hp:orgSz width="{iw}" height="{ih}"/>
  <hp:curSz width="{w}" height="{h}"/>
  <hp:flip horizontal="{fh}" vertical="{fv}"/>
  <hp:rotationInfo angle="{a}" centerX="{cx}" centerY="{cy}" rotateimage="0"/>
  <hp:renderingInfo>
    <hc:transMatrix .../><hc:scaMatrix .../><hc:rotMatrix .../>
    <hc:scaMatrix .../><hc:rotMatrix .../>          <!-- second pair -->
  </hp:renderingInfo>
  <hp:lineShape color="{lc}" width="{lw}" style="NONE" endCap="FLAT"
      headStyle="NORMAL" tailStyle="NORMAL" headfill="1" tailfill="1"
      headSz="MEDIUM_MEDIUM" tailSz="MEDIUM_MEDIUM" outlineStyle="NORMAL" alpha="0"/>
  <hp:shadow type="NONE" color="#000000" offsetX="0" offsetY="0" alpha="0"/>
  <hp:drawText lastWidth="{maxwidth}" name="" editable="0">
    <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK"
        vertAlign="{VALIGN}" linkListIDRef="0" linkListNextIDRef="0"
        textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
      <hp:p ...>          <!-- reuse _write_paragraph -->
```
`vertAlign` maps `TextboxParagraphList/@valign`: `middle`→`CENTER`, `top`→`TOP`, `bottom`→`BOTTOM`. `groupLevel` is 1 for a top-level rect (Hancom emits 1 even at top level for text-box rects). `ratio="0"` is a constant here.

- [ ] **Step 1: Write failing model test**

Add to `tests/test_convert_rect.py`:
```python
from hwp2hwpx.hwpmodel.model import HwpRect, HwpDrawText, HwpShapeComponent, HwpDrawing


def test_hwp_rect_model_defaults():
    r = HwpRect()
    assert r.line_color == "#000000"
    assert r.line_width == 0
    assert r.draw_text is None


def test_shape_component_has_second_matrix_pair():
    c = HwpShapeComponent()
    assert c.scaler_matrix2 == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert c.rotator_matrix2 == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
```

- [ ] **Step 2: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_convert_rect.py -q`
Expected: FAIL (ImportError: cannot import name 'HwpRect').

- [ ] **Step 3: Add HWP models**

In `hwp2hwpx/hwpmodel/model.py`, extend `HwpShapeComponent` (add after `rotator_matrix`):
```python
    scaler_matrix2: list = field(default_factory=lambda: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    rotator_matrix2: list = field(default_factory=lambda: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
```
Add new dataclasses (near `HwpDrawing`):
```python
@dataclass
class HwpDrawText:
    last_width: int = 0
    vert_align: str = "CENTER"
    paragraphs: list = field(default_factory=list)


@dataclass
class HwpRect:
    line_color: str = "#000000"
    line_width: int = 0
    draw_text: "HwpDrawText" = None
```
Extend `HwpDrawing` (add field after `picture`):
```python
    rect: "HwpRect" = None
```

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_convert_rect.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Write failing reader test**

Add to `tests/test_convert_rect.py`:
```python
import glob
from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing, hwp5_xml


def _first_rec_gso(root):
    for el in root.iter():
        if isinstance(el.tag, str) and etree.QName(el).localname == "GShapeObjectControl":
            comp = el.find("ShapeComponent")
            if comp is not None and (comp.get("chid0") == "$rec" or comp.get("chid") == "$rec"):
                return el
    return None


def test_reader_parses_toplevel_rect_with_text():
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    gso = _first_rec_gso(root)
    d = _parse_drawing(gso)
    assert d is not None
    assert d.kind == "rect"
    assert d.rect is not None
    assert d.rect.line_color == "#000000"
    # second matrix pair captured
    assert d.component.scaler_matrix2 != [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    # nested paragraph text reused parse_paragraph
    assert len(d.rect.draw_text.paragraphs) >= 1
    assert d.rect.draw_text.last_width > 0
```

- [ ] **Step 6: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_convert_rect.py::test_reader_parses_toplevel_rect_with_text -q`
Expected: FAIL (`d.kind` is not "rect"; `_parse_drawing` returns None for `$rec`).

- [ ] **Step 7: Implement reader**

In `hwp2hwpx/hwpmodel/reader.py`:

Import the new models — add `HwpRect, HwpDrawText` to the `from .model import (...)` block.

Extend `_parse_shape_component` to capture the second scaler/rotator pair. Replace the `scaler`/`rotator` lookups so both pairs are read:
```python
def _parse_shape_component(comp_el):
    center = comp_el.find("Coord[@attribute-name='rotation_center']")
    trans = comp_el.find("Matrix[@attribute-name='translation']")
    srms = comp_el.findall(".//ScaleRotationMatrix")
    def _pair(idx):
        if idx < len(srms):
            return (_matrix_values(srms[idx].find("Matrix[@attribute-name='scaler']")),
                    _matrix_values(srms[idx].find("Matrix[@attribute-name='rotator']")))
        return ([1.0, 0.0, 0.0, 1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    # fall back to the pre-existing flat lookup when there is no ScaleRotationMatrix
    if srms:
        (sca1, rot1) = _pair(0)
        (sca2, rot2) = _pair(1)
    else:
        sca1 = _matrix_values(comp_el.find(".//Matrix[@attribute-name='scaler']"))
        rot1 = _matrix_values(comp_el.find(".//Matrix[@attribute-name='rotator']"))
        sca2, rot2 = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
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
        scaler_matrix=sca1, rotator_matrix=rot1,
        scaler_matrix2=sca2, rotator_matrix2=rot2,
    )
```
Note: `_matrix_values(None)` must return identity — confirm `_matrix_values` handles a `None` arg; if it does not, guard with `if el is None: return [1.0,0.0,0.0,1.0,0.0,0.0]` at its top.

Add `_VALIGN_BOX = {"top": "TOP", "middle": "CENTER", "bottom": "BOTTOM"}` near the module constants, and a rect parser:
```python
def _parse_rect(comp_el):
    bl = comp_el.find("BorderLine[@attribute-name='border']")
    tpl = comp_el.find("TextboxParagraphList")
    paras = []
    if tpl is not None:
        for p_el in tpl.findall("Paragraph"):
            paras.append(parse_paragraph(p_el))
    dt = HwpDrawText(
        last_width=_int(tpl.get("maxwidth")) if tpl is not None else 0,
        vert_align=_VALIGN_BOX.get((tpl.get("valign") if tpl is not None else "middle"), "CENTER"),
        paragraphs=paras,
    )
    return HwpRect(
        line_color=(bl.get("color") if bl is not None else None) or "#000000",
        line_width=_int(bl.get("width")) if bl is not None else 0,
        draw_text=dt,
    )
```
In `_parse_drawing`, extend the accepted set and add the `$rec` branch:
```python
    if chid0 not in ("$lin", "$pic", "$rec"):
        return None
    ...
    if chid0 == "$lin":
        return HwpDrawing(kind="line", line=_parse_line_shape(comp), **common)
    if chid0 == "$rec":
        return HwpDrawing(kind="rect", rect=_parse_rect(comp), **common)
    return HwpDrawing(kind="pic", picture=_parse_picture(comp), **common)
```

- [ ] **Step 8: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_convert_rect.py -q`
Expected: PASS (3 tests).

- [ ] **Step 9: Write failing OWPML-model + mapper test**

Add to `tests/test_convert_rect.py`:
```python
from hwp2hwpx.owpml.model import Rect, DrawText, SubList
from hwp2hwpx.mapper.drawing import map_drawing


def test_mapper_maps_rect_to_owpml_rect():
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    d = _parse_drawing(_first_rec_gso(root))
    m = map_drawing(d)
    assert isinstance(m, Rect)
    assert m.ratio == 0
    assert m.line_shape.color == "#000000"
    assert isinstance(m.draw_text, DrawText)
    assert isinstance(m.draw_text.sub_list, SubList)
    assert m.draw_text.sub_list.vert_align == "CENTER"
    assert len(m.draw_text.sub_list.paras) >= 1   # reused map_paragraph
    # second matrix pair carried through
    assert m.sca2 is not None and m.rot2 is not None
```

- [ ] **Step 10: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_convert_rect.py::test_mapper_maps_rect_to_owpml_rect -q`
Expected: FAIL (ImportError: Rect).

- [ ] **Step 11: Add OWPML models + mapper**

In `hwp2hwpx/owpml/model.py` add (near `Pic`/`Line`):
```python
@dataclass
class SubList:
    vert_align: str = "CENTER"
    paras: list = field(default_factory=list)


@dataclass
class DrawText:
    last_width: int = 0
    sub_list: "SubList" = None


@dataclass
class Rect:
    id: int = 0
    z_order: int = 0
    text_wrap: str = "TOP_AND_BOTTOM"
    text_flow: str = "BOTH_SIDES"
    group_level: int = 1
    instid: int = 0
    ratio: int = 0
    offset: "Offset" = None
    org_sz: "OrgSz" = None
    cur_sz: "CurSz" = None
    flip: "Flip" = None
    rotation_info: "RotationInfo" = None
    rendering_info: "RenderingInfo" = None
    sca2: "Matrix" = None
    rot2: "Matrix" = None
    line_shape: "LineShape" = None
    shadow: "Shadow" = None
    draw_text: "DrawText" = None
```
In `hwp2hwpx/mapper/drawing.py`, import `Rect, DrawText, SubList` and add:
```python
def _map_rect(hd):
    comp, rc = hd.component, hd.rect
    dt = rc.draw_text
    sub = SubList(vert_align=dt.vert_align,
                  paras=[map_paragraph(p, 0) for p in dt.paragraphs])
    common = _common_container(hd, comp, 0)
    return Rect(
        id=common["id"], z_order=common["z_order"], text_wrap=common["text_wrap"],
        instid=hd.instance_id, group_level=1, ratio=0,
        offset=common["offset"], org_sz=common["org_sz"], cur_sz=common["cur_sz"],
        flip=common["flip"], rotation_info=common["rotation_info"],
        rendering_info=common["rendering_info"],
        sca2=_matrix(comp.scaler_matrix2), rot2=_matrix(comp.rotator_matrix2),
        line_shape=LineShape(color=rc.line_color, width=rc.line_width,
                             style="NONE", end_cap="FLAT"),
        shadow=Shadow(),
        draw_text=DrawText(last_width=dt.last_width, sub_list=sub),
    )
```
Add `map_paragraph` import: `from .body import map_paragraph`. **Watch for a circular import** — `body.py` imports from `drawing.py` (`map_drawing`). If importing `map_paragraph` at module top raises, do the import lazily inside `_map_rect` (`from .body import map_paragraph`). Verify which is needed when the test runs.

Extend `map_drawing`:
```python
    if hd.kind == "rect" and hd.rect is not None:
        return _map_rect(hd)
```

- [ ] **Step 12: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_convert_rect.py -q`
Expected: PASS (4 tests).

- [ ] **Step 13: Write failing writer test**

Add to `tests/test_convert_rect.py`:
```python
from hwp2hwpx.constants import NS
from hwp2hwpx.owpml.section_writer import _write_run
from hwp2hwpx.owpml.model import Run


def _run_xml(run):
    p_el = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"], "hc": NS["hc"]})
    _write_run(p_el, run, state=None)
    return etree.tostring(p_el, encoding="unicode")


def test_writer_emits_rect_with_drawtext(tmp_path):
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    rect = map_drawing(_parse_drawing(_first_rec_gso(root)))
    xml = _run_xml(Run(char_pr_id=0, drawing=rect))
    assert "<hp:rect " in xml and 'ratio="0"' in xml
    assert xml.count("<hc:scaMatrix") == 2   # both matrix pairs
    assert "<hp:drawText " in xml and "<hp:subList " in xml
    assert 'vertAlign="CENTER"' in xml
    assert "<hp:p " in xml   # nested paragraph rendered
```

- [ ] **Step 14: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_convert_rect.py::test_writer_emits_rect_with_drawtext -q`
Expected: FAIL (no `<hp:rect>` emitted).

- [ ] **Step 15: Implement writer**

In `hwp2hwpx/owpml/section_writer.py`, import `Rect` (and any helpers). In `_write_run`, extend the drawing dispatch:
```python
    if getattr(run, "drawing", None) is not None:
        if isinstance(run.drawing, Pic):
            _write_pic(r, run.drawing)
        elif isinstance(run.drawing, Line):
            _write_line(r, run.drawing)
        elif isinstance(run.drawing, Rect):
            _write_rect(r, run.drawing, state)
```
Add `_write_rect` and `_write_draw_text`. Follow `_write_pic`'s structure for the shared prologue (offset/orgSz/curSz/flip/rotationInfo/renderingInfo), then emit the rect-specific tail. The renderingInfo must emit BOTH matrix pairs:
```python
def _write_rect(run_el, rc, state):
    e = etree.SubElement(run_el, _hp("rect"))
    for k, v in (("id", str(rc.id)), ("zOrder", str(rc.z_order)),
                 ("numberingType", "NONE"), ("textWrap", rc.text_wrap),
                 ("textFlow", rc.text_flow), ("lock", "0"),
                 ("dropcapstyle", "None"), ("href", ""),
                 ("groupLevel", str(rc.group_level)), ("instid", str(rc.instid)),
                 ("ratio", str(rc.ratio))):
        e.set(k, v)
    _write_shape_geom(e, rc)          # offset/orgSz/curSz/flip/rotationInfo
    rend = etree.SubElement(e, _hp("renderingInfo"))
    for tag, m in (("transMatrix", rc.rendering_info.trans),
                   ("scaMatrix", rc.rendering_info.sca),
                   ("rotMatrix", rc.rendering_info.rot),
                   ("scaMatrix", rc.sca2), ("rotMatrix", rc.rot2)):
        me = etree.SubElement(rend, _hc(tag))
        for i in range(1, 7):
            me.set("e%d" % i, getattr(m, "e%d" % i))
    ls = rc.line_shape
    lsh = etree.SubElement(e, _hp("lineShape"))
    for k, v in (("color", ls.color), ("width", str(ls.width)), ("style", ls.style),
                 ("endCap", "FLAT"), ("headStyle", "NORMAL"), ("tailStyle", "NORMAL"),
                 ("headfill", "1"), ("tailfill", "1"), ("headSz", "MEDIUM_MEDIUM"),
                 ("tailSz", "MEDIUM_MEDIUM"), ("outlineStyle", "NORMAL"), ("alpha", "0")):
        lsh.set(k, v)
    sh = etree.SubElement(e, _hp("shadow"))
    for k, v in (("type", "NONE"), ("color", "#000000"), ("offsetX", "0"),
                 ("offsetY", "0"), ("alpha", "0")):
        sh.set(k, v)
    _write_draw_text(e, rc.draw_text, state)


def _write_draw_text(rect_el, dt, state):
    if dt is None:
        return
    dte = etree.SubElement(rect_el, _hp("drawText"))
    dte.set("lastWidth", str(dt.last_width)); dte.set("name", ""); dte.set("editable", "0")
    sl = dt.sub_list
    sle = etree.SubElement(dte, _hp("subList"))
    for k, v in (("id", ""), ("textDirection", "HORIZONTAL"), ("lineWrap", "BREAK"),
                 ("vertAlign", sl.vert_align), ("linkListIDRef", "0"),
                 ("linkListNextIDRef", "0"), ("textWidth", "0"), ("textHeight", "0"),
                 ("hasTextRef", "0"), ("hasNumRef", "0")):
        sle.set(k, v)
    for para in sl.paras:
        _write_paragraph(sle, para, state)
```
Factor the shared prologue used by `_write_pic`/`_write_line`/`_write_rect` into `_write_shape_geom(el, obj)` emitting offset/orgSz/curSz/flip/rotationInfo from `obj.offset/org_sz/cur_sz/flip/rotation_info`, and call it from `_write_rect`. (Refactoring `_write_pic`/`_write_line` to also use it is optional and out of scope — keep this task's diff focused; only `_write_rect` must use it.)

- [ ] **Step 16: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_convert_rect.py -q`
Expected: PASS (5 tests).

- [ ] **Step 17: Regression + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (samples 3 & 4 unchanged — top-level rects only exist in the 2013 sample; the 2013 `$con` container is still skipped, so its nested rects/JPEG are not yet emitted).
```bash
git add hwp2hwpx/ tests/test_convert_rect.py
git commit -m "feat: map HWP rectangle shapes with text to OWPML rect/drawText"
```

---

## Task 2: Container shapes (`$con`) with recursive children

Adds the `$con` container/group drawing kind whose children are shapes (pic, rect, nested containers), emitted as `<hp:container>` with incrementing `groupLevel`. Recovers the JPEG pic nested inside the 2013 container.

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (`HwpDrawing.children`)
- Modify: `hwp2hwpx/hwpmodel/reader.py` (`_parse_drawing` `$con` branch, recursive)
- Modify: `hwp2hwpx/owpml/model.py` (add `Container`)
- Modify: `hwp2hwpx/mapper/drawing.py` (`_map_container`, recursive dispatch; propagate `group_level`)
- Modify: `hwp2hwpx/owpml/section_writer.py` (`_write_container`, recursive)
- Test: `tests/test_convert_container.py` (new)

**Interfaces:**
- Consumes: Task 1's `_parse_rect`/`_map_rect`/`_write_rect`, existing pic parse/map/write.
- Produces:
  - `HwpDrawing.children:list` (child `HwpDrawing`s; empty for leaf shapes).
  - OWPML `Container(**shape_object_attrs, children:list)`.
  - `map_drawing`/writer recurse; child `group_level = parent + 1`.

### Source → target facts

Source `$con` `ShapeComponent` (chid=`$con`) contains child `ShapeComponent`s (each a `$pic`/`$rec`/nested `$con`) as direct children, plus its own geometry. The container GShapeObjectControl wraps a single top `ShapeComponent chid0=$con`. Target `<hp:container ... groupLevel="0">` holds child `<hp:pic>`/`<hp:rect>` at `groupLevel="1"`, sharing the container's geometry prologue (offset/orgSz/curSz/flip/rotationInfo/renderingInfo with ONE matrix pair — container uses `scalerotations-count="1"`).

Child shapes inside a container are nested `ShapeComponent`s, not wrapped in their own `GShapeObjectControl`. `_parse_drawing` currently reads a `GShapeObjectControl`; add a helper that parses a bare child `ShapeComponent` (it has `chid`, geometry, and type-specific children) into an `HwpDrawing`, reusing `_parse_rect`/`_parse_picture`/`_parse_line_shape`. The child's shape-object placement attrs (flow, x, y, width, height, etc.) are absent on nested components — default them (they are not emitted distinctly; geometry comes from the component).

- [ ] **Step 1: Write failing reader test**

`tests/test_convert_container.py`:
```python
import glob
from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing, hwp5_xml


def _con_gso(root):
    for el in root.iter():
        if isinstance(el.tag, str) and etree.QName(el).localname == "GShapeObjectControl":
            comp = el.find("ShapeComponent")
            if comp is not None and (comp.get("chid0") == "$con" or comp.get("chid") == "$con"):
                return el
    return None


def test_reader_parses_container_children():
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    d = _parse_drawing(_con_gso(root))
    assert d.kind == "container"
    kinds = sorted(c.kind for c in d.children)
    assert kinds == ["pic", "rect", "rect"]   # 1 pic + 2 rects
    pic = [c for c in d.children if c.kind == "pic"][0]
    assert pic.picture.bindata_id == 2   # the JPEG, previously dropped
```

- [ ] **Step 2: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_convert_container.py -q`
Expected: FAIL (`$con` → None today).

- [ ] **Step 3: Implement reader**

In `hwp2hwpx/hwpmodel/model.py`, add to `HwpDrawing`:
```python
    children: list = field(default_factory=list)
```
In `hwp2hwpx/hwpmodel/reader.py`, add a nested-component parser and the `$con` branch. Add `"$con"` to the accepted `chid0` set in `_parse_drawing`. Then:
```python
def _parse_child_component(comp_el):
    chid = (comp_el.get("chid0") or comp_el.get("chid") or "").strip()
    if chid not in ("$lin", "$pic", "$rec", "$con"):
        return None
    common = dict(component=_parse_shape_component(comp_el))
    if chid == "$lin":
        return HwpDrawing(kind="line", line=_parse_line_shape(comp_el), **common)
    if chid == "$rec":
        return HwpDrawing(kind="rect", rect=_parse_rect(comp_el), **common)
    if chid == "$pic":
        return HwpDrawing(kind="pic", picture=_parse_picture(comp_el), **common)
    return HwpDrawing(kind="container", children=_parse_container_children(comp_el), **common)


def _parse_container_children(con_comp_el):
    out = []
    for child in con_comp_el.findall("ShapeComponent"):
        d = _parse_child_component(child)
        if d is not None:
            out.append(d)
    return out
```
In `_parse_drawing`, add the `$con` branch (uses the outer `common` dict built from the GShapeObjectControl):
```python
    if chid0 == "$con":
        return HwpDrawing(kind="container",
                          children=_parse_container_children(comp), **common)
```
Note: `comp` in `_parse_drawing` is the top `ShapeComponent chid0=$con`; its direct `ShapeComponent` children are the group members. Confirm `findall("ShapeComponent")` returns only direct children (it does — `findall` is not recursive).

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_convert_container.py::test_reader_parses_container_children -q`
Expected: PASS.

- [ ] **Step 5: Write failing mapper test**

Add:
```python
from hwp2hwpx.owpml.model import Container, Pic, Rect
from hwp2hwpx.mapper.drawing import map_drawing


def test_mapper_maps_container_recursively():
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    m = map_drawing(_parse_drawing(_con_gso(root)))
    assert isinstance(m, Container)
    assert m.group_level == 0
    child_types = sorted(type(c).__name__ for c in m.children)
    assert child_types == ["Pic", "Rect", "Rect"]
    for c in m.children:
        assert c.group_level == 1
```

- [ ] **Step 6: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_convert_container.py::test_mapper_maps_container_recursively -q`
Expected: FAIL (ImportError: Container).

- [ ] **Step 7: Implement mapper**

In `hwp2hwpx/owpml/model.py` add:
```python
@dataclass
class Container:
    id: int = 0
    z_order: int = 0
    text_wrap: str = "TOP_AND_BOTTOM"
    text_flow: str = "BOTH_SIDES"
    group_level: int = 0
    instid: int = 0
    offset: "Offset" = None
    org_sz: "OrgSz" = None
    cur_sz: "CurSz" = None
    flip: "Flip" = None
    rotation_info: "RotationInfo" = None
    rendering_info: "RenderingInfo" = None
    children: list = field(default_factory=list)
```
In `hwp2hwpx/mapper/drawing.py`, import `Container` and add. A child comes from a nested component that lacks placement attrs, so map it via a component-only path. Add a helper that maps any `HwpDrawing` at a given group level:
```python
def _map_shape(hd, group_level):
    if hd.kind == "pic":
        m = _map_pic(hd)
    elif hd.kind == "rect":
        m = _map_rect(hd)
    elif hd.kind == "line":
        m = _map_line(hd)
    elif hd.kind == "container":
        m = _map_container(hd, group_level)
    else:
        return None
    if hasattr(m, "group_level"):
        m.group_level = group_level
    return m


def _map_container(hd, group_level=0):
    comp = hd.component
    common = _common_container(hd, comp, 0)
    children = [c for c in (_map_shape(ch, group_level + 1) for ch in hd.children)
                if c is not None]
    return Container(
        id=common["id"], z_order=common["z_order"], text_wrap=common["text_wrap"],
        instid=hd.instance_id, group_level=group_level,
        offset=common["offset"], org_sz=common["org_sz"], cur_sz=common["cur_sz"],
        flip=common["flip"], rotation_info=common["rotation_info"],
        rendering_info=common["rendering_info"], children=children,
    )
```
Note: `_map_pic`/`_map_line`/`_map_rect` use `_common_container`, which reads placement attrs (`hd.width`, `hd.inline`, etc.) that are defaulted-to-zero on nested children — acceptable, since Pic/Rect geometry that matters comes from the component and the sz/pos blocks are count-neutral. Ensure `Pic`/`Rect` carry a settable `group_level` (Pic already has `group_level`; Rect added in Task 1). Extend `map_drawing`:
```python
    if hd.kind == "container":
        return _map_container(hd, 0)
```

- [ ] **Step 8: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_convert_container.py -q`
Expected: PASS (2 tests).

- [ ] **Step 9: Write failing writer + end-to-end test**

Add:
```python
import tempfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def test_end_to_end_container_and_shapes_present():
    hwp = glob.glob("samples/2013*.hwp")[0]
    ref = glob.glob("samples/2013*.hwpx")[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    o = unzip_parts(out)["Contents/section0.xml"]
    t = unzip_parts(ref)["Contents/section0.xml"]
    miss = score_part(o, t)["missing"]
    assert miss.get("container", 0) == 0
    assert miss.get("rect", 0) == 0
    assert miss.get("pic", 0) == 0
    assert miss.get("drawText", 0) == 0
    xml = o.decode("utf-8")
    assert '<hp:container ' in xml and 'groupLevel="1"' in xml
```

- [ ] **Step 10: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_convert_container.py::test_end_to_end_container_and_shapes_present -q`
Expected: FAIL (no `<hp:container>`).

- [ ] **Step 11: Implement writer**

In `hwp2hwpx/owpml/section_writer.py`, import `Container` and dispatch it in `_write_run`:
```python
        elif isinstance(run.drawing, Container):
            _write_container(r, run.drawing, state)
```
Add:
```python
def _write_shape_child(parent_el, shape, state):
    if isinstance(shape, Pic):
        # re-parent: _write_pic appends to run_el; emit into parent_el instead
        _write_pic(parent_el, shape)
    elif isinstance(shape, Rect):
        _write_rect(parent_el, shape, state)
    elif isinstance(shape, Line):
        _write_line(parent_el, shape)
    elif isinstance(shape, Container):
        _write_container(parent_el, shape, state)


def _write_container(run_el, cont, state):
    e = etree.SubElement(run_el, _hp("container"))
    for k, v in (("id", str(cont.id)), ("zOrder", str(cont.z_order)),
                 ("numberingType", "PICTURE"), ("textWrap", cont.text_wrap),
                 ("textFlow", cont.text_flow), ("lock", "0"),
                 ("dropcapstyle", "None"), ("href", ""),
                 ("groupLevel", str(cont.group_level)), ("instid", str(cont.instid))):
        e.set(k, v)
    _write_shape_geom(e, cont)
    rend = etree.SubElement(e, _hp("renderingInfo"))
    for tag, m in (("transMatrix", cont.rendering_info.trans),
                   ("scaMatrix", cont.rendering_info.sca),
                   ("rotMatrix", cont.rendering_info.rot)):
        me = etree.SubElement(rend, _hc(tag))
        for i in range(1, 7):
            me.set("e%d" % i, getattr(m, "e%d" % i))
    for child in cont.children:
        _write_shape_child(e, child, state)
```
`_write_pic` currently takes `(run_el, p)` and appends `<hp:pic>` to `run_el`; called with the container element as `parent_el` it nests correctly. Confirm `_write_pic` uses only `SubElement(run_el, ...)` (it does).

- [ ] **Step 12: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_convert_container.py -q`
Expected: PASS (3 tests).

- [ ] **Step 13: Regression + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass; samples 3 & 4 unchanged (no `$con` in them).
```bash
git add hwp2hwpx/ tests/test_convert_container.py
git commit -m "feat: map HWP container/group shapes recursively to OWPML container"
```

---

## Task 3: Bindata sequential renumbering

Renumber embedded images `image1..N` by document order of first reference (preserving extension), so the recovered JPEG and the other two images match Hancom's naming across BinData filenames, `content.hpf` items, and section `binaryItemIDRef`. Sample 4's map is the identity and its output must stay byte-identical.

**Files:**
- Modify: `hwp2hwpx/hwpmodel/bindata.py` (`extract_bin_items` assigns sequential indices; expose the bindata-id→index map)
- Modify: `hwp2hwpx/mapper/drawing.py` (`_map_pic` uses the sequential index for `bin_item_id`)
- Modify: `hwp2hwpx/convert.py` (thread the map from extraction into mapping)
- Test: `tests/test_bindata_renumber.py` (new)

**Interfaces:**
- Consumes: `_collect_pic_bindata_ids` (already walks drawings in document order; now also reaches container children via Task 2 — verify it recurses into `drawing.children`; if not, extend `_collect_pic_bindata_ids` to recurse).
- Produces: `extract_bin_items(hwp_path, hwp_doc)` returns `(items, id_to_index)` where `id_to_index[bindata_id] = sequential 1-based index`. `map_document` accepts an optional `bin_index` dict and passes it to `map_drawing`/`_map_pic`.

### Facts

`_collect_pic_bindata_ids` returns bindata-ids in first-reference document order. The sequential index is `enumerate(ids, 1)`. `_map_pic` line ~93 currently hardcodes `bin_item_id="image%d" % pic.bindata_id` — replace with a lookup into the index map (fallback to identity when absent, so unit tests without a map still work).

**Critical:** `_collect_pic_bindata_ids` must reach pics INSIDE containers (Task 2). Verify `run.drawing` walking recurses into `.children`; if it only checks top-level `d.picture`, extend it:
```python
def _iter_pics(drawing):
    if drawing is None:
        return
    if drawing.kind == "pic" and drawing.picture is not None:
        yield drawing.picture
    for ch in getattr(drawing, "children", ()):
        yield from _iter_pics(ch)
```
and use it in `_collect_pic_bindata_ids`.

- [ ] **Step 1: Write failing test**

`tests/test_bindata_renumber.py`:
```python
import glob, tempfile, zipfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _bindata(path):
    return sorted(n for n in zipfile.ZipFile(path).namelist() if n.startswith("BinData/"))


def test_2013_images_renumbered_document_order():
    hwp = glob.glob("samples/2013*.hwp")[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    assert _bindata(out) == ["BinData/image1.jpg", "BinData/image2.bmp",
                             "BinData/image3.png"]


def test_2013_binaryitemidref_matches_names():
    import re
    hwp = glob.glob("samples/2013*.hwp")[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    xml = unzip_parts(out)["Contents/section0.xml"].decode("utf-8")
    refs = set(re.findall(r'binaryItemIDRef="([^"]+)"', xml))
    assert refs == {"image1", "image2", "image3"}


def test_sample4_bindata_unchanged():
    hwp = glob.glob("samples/4.*.hwp")[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    assert _bindata(out) == ["BinData/image1.bmp", "BinData/image2.bmp",
                             "BinData/image3.bmp"]
```

- [ ] **Step 2: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_bindata_renumber.py -q`
Expected: FAIL (2013 names are `image1.png`/`image3.bmp` and the JPEG naming/order is wrong).

- [ ] **Step 3: Implement**

In `hwp2hwpx/hwpmodel/bindata.py`: add `_iter_pics` (above), use it in `_collect_pic_bindata_ids`. Change `extract_bin_items` to build `id_to_index = {bid: i for i, bid in enumerate(ids, 1)}`, name items `image{index}`, and return `(items, id_to_index)`.

In `hwp2hwpx/mapper/drawing.py`: give `_map_pic` access to the index. Simplest: add a module-level indirection the mapper reads. Preferred (explicit): thread a `bin_index` param. Add an optional param to `map_drawing(hd, bin_index=None)` and `_map_pic(hd, bin_index)`, and in `_map_pic`:
```python
    idx = (bin_index or {}).get(pic.bindata_id, pic.bindata_id)
    ... img=Img(bin_item_id="image%d" % idx, ...)
```
Propagate `bin_index` through `_map_shape`/`_map_container` recursion so nested pics resolve too.

In `hwp2hwpx/convert.py`: `extract_bin_items` now returns a tuple. Update:
```python
    items, bin_index = extract_bin_items(hwp_path, hwp_doc)
    owpml_doc = map_document(hwp_doc, title=..., bin_index=bin_index)
    owpml_doc.bin_items = items
```
Add `bin_index=None` to `map_document` and pass it down to every `map_drawing` call in `map_paragraph`.

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_bindata_renumber.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Regression + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass; sample 4 byte-identical (identity map).
```bash
git add hwp2hwpx/ tests/test_bindata_renumber.py
git commit -m "feat: renumber embedded images by document order"
```

---

## Task 4: content.hpf metadata from summary info

Emit the full Hancom namespace list on `<opf:package>` and the `<opf:meta>` blocks (creator, subject, description, lastsaveby, CreatedDate, ModifiedDate, date, keyword) sourced from `HwpSummaryInfo`. Closes `content.hpf` `meta`×8; `item`×1 is already closed by the recovered JPEG (Tasks 1–3).

**Files:**
- Modify: `hwp2hwpx/hwpmodel/bindata.py` OR new `hwp2hwpx/hwpmodel/summary.py` (`read_summary_info(hwp_path)` — parse `hwp5proc summaryinfo` text)
- Modify: `hwp2hwpx/hwpmodel/model.py` (`HwpSummaryInfo` dataclass; `HwpDocument.summary_info`)
- Modify: `hwp2hwpx/convert.py` (call `read_summary_info(hwp_path)`, attach to doc — mirrors `extract_bin_items`)
- Modify: `hwp2hwpx/owpml/model.py` (`Metadata` gains the meta fields) and mapper to populate
- Modify: `hwp2hwpx/owpml/package_parts.py` (`content_hpf` emits namespaces + meta)
- Test: `tests/test_content_hpf_meta.py` (new)

**Interfaces:**
- Consumes: `hwp5proc summaryinfo <path>` stdout (stable `Key: value` lines). The body-XML `HwpSummaryInfo` element is an opaque `PropertySetStream` — do NOT parse it; use the subcommand.
- Produces: `read_summary_info(hwp_path) -> HwpSummaryInfo(title, creator, subject, description, last_saved_by, created_date, modified_date, date, keyword)`; `content_hpf(metadata, section_count, bin_items)` emits the meta blocks from `metadata`. Since `read_document` receives only XML bytes, summary is read from the path in `convert.py` and attached to `doc.summary_info` (like `bin_items`).

### Facts (exact target)

Namespaces on `<opf:package>` (full set): `ha, hp, hp10, hs, hc, hh, hhs, hm, hpf, dc, opf, ooxmlchart, hwpunitchar, epub, config` (URIs captured in the spec's ground-truth section). Meta block format:
```xml
<opf:meta name="creator" content="text">최병철</opf:meta>
<opf:meta name="subject" content="text"/>
<opf:meta name="description" content="text"/>
<opf:meta name="lastsaveby" content="text">bkk</opf:meta>
<opf:meta name="CreatedDate" content="text">2008-05-01T06:01:38Z</opf:meta>
<opf:meta name="ModifiedDate" content="text">2026-07-17T13:11:47Z</opf:meta>
<opf:meta name="date" content="text">2009년 8월 23일 ...</opf:meta>
<opf:meta name="keyword" content="text"/>
```
Empty values → self-closing `<opf:meta name="x" content="text"/>`. `content="text"` is constant. Title/language come from summary (`<opf:title>`, `<opf:language>`). `ModifiedDate`/`lastsaveby` values are non-goals — populate from source best-effort (created/modified timestamps formatted `YYYY-MM-DDThh:mm:ssZ`); the ELEMENTS must exist for the count.

`hwp5proc summaryinfo <path>` output is `Key: value` lines; parse these keys and map to the meta names:

| summaryinfo line | HwpSummaryInfo field | opf:meta name |
|---|---|---|
| `Title:` | title | (→ `<opf:title>`) |
| `Author:` | creator | creator |
| `Subject:` | subject | subject |
| `Comments:` | description | description |
| `Last saved by:` | last_saved_by | lastsaveby |
| `Created at:` (`2008-05-01 06:01:38.812000`) | created_date | CreatedDate |
| `Last saved at:` | modified_date | ModifiedDate |
| `Date:` | date | date |
| `Keywords:` | keyword | keyword |

Timestamp reformat: `YYYY-MM-DD hh:mm:ss[.ffffff]` → `YYYY-MM-DDThh:mm:ssZ` (drop fractional seconds, insert `T`, append `Z`). Split each line on the FIRST `": "` only (values like `Date:` contain colons). The 8 `<opf:meta>` names to emit, in order: creator, subject, description, lastsaveby, CreatedDate, ModifiedDate, date, keyword.

- [ ] **Step 1: Write failing reader test**

`tests/test_content_hpf_meta.py`:
```python
import glob


def test_summary_info_parsed():
    from hwp2hwpx.hwpmodel.summary import read_summary_info
    si = read_summary_info(glob.glob("samples/2013*.hwp")[0])
    assert si.creator == "최병철"
    assert si.title == "ETRI 미래가치 제고 방안"
    assert si.created_date == "2008-05-01T06:01:38Z"
```
*(If you place `read_summary_info` in `bindata.py` instead of a new `summary.py`, import it from there.)*

- [ ] **Step 2: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_content_hpf_meta.py -q`
Expected: FAIL (no `hwp2hwpx.hwpmodel.summary` module).

- [ ] **Step 3: Implement reader + model**

Add `HwpSummaryInfo` to `hwp2hwpx/hwpmodel/model.py` (str fields `title, creator, subject, description, last_saved_by, created_date, modified_date, date, keyword`, all defaulting `""`). Add `summary_info: "HwpSummaryInfo" = None` to `HwpDocument`.

Add `read_summary_info(hwp_path)` (in a new `hwp2hwpx/hwpmodel/summary.py`, or beside `extract_bin_items` in `bindata.py`):
```python
import subprocess
from .reader import _hwp5proc
from .model import HwpSummaryInfo

_KEYS = {"Title": "title", "Author": "creator", "Subject": "subject",
         "Comments": "description", "Last saved by": "last_saved_by",
         "Created at": "created_date", "Last saved at": "modified_date",
         "Date": "date", "Keywords": "keyword"}
_TS = ("created_date", "modified_date")


def _fmt_ts(v):
    v = v.split(".", 1)[0].strip()          # drop fractional seconds
    return v.replace(" ", "T") + "Z" if v else ""


def read_summary_info(hwp_path):
    out = subprocess.run([_hwp5proc(), "summaryinfo", hwp_path],
                         capture_output=True).stdout.decode("utf-8", "replace")
    fields = {}
    for line in out.splitlines():
        if ": " not in line:
            continue
        key, val = line.split(": ", 1)
        attr = _KEYS.get(key.strip())
        if attr is None:
            continue
        val = val.strip()
        fields[attr] = _fmt_ts(val) if attr in _TS else val
    return HwpSummaryInfo(**fields)
```
In `hwp2hwpx/convert.py`, after `read_document`, attach: `hwp_doc.summary_info = read_summary_info(hwp_path)`.

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_content_hpf_meta.py::test_summary_info_parsed -q`
Expected: PASS.

- [ ] **Step 5: Write failing writer test**

Add:
```python
import tempfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from hwp2hwpx.fidelity.diff import score_part


def test_content_hpf_meta_blocks_present():
    hwp = glob.glob("samples/2013*.hwp")[0]
    ref = glob.glob("samples/2013*.hwpx")[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    o = unzip_parts(out)["Contents/content.hpf"]
    t = unzip_parts(ref)["Contents/content.hpf"]
    assert score_part(o, t)["missing"].get("meta", 0) == 0
    xml = o.decode("utf-8")
    assert '<opf:meta name="creator" content="text">최병철</opf:meta>' in xml
    assert '<opf:meta name="keyword" content="text"/>' in xml
```

- [ ] **Step 6: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_content_hpf_meta.py::test_content_hpf_meta_blocks_present -q`
Expected: FAIL (no meta blocks).

- [ ] **Step 7: Implement writer + mapper**

Extend `Metadata` in `hwp2hwpx/owpml/model.py` with the meta fields; populate it in the mapper (`map_document`/`map_metadata`) from `hwp_doc.summary_info`. In `hwp2hwpx/owpml/package_parts.py`, expand the `<opf:package>` namespace declarations to the full set and emit the 8 `<opf:meta>` blocks from `metadata` (self-close empties, text-fill non-empties). Keep `<opf:title>`/`<opf:language>` sourced from `metadata`.

- [ ] **Step 8: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_content_hpf_meta.py -q`
Expected: PASS.

- [ ] **Step 9: Regression + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. Samples 3 & 4 `content.hpf` gain meta blocks — if any existing test asserts s3/s4 `content.hpf` bytes, re-baseline it with the delta noted in the commit. s3/s4 `section0.xml` unaffected.
```bash
git add hwp2hwpx/ tests/test_content_hpf_meta.py
git commit -m "feat: emit content.hpf metadata from HWP summary info"
```

---

## Task 5: container.rdf + container.xml rootfile

Emit the missing `META-INF/container.rdf` part (all samples) and add its `<ocf:rootfile>` entry to `container.xml`. Closes `container.xml` `rootfile`×1 and the entire `container.rdf` part.

**Files:**
- Modify: `hwp2hwpx/owpml/package_parts.py` (`container_rdf(section_count)`; add rootfile to `container_xml`)
- Modify: `hwp2hwpx/owpml/writer.py` (write the `META-INF/container.rdf` part)
- Test: `tests/test_container_rdf.py` (new)

**Interfaces:**
- Consumes: section count (from `doc.sections`).
- Produces: `container_rdf(section_count) -> bytes`; `container_xml` includes the rdf rootfile.

### Facts (exact target)

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about=""><ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" rdf:resource="Contents/header.xml"/></rdf:Description><rdf:Description rdf:about="Contents/header.xml"><rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#HeaderFile"/></rdf:Description><rdf:Description rdf:about=""><ns0:hasPart xmlns:ns0="http://www.hancom.co.kr/hwpml/2016/meta/pkg#" rdf:resource="Contents/section0.xml"/></rdf:Description><rdf:Description rdf:about="Contents/section0.xml"><rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#SectionFile"/></rdf:Description><rdf:Description rdf:about=""><rdf:type rdf:resource="http://www.hancom.co.kr/hwpml/2016/meta/pkg#Document"/></rdf:Description></rdf:RDF>
```
Structure: one header `hasPart`+`HeaderFile`, then per-section (`section{i}.xml`) a `hasPart`+`SectionFile`, then a final `Document` type. `container.xml` rootfile to add (after PrvText):
```xml
<ocf:rootfile full-path="META-INF/container.rdf" media-type="application/rdf+xml"/>
```

- [ ] **Step 1: Write failing test**

`tests/test_container_rdf.py`:
```python
import glob, tempfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _out(n):
    hwp = glob.glob("samples/%s*.hwp" % n)[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    return unzip_parts(out)


def test_container_rdf_present_and_matches():
    o = _out("2013")
    assert "META-INF/container.rdf" in o
    rdf = o["META-INF/container.rdf"].decode("utf-8")
    assert "#HeaderFile" in rdf and "#SectionFile" in rdf and "#Document" in rdf
    assert rdf.count("#SectionFile") == 1


def test_container_xml_has_rdf_rootfile():
    o = _out("2013")
    cx = o["META-INF/container.xml"].decode("utf-8")
    assert 'full-path="META-INF/container.rdf" media-type="application/rdf+xml"' in cx


def test_container_rdf_all_samples():
    for n in ("3.", "4.", "2013"):
        assert "META-INF/container.rdf" in _out(n)
```

- [ ] **Step 2: Run — expect failure**

Run: `.venv/bin/python -m pytest tests/test_container_rdf.py -q`
Expected: FAIL (part absent).

- [ ] **Step 3: Implement**

In `hwp2hwpx/owpml/package_parts.py`, add `container_rdf(section_count)` returning the exact bytes (build the per-section descriptions in a loop over `range(section_count)` → `Contents/section{i}.xml`). Add the rdf `<ocf:rootfile>` line to `container_xml`. In `hwp2hwpx/owpml/writer.py`, add `parts["META-INF/container.rdf"] = container_rdf(len(doc.sections))`.

- [ ] **Step 4: Run — expect pass**

Run: `.venv/bin/python -m pytest tests/test_container_rdf.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Regression + full end-to-end score + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. Then verify the aggregate improvement:
```bash
.venv/bin/python -c "
import glob, tempfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
for n in ['3.','4.','2013']:
    hwp=glob.glob('samples/%s*.hwp'%n)[0]; ref=glob.glob('samples/%s*.hwpx'%n)[0]
    out=tempfile.mktemp(suffix='.hwpx'); convert(hwp,out)
    o=unzip_parts(out); t=unzip_parts(ref)
    print('sample', n)
    for part in ['Contents/header.xml','Contents/section0.xml','Contents/content.hpf']:
        print('  %-24s %.4f'%(part, score_part(o[part],t[part])['match']))
"
```
Expected: 2013 section0 ≈0.99+, header ≈0.998, content.hpf ≈1.0; samples 3 & 4 header/section unchanged.
```bash
git add hwp2hwpx/ tests/test_container_rdf.py
git commit -m "feat: emit META-INF/container.rdf and rootfile entry"
```

---

## Final verification (after all tasks)

- Full suite green: `.venv/bin/python -m pytest -q`.
- 2013 BinData names == Hancom (`image1.jpg`, `image2.bmp`, `image3.png`); JPEG present.
- Samples 3 & 4: header/section0 fidelity unchanged; sample 4 bindata byte-identical.
- Remaining 2013 gaps are the documented non-goals + separate milestones (substFont, header `numberings`/`supscript`/fill/color, PrvImage).
