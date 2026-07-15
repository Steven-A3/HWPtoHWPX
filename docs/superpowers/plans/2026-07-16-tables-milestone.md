# Tables Milestone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert HWP tables into faithful HWPX tables (structure, cell text, merged cells, real cell borders + background fills), recovering document content the milestone-1 converter drops.

**Architecture:** Extend the existing 4 layers (Reader → HWP model → Mapper → OWPML model → Writer) with table + borderFill element types. The paragraph parser (reader) and paragraph mapper are made reusable/recursive so table cells reuse the exact body-paragraph code path.

**Tech Stack:** Python 3.9+ (dev on 3.11), `lxml`, `pyhwp`, `pytest`. Same as milestone 1.

## Global Constraints

- Python **3.9+** floor; no post-3.9 syntax. Deps limited to stdlib, lxml, pyhwp, pytest.
- Run tests with `.venv/bin/pytest`. hwp5proc is auto-located (milestone 1).
- All milestone-1 tests MUST stay green. Output MUST still open in Hancom.
- **Verified ground-truth values (from the real samples — use verbatim):**
  - HWP side (pyhwp): table = `Paragraph/LineSeg/TableControl > TableBody(borderfill-id, cellspacing, cols, rows, padding-*) > TableRow > TableCell(borderfill-id, col, row, colspan, rowspan, width, height, valign) > Paragraph*`. All 33 `TableControl`s are direct `LineSeg` children. `IdMappings/BorderFill` (52 of them, positional id) each has 5 `Border(attribute-name=left|right|top|bottom|diagonal, stroke-type, width="0.4mm", color)` + optional `FillColorPattern(background-color)`.
  - HWPX side: `hp:tbl(id, zOrder="0", numberingType="TABLE", textWrap="TOP_AND_BOTTOM", textFlow="BOTH_SIDES", lock="0", dropcapstyle="None", pageBreak="NONE", repeatHeader="1", rowCnt, colCnt, cellSpacing, borderFillIDRef, noAdjust="0")` inside a `hp:run`; children `hp:sz(width, widthRelTo="ABSOLUTE", height, heightRelTo="ABSOLUTE", protect="0")`, `hp:pos(treatAsChar="1", affectLSpacing="0", flowWithText="1", allowOverlap="0", holdAnchorAndSO="0", vertRelTo="PARA", horzRelTo="COLUMN", vertAlign="TOP", horzAlign="LEFT")`, `hp:outMargin`/`hp:inMargin(left,right,top,bottom)`, then `hp:tr*`.
  - `hp:tc(name="", header="0", hasMargin="0", protect="0", editable="0", dirty="0", borderFillIDRef)` > `hp:subList(id="", textDirection="HORIZONTAL", lineWrap="BREAK", vertAlign, linkListIDRef="0", linkListNextIDRef="0", textWidth="0", textHeight="0", hasTextRef="0", hasNumRef="0")` (holds cell `hp:p`s) + `hp:cellAddr(colAddr, rowAddr)` + `hp:cellSpan(colSpan, rowSpan)` + `hp:cellSz(width, height)` + `hp:cellMargin(left,right,top,bottom)`.
  - Header: `<hh:borderFills itemCnt>` sits in `refList` **after fontfaces, before charProperties**. Each `<hh:borderFill id threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">` has `<hh:slash type="NONE" Crooked="0" isCounter="0"/>`, `<hh:backSlash .../>`, `<hh:leftBorder/rightBorder/topBorder/bottomBorder/diagonal type=SOLID|NONE width="0.4 mm" color="#000000"/>`, and (only when filled) `<hc:fillBrush><hc:winBrush faceColor="#RRGGBB" hatchColor="#FF000000" alpha="0"/></hc:fillBrush>`.
  - Normalizations: HWP `stroke-type` → UPPERCASE (`solid`→`SOLID`, `none`→`NONE`); width `"0.4mm"` → `"0.4 mm"` (single space before unit); color passes through; HWP cell `valign` `middle`/`top`/`bottom` → HWPX `CENTER`/`TOP`/`BOTTOM`.
- OWPML namespaces already in `hwp2hwpx/constants.py` `NS` (includes `hc` = core, needed for fillBrush/winBrush).

## Files touched

```
hwp2hwpx/hwpmodel/model.py     # + HwpBorder, HwpBorderFill, HwpTable/Row/Cell; HwpRun.table; HwpDocInfo.border_fills
hwp2hwpx/hwpmodel/reader.py    # + _parse_border_fills; parse_paragraph (refactor) + _parse_table
hwp2hwpx/owpml/model.py        # + Border, BorderFill, Tc, TableRow, Table; Run.table; Header.border_fills
hwp2hwpx/mapper/border_fill.py # NEW: map_border_fills
hwp2hwpx/mapper/table.py       # NEW: map_table (imports map_paragraph)
hwp2hwpx/mapper/body.py        # map_paragraph (refactor, reusable+recursive); wire border_fills
hwp2hwpx/owpml/header_writer.py# emit <hh:borderFills>
hwp2hwpx/owpml/section_writer.py# _write_paragraph/_write_run/_write_table/_write_cell
```

---

### Task 1: HWP model — border + table dataclasses

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py`
- Create: `tests/test_hwpmodel_tables.py`

**Interfaces:**
- Produces (dataclasses in `hwp2hwpx.hwpmodel.model`):
  - `HwpBorder(kind: str, stroke_type: str = "none", width: str = "0.1mm", color: str = "#000000")`
  - `HwpBorderFill(index: int, borders=[], fill_color: str | None = None)`
  - `HwpTableCell(col=0, row=0, col_span=1, row_span=1, width=0, height=0, border_fill_id=0, valign="middle", paragraphs=[])`
  - `HwpTableRow(cells=[])`
  - `HwpTable(rows=0, cols=0, cell_spacing=0, border_fill_id=0, width=0, height=0, table_rows=[])`
  - `HwpRun` gains `table=None` (kept as last field, default None).
  - `HwpDocInfo` gains `border_fills=[]`.

- [ ] **Step 1: Write failing test `tests/test_hwpmodel_tables.py`**

```python
from hwp2hwpx.hwpmodel.model import (
    HwpBorder, HwpBorderFill, HwpTableCell, HwpTableRow, HwpTable,
    HwpRun, HwpParagraph, HwpDocInfo,
)


def test_border_and_borderfill():
    bf = HwpBorderFill(index=3, borders=[HwpBorder(kind="left", stroke_type="solid",
                                                   width="0.4mm", color="#000000")],
                       fill_color="#bbbbbb")
    assert bf.index == 3
    assert bf.borders[0].kind == "left"
    assert bf.fill_color == "#bbbbbb"


def test_table_structure_and_run_table():
    cell = HwpTableCell(col=1, row=0, col_span=2, row_span=1, width=100, height=50,
                        border_fill_id=5, valign="middle",
                        paragraphs=[HwpParagraph(para_shape_id=0)])
    table = HwpTable(rows=1, cols=3, cell_spacing=0, border_fill_id=4,
                     width=300, height=50, table_rows=[HwpTableRow(cells=[cell])])
    run = HwpRun(char_shape_id=0, text="", table=table)
    assert run.table.table_rows[0].cells[0].col_span == 2
    assert HwpRun(char_shape_id=0, text="x").table is None


def test_docinfo_border_fills_default_empty():
    assert HwpDocInfo().border_fills == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_hwpmodel_tables.py -v`
Expected: FAIL with `ImportError` (new names not defined).

- [ ] **Step 3: Edit `hwp2hwpx/hwpmodel/model.py`** — add `table=None` to `HwpRun`, `border_fills` to `HwpDocInfo`, and append the new dataclasses.

Change `HwpRun`:
```python
@dataclass
class HwpRun:
    char_shape_id: int
    text: str = ""
    table: "HwpTable" = None
```

Change `HwpDocInfo` to add the field:
```python
@dataclass
class HwpDocInfo:
    fonts: list = field(default_factory=list)
    char_shapes: list = field(default_factory=list)
    para_shapes: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
```

Append at end of file:
```python
@dataclass
class HwpBorder:
    kind: str
    stroke_type: str = "none"
    width: str = "0.1mm"
    color: str = "#000000"


@dataclass
class HwpBorderFill:
    index: int
    borders: list = field(default_factory=list)
    fill_color: str = None


@dataclass
class HwpTableCell:
    col: int = 0
    row: int = 0
    col_span: int = 1
    row_span: int = 1
    width: int = 0
    height: int = 0
    border_fill_id: int = 0
    valign: str = "middle"
    paragraphs: list = field(default_factory=list)


@dataclass
class HwpTableRow:
    cells: list = field(default_factory=list)


@dataclass
class HwpTable:
    rows: int = 0
    cols: int = 0
    cell_spacing: int = 0
    border_fill_id: int = 0
    width: int = 0
    height: int = 0
    table_rows: list = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_hwpmodel_tables.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass (milestone-1 tests unaffected; `HwpRun(char_shape_id, text)` still works because `text` now has a default but positional call is unchanged).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py tests/test_hwpmodel_tables.py
git commit -m "feat: HWP model dataclasses for borders and tables"
```

---

### Task 2: OWPML model — border + table dataclasses

**Files:**
- Modify: `hwp2hwpx/owpml/model.py`
- Create: `tests/test_owpml_model_tables.py`

**Interfaces:**
- Produces (dataclasses in `hwp2hwpx.owpml.model`):
  - `Border(kind: str, type: str = "NONE", width: str = "0.1 mm", color: str = "#000000")`
  - `BorderFill(id: int, borders=[], fill_color: str | None = None)`
  - `Tc(col_addr=0, row_addr=0, col_span=1, row_span=1, width=0, height=0, border_fill_id=0, valign="CENTER", paras=[])`
  - `TableRow(cells=[])`
  - `Table(id=0, row_cnt=0, col_cnt=0, cell_spacing=0, border_fill_id=0, width=0, height=0, rows=[])`
  - `Run` gains `table=None` (last field).
  - `Header` gains `border_fills=[]`.

- [ ] **Step 1: Write failing test `tests/test_owpml_model_tables.py`**

```python
from hwp2hwpx.owpml.model import (
    Border, BorderFill, Tc, TableRow, Table, Run, Header,
)


def test_borderfill_and_table():
    bf = BorderFill(id=5, borders=[Border(kind="left", type="SOLID",
                                          width="0.4 mm", color="#000000")],
                    fill_color="#bbbbbb")
    tc = Tc(col_addr=0, row_addr=0, col_span=2, row_span=1, width=100, height=50,
            border_fill_id=5, valign="CENTER", paras=[])
    table = Table(id=1, row_cnt=1, col_cnt=3, cell_spacing=0, border_fill_id=4,
                  width=300, height=50, rows=[TableRow(cells=[tc])])
    assert bf.borders[0].type == "SOLID"
    assert table.rows[0].cells[0].col_span == 2


def test_run_table_and_header_border_fills_defaults():
    assert Run(char_pr_id=0).table is None
    assert Header().border_fills == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_owpml_model_tables.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Edit `hwp2hwpx/owpml/model.py`** — add `table=None` to `Run`, `border_fills` to `Header`, append new dataclasses.

Change `Run`:
```python
@dataclass
class Run:
    char_pr_id: int
    texts: list = field(default_factory=list)
    table: "Table" = None
```

Change `Header` to add the field:
```python
@dataclass
class Header:
    fonts_by_lang: dict = field(default_factory=dict)
    char_prs: list = field(default_factory=list)
    para_prs: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
```

Append at end of file:
```python
@dataclass
class Border:
    kind: str
    type: str = "NONE"
    width: str = "0.1 mm"
    color: str = "#000000"


@dataclass
class BorderFill:
    id: int
    borders: list = field(default_factory=list)
    fill_color: str = None


@dataclass
class Tc:
    col_addr: int = 0
    row_addr: int = 0
    col_span: int = 1
    row_span: int = 1
    width: int = 0
    height: int = 0
    border_fill_id: int = 0
    valign: str = "CENTER"
    paras: list = field(default_factory=list)


@dataclass
class TableRow:
    cells: list = field(default_factory=list)


@dataclass
class Table:
    id: int = 0
    row_cnt: int = 0
    col_cnt: int = 0
    cell_spacing: int = 0
    border_fill_id: int = 0
    width: int = 0
    height: int = 0
    rows: list = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_owpml_model_tables.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/model.py tests/test_owpml_model_tables.py
git commit -m "feat: OWPML model dataclasses for borders and tables"
```

---

### Task 3: Reader — parse BorderFill definitions

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py` (add `_parse_border_fills`, call it in `read_docinfo`)
- Create: `tests/test_reader_borderfills.py`

**Interfaces:**
- Consumes: `HwpBorder`, `HwpBorderFill` from model.
- Produces: `read_docinfo(...)` result's `.border_fills` populated (positional index == id). `HwpBorderFill.borders` has one `HwpBorder` per `<Border>` (kind from `attribute-name`); `fill_color` = `FillColorPattern/@background-color` when present and not `"none"`, else `None`.

- [ ] **Step 1: Write failing test `tests/test_reader_borderfills.py`**

```python
from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _docinfo():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read())


def test_border_fills_count_and_shape():
    di = _docinfo()
    assert len(di.border_fills) == 52
    bf = di.border_fills[0]
    kinds = [b.kind for b in bf.borders]
    assert kinds == ["left", "right", "top", "bottom", "diagonal"]


def test_some_borderfill_has_solid_border():
    di = _docinfo()
    assert any(any(b.stroke_type == "solid" for b in bf.borders)
               for bf in di.border_fills)


def test_some_borderfill_has_fill_color():
    di = _docinfo()
    assert any(bf.fill_color for bf in di.border_fills)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_reader_borderfills.py -v`
Expected: FAIL (border_fills empty → assertions fail).

- [ ] **Step 3: Edit `hwp2hwpx/hwpmodel/reader.py`** — extend the import, add `_parse_border_fills`, and set `border_fills` in the `read_docinfo` return.

Update the model import at the top to include the new names:
```python
from .model import (
    HwpFont, HwpCharShape, HwpParaShape, HwpDocInfo,
    HwpRun, HwpParagraph, HwpSection, HwpDocument,
    HwpBorder, HwpBorderFill, HwpTable, HwpTableRow, HwpTableCell,
)
```

Add this helper (e.g. after `_font_group_offsets`):
```python
def _parse_border_fills(id_mappings):
    out = []
    for i, bf_el in enumerate(id_mappings.findall("BorderFill")):
        borders = []
        for b in bf_el.findall("Border"):
            borders.append(HwpBorder(
                kind=b.get("attribute-name") or "",
                stroke_type=b.get("stroke-type") or "none",
                width=b.get("width") or "0.1mm",
                color=b.get("color") or "#000000",
            ))
        fcp = bf_el.find("FillColorPattern")
        fill_color = None
        if fcp is not None:
            bg = fcp.get("background-color")
            if bg and bg.lower() != "none":
                fill_color = bg
        out.append(HwpBorderFill(index=i, borders=borders, fill_color=fill_color))
    return out
```

In `read_docinfo`, change the final return to include border_fills:
```python
    return HwpDocInfo(fonts=fonts, char_shapes=char_shapes,
                      para_shapes=para_shapes,
                      border_fills=_parse_border_fills(id_mappings))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_reader_borderfills.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_borderfills.py
git commit -m "feat: parse HWP BorderFill definitions"
```

---

### Task 4: Mapper — border fills → OWPML BorderFill

**Files:**
- Create: `hwp2hwpx/mapper/border_fill.py`
- Create: `tests/test_mapper_borderfill.py`

**Interfaces:**
- Consumes: `hwpmodel.model.HwpBorderFill`/`HwpBorder`.
- Produces: `hwp2hwpx.mapper.border_fill.map_border_fills(hwp_bfs) -> list[owpml.model.BorderFill]`. Per border: `type` = UPPERCASE stroke_type, `width` = normalized `"N mm"`, `color` passthrough. `BorderFill.id` = source index; `fill_color` passthrough.

- [ ] **Step 1: Write failing test `tests/test_mapper_borderfill.py`**

```python
from hwp2hwpx.mapper.border_fill import map_border_fills
from hwp2hwpx.hwpmodel.model import HwpBorderFill, HwpBorder


def test_maps_stroke_width_color_and_fill():
    src = [HwpBorderFill(index=2, borders=[
        HwpBorder(kind="left", stroke_type="solid", width="0.4mm", color="#000000"),
        HwpBorder(kind="top", stroke_type="none", width="0.1mm", color="#123456"),
    ], fill_color="#bbbbbb")]
    out = map_border_fills(src)
    assert out[0].id == 2
    left = out[0].borders[0]
    assert left.kind == "left"
    assert left.type == "SOLID"
    assert left.width == "0.4 mm"
    assert left.color == "#000000"
    assert out[0].borders[1].type == "NONE"
    assert out[0].fill_color == "#bbbbbb"


def test_width_already_spaced_is_untouched():
    src = [HwpBorderFill(index=0, borders=[
        HwpBorder(kind="left", stroke_type="solid", width="0.5 mm", color="#000000")])]
    assert map_border_fills(src)[0].borders[0].width == "0.5 mm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mapper_borderfill.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/mapper/border_fill.py`**

```python
"""Map HWP border/fill definitions to OWPML borderFills."""
from ..owpml.model import Border, BorderFill


def _norm_width(w):
    w = (w or "0.1mm").strip()
    if w.endswith("mm") and not w.endswith(" mm"):
        w = w[:-2].rstrip() + " mm"
    return w


def map_border_fills(hwp_bfs):
    out = []
    for bf in hwp_bfs:
        borders = [Border(
            kind=b.kind,
            type=(b.stroke_type or "none").upper(),
            width=_norm_width(b.width),
            color=b.color or "#000000",
        ) for b in bf.borders]
        out.append(BorderFill(id=bf.index, borders=borders, fill_color=bf.fill_color))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_mapper_borderfill.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/border_fill.py tests/test_mapper_borderfill.py
git commit -m "feat: mapper for border fills"
```

---

### Task 5: Writer — emit `<hh:borderFills>` in header

**Files:**
- Modify: `hwp2hwpx/owpml/header_writer.py`
- Create: `tests/test_header_borderfills.py`

**Interfaces:**
- Consumes: `owpml.model.Header.border_fills` (list of `BorderFill`).
- Produces: `header_xml` emits `<hh:borderFills itemCnt=…>` immediately after `<hh:fontfaces>` and before `<hh:charProperties>`. Each `<hh:borderFill>` has slash/backSlash, the 5 side borders, and `<hc:fillBrush><hc:winBrush faceColor=… hatchColor="#FF000000" alpha="0"/></hc:fillBrush>` only when `fill_color` is set.

- [ ] **Step 1: Write failing test `tests/test_header_borderfills.py`**

```python
from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, BorderFill, Border
from hwp2hwpx.constants import NS


def _hh(t):
    return "{%s}%s" % (NS["hh"], t)


def _hc(t):
    return "{%s}%s" % (NS["hc"], t)


def _header():
    return Header(border_fills=[
        BorderFill(id=0, borders=[
            Border(kind="left", type="SOLID", width="0.4 mm", color="#000000"),
            Border(kind="right", type="SOLID", width="0.4 mm", color="#000000"),
            Border(kind="top", type="SOLID", width="0.4 mm", color="#000000"),
            Border(kind="bottom", type="SOLID", width="0.4 mm", color="#000000"),
            Border(kind="diagonal", type="NONE", width="0.1 mm", color="#000000"),
        ]),
        BorderFill(id=1, borders=[], fill_color="#bbbbbb"),
    ])


def test_borderfills_present_with_count():
    root = etree.fromstring(header_xml(_header()))
    bfs = root.find(".//" + _hh("borderFills"))
    assert bfs is not None
    assert bfs.get("itemCnt") == "2"
    assert len(bfs.findall(_hh("borderFill"))) == 2
    first = bfs.findall(_hh("borderFill"))[0]
    assert first.find(_hh("leftBorder")).get("type") == "SOLID"
    assert first.find(_hh("leftBorder")).get("width") == "0.4 mm"


def test_fillbrush_only_when_filled():
    root = etree.fromstring(header_xml(_header()))
    bfs = root.findall(".//" + _hh("borderFill"))
    assert bfs[0].find(_hc("fillBrush")) is None          # id 0: no fill
    wb = bfs[1].find(_hc("fillBrush")).find(_hc("winBrush"))
    assert wb.get("faceColor") == "#bbbbbb"


def test_borderfills_before_charproperties():
    root = etree.fromstring(header_xml(_header()))
    ref = root.find(_hh("refList"))
    order = [c.tag.rsplit("}", 1)[-1] for c in ref]
    assert order.index("borderFills") < order.index("charProperties")
    assert order.index("fontfaces") < order.index("borderFills")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_header_borderfills.py -v`
Expected: FAIL (no borderFills element yet).

- [ ] **Step 3: Edit `hwp2hwpx/owpml/header_writer.py`** — add an `_hc` helper and emit borderFills between fontfaces and charProperties.

Add near `_hh`:
```python
def _hc(tag):
    return "{%s}%s" % (NS["hc"], tag)
```

Immediately AFTER the `fontfaces` block (the `for lang, fonts in header.fonts_by_lang.items()` loop) and BEFORE the `charProperties` block, insert:
```python
    bfs_el = etree.SubElement(ref, _hh("borderFills"))
    bfs_el.set("itemCnt", str(len(header.border_fills)))
    for bf in header.border_fills:
        be = etree.SubElement(bfs_el, _hh("borderFill"))
        be.set("id", str(bf.id))
        be.set("threeD", "0")
        be.set("shadow", "0")
        be.set("centerLine", "NONE")
        be.set("breakCellSeparateLine", "0")
        for slash in ("slash", "backSlash"):
            se = etree.SubElement(be, _hh(slash))
            se.set("type", "NONE")
            se.set("Crooked", "0")
            se.set("isCounter", "0")
        by_kind = {b.kind: b for b in bf.borders}
        for kind, tag in (("left", "leftBorder"), ("right", "rightBorder"),
                          ("top", "topBorder"), ("bottom", "bottomBorder"),
                          ("diagonal", "diagonal")):
            b = by_kind.get(kind)
            el = etree.SubElement(be, _hh(tag))
            el.set("type", b.type if b else "NONE")
            el.set("width", b.width if b else "0.1 mm")
            el.set("color", b.color if b else "#000000")
        if bf.fill_color:
            fb = etree.SubElement(be, _hc("fillBrush"))
            wb = etree.SubElement(fb, _hc("winBrush"))
            wb.set("faceColor", bf.fill_color)
            wb.set("hatchColor", "#FF000000")
            wb.set("alpha", "0")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_header_borderfills.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass (milestone-1 header test is order-agnostic; empty `border_fills` yields `<hh:borderFills itemCnt="0"/>`).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/header_writer.py tests/test_header_borderfills.py
git commit -m "feat: emit hh:borderFills in header.xml"
```

---

### Task 6: Reader — recursive paragraph parser + table parsing

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py` (replace `_paragraph_runs`/`read_document` internals with `parse_paragraph` + `_parse_table`)
- Create: `tests/test_reader_tables.py`

**Interfaces:**
- Produces: `hwp2hwpx.hwpmodel.reader.parse_paragraph(para_el) -> HwpParagraph` — walks `LineSeg/*` in order: `Text` (non-empty) → text `HwpRun`; `TableControl` → `HwpRun(table=_parse_table(el))`; skips other controls. `_parse_table(tc_el) -> HwpTable` (rows/cols/border_fill_id/cell_spacing/width/height + rows→cells→paragraphs via recursive `parse_paragraph`). `read_document` uses `parse_paragraph` for top-level `ColumnSet/Paragraph`.
- Behavior preserved: body still yields one `HwpSection` with 220 top-level paragraphs; 33 of them now carry a table run.

- [ ] **Step 1: Write failing test `tests/test_reader_tables.py`**

```python
from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _doc():
    with open(FIXTURE, "rb") as f:
        return read_document(f.read())


def _tables(doc):
    return [r.table for s in doc.sections for p in s.paragraphs
            for r in p.runs if r.table is not None]


def test_body_still_has_220_paragraphs():
    doc = _doc()
    assert len(doc.sections[0].paragraphs) == 220


def test_thirty_three_tables_in_body():
    doc = _doc()
    assert len(_tables(_doc())) == 33


def test_table_has_rows_cells_and_cell_text():
    tables = _tables(_doc())
    t = tables[0]
    assert len(t.table_rows) >= 1
    cell = t.table_rows[0].cells[0]
    assert cell.border_fill_id > 0
    # a cell somewhere in the first table has real paragraph text
    text = "".join(r.text for row in t.table_rows for c in row.cells
                   for para in c.paragraphs for r in para.runs)
    assert text.strip() != ""


def test_merged_cell_span_detected():
    tables = _tables(_doc())
    spans = [(c.col_span, c.row_span) for t in tables
             for row in t.table_rows for c in row.cells]
    assert any(cs > 1 or rs > 1 for cs, rs in spans)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_reader_tables.py -v`
Expected: FAIL (`ImportError`/`AttributeError`: `parse_paragraph`/`.table` not present yet).

- [ ] **Step 3: Edit `hwp2hwpx/hwpmodel/reader.py`** — replace the `_paragraph_runs` function and the paragraph-building loop in `read_document` with the recursive parser.

Delete `_paragraph_runs` (lines defining it) and add these two functions in its place:
```python
def _parse_table(tc_el):
    body = tc_el.find("TableBody")
    if body is None:
        return HwpTable()
    rows = []
    for row_el in body.findall("TableRow"):
        cells = []
        for cell_el in row_el.findall("TableCell"):
            cells.append(HwpTableCell(
                col=_int(cell_el.get("col")),
                row=_int(cell_el.get("row")),
                col_span=_int(cell_el.get("colspan"), 1),
                row_span=_int(cell_el.get("rowspan"), 1),
                width=_int(cell_el.get("width")),
                height=_int(cell_el.get("height")),
                border_fill_id=_int(cell_el.get("borderfill-id")),
                valign=cell_el.get("valign") or "middle",
                paragraphs=[parse_paragraph(p) for p in cell_el.findall("Paragraph")],
            ))
        rows.append(HwpTableRow(cells=cells))
    width = sum(c.width for c in rows[0].cells) if rows else 0
    return HwpTable(
        rows=_int(body.get("rows")),
        cols=_int(body.get("cols")),
        cell_spacing=_int(body.get("cellspacing")),
        border_fill_id=_int(body.get("borderfill-id")),
        width=width,
        height=_int(tc_el.get("height")),
        table_rows=rows,
    )


def parse_paragraph(para_el):
    """Build one HwpParagraph, walking LineSeg children in reading order:
    Text -> text run; TableControl -> table run; other controls skipped."""
    runs = []
    for child in para_el.findall("LineSeg/*"):
        if child.tag == "Text":
            content = child.text or ""
            if content:
                runs.append(HwpRun(
                    char_shape_id=_int(child.get("charshape-id")),
                    text=content,
                ))
        elif child.tag == "TableControl":
            runs.append(HwpRun(
                char_shape_id=_int(child.get("charshape-id")),
                text="",
                table=_parse_table(child),
            ))
    return HwpParagraph(
        para_shape_id=_int(para_el.get("parashape-id")),
        style_id=_int(para_el.get("style-id")),
        runs=runs,
    )
```

In `read_document`, replace the inner paragraph loop:
```python
        for col in sec_el.findall("ColumnSet"):
            for para_el in col.findall("Paragraph"):
                paras.append(parse_paragraph(para_el))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_reader_tables.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass. `tests/test_reader_body.py` still holds (220 paragraphs; multi-run + non-empty text still true).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_tables.py
git commit -m "feat: recursive paragraph parser + HWP table parsing"
```

---

### Task 7: Mapper — reusable `map_paragraph` + `map_table` + wire border_fills

**Files:**
- Modify: `hwp2hwpx/mapper/body.py` (extract `map_paragraph`, wire `border_fills`)
- Create: `hwp2hwpx/mapper/table.py`
- Create: `tests/test_mapper_table.py`

**Interfaces:**
- Produces: `hwp2hwpx.mapper.body.map_paragraph(hpar, para_id) -> owpml.model.Para` (text run → `Run(texts=[Text])`; table run → `Run(texts=[], table=map_table(...))` via deferred import; empty → one placeholder `Run(char_pr_id=0, texts=[])`; `style_id` clamped to 0). `hwp2hwpx.mapper.table.map_table(hwp_table) -> owpml.model.Table` (cells → `Tc` with cellAddr/cellSpan/cellSz, valign mapped, cell paras via `map_paragraph`). `map_document` sets `Header.border_fills = map_border_fills(di.border_fills)`.

- [ ] **Step 1: Write failing test `tests/test_mapper_table.py`**

```python
from hwp2hwpx.mapper.table import map_table
from hwp2hwpx.mapper.body import map_document, map_paragraph
from hwp2hwpx.hwpmodel.model import (
    HwpTable, HwpTableRow, HwpTableCell, HwpParagraph, HwpRun,
    HwpDocument, HwpDocInfo, HwpBorderFill, HwpBorder, HwpSection,
)


def _table():
    cell = HwpTableCell(col=0, row=0, col_span=2, row_span=1, width=100, height=50,
                        border_fill_id=5, valign="middle",
                        paragraphs=[HwpParagraph(para_shape_id=0,
                                                 runs=[HwpRun(char_shape_id=3, text="가")])])
    return HwpTable(rows=1, cols=2, cell_spacing=0, border_fill_id=4,
                    width=100, height=50, table_rows=[HwpTableRow(cells=[cell])])


def test_map_table_structure():
    t = map_table(_table())
    assert t.row_cnt == 1 and t.col_cnt == 2 and t.border_fill_id == 4
    tc = t.rows[0].cells[0]
    assert (tc.col_addr, tc.row_addr) == (0, 0)
    assert (tc.col_span, tc.row_span) == (2, 1)
    assert tc.valign == "CENTER"
    assert tc.paras[0].runs[0].texts[0].content == "가"


def test_map_paragraph_with_table_run():
    hpar = HwpParagraph(para_shape_id=0, runs=[HwpRun(char_shape_id=0, table=_table())])
    para = map_paragraph(hpar, 7)
    assert para.id == 7
    assert para.runs[0].table is not None
    assert para.runs[0].table.col_cnt == 2


def test_map_document_wires_border_fills():
    di = HwpDocInfo(border_fills=[HwpBorderFill(index=0, borders=[
        HwpBorder(kind="left", stroke_type="solid", width="0.4mm", color="#000000")])])
    doc = map_document(HwpDocument(docinfo=di, sections=[HwpSection(paragraphs=[])]))
    assert len(doc.header.border_fills) == 1
    assert doc.header.border_fills[0].borders[0].type == "SOLID"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mapper_table.py -v`
Expected: FAIL with `ModuleNotFoundError` (no `mapper.table`).

- [ ] **Step 3: Create `hwp2hwpx/mapper/table.py`**

```python
"""Map HWP tables to OWPML tables. Cell paragraphs reuse map_paragraph."""
from ..owpml.model import Table, TableRow, Tc
from .body import map_paragraph

_VALIGN = {"middle": "CENTER", "center": "CENTER", "top": "TOP", "bottom": "BOTTOM"}


def map_table(hwp_table):
    rows = []
    for hrow in hwp_table.table_rows:
        cells = []
        for c in hrow.cells:
            cells.append(Tc(
                col_addr=c.col,
                row_addr=c.row,
                col_span=c.col_span,
                row_span=c.row_span,
                width=c.width,
                height=c.height,
                border_fill_id=c.border_fill_id,
                valign=_VALIGN.get((c.valign or "").lower(), "CENTER"),
                paras=[map_paragraph(p, i) for i, p in enumerate(c.paragraphs)],
            ))
        rows.append(TableRow(cells=cells))
    return Table(
        id=0,
        row_cnt=hwp_table.rows,
        col_cnt=hwp_table.cols,
        cell_spacing=hwp_table.cell_spacing,
        border_fill_id=hwp_table.border_fill_id,
        width=hwp_table.width,
        height=hwp_table.height,
        rows=rows,
    )
```

- [ ] **Step 4: Rewrite `hwp2hwpx/mapper/body.py`** to extract `map_paragraph` and wire border_fills:

```python
"""Map a whole HwpDocument to an OwpmlDocument."""
from ..owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Text, Metadata,
)
from .fonts import map_fonts
from .char_pr import map_char_shapes
from .para_pr import map_para_shapes
from .border_fill import map_border_fills


def map_paragraph(hpar, para_id):
    """Map one HwpParagraph to an OWPML Para. A table run becomes a Run whose
    `table` is set (deferred import breaks the body<->table recursion cycle)."""
    runs = []
    for r in hpar.runs:
        if getattr(r, "table", None) is not None:
            from .table import map_table
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[],
                            table=map_table(r.table)))
        else:
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[Text(r.text)]))
    if not runs:
        # Hancom always emits at least one <hp:run> per <hp:p>.
        runs = [Run(char_pr_id=0, texts=[])]
    # style_id clamped to 0: header.xml emits only the default style id 0.
    return Para(id=para_id, para_pr_id=hpar.para_shape_id, style_id=0, runs=runs)


def map_document(hwp_doc, title=""):
    di = hwp_doc.docinfo
    header = Header(
        fonts_by_lang=map_fonts(di.fonts),
        char_prs=map_char_shapes(di.char_shapes),
        para_prs=map_para_shapes(di.para_shapes),
        border_fills=map_border_fills(di.border_fills),
    )
    sections = []
    para_id = 0
    for hsec in hwp_doc.sections:
        paras = []
        for hpar in hsec.paragraphs:
            paras.append(map_paragraph(hpar, para_id))
            para_id += 1
        sections.append(Section(paras=paras))
    return OwpmlDocument(header=header, sections=sections,
                         metadata=Metadata(title=title))
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_mapper_table.py tests/test_mapper_body.py -v`
Expected: PASS. (`test_mapper_body.py` from milestone 1 still holds — `map_document` output for a plain paragraph is unchanged, and `style_id` is still clamped to 0.)

- [ ] **Step 6: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/mapper/table.py hwp2hwpx/mapper/body.py tests/test_mapper_table.py
git commit -m "feat: map_paragraph refactor + map_table + wire border fills"
```

---

### Task 8: Writer — emit `<hp:tbl>` in sections

**Files:**
- Modify: `hwp2hwpx/owpml/section_writer.py`
- Create: `tests/test_section_writer_tables.py`

**Interfaces:**
- Consumes: `owpml.model.Section`/`Para`/`Run`/`Table`/`TableRow`/`Tc`.
- Produces: `section_xml(section)` unchanged signature. Now: paragraphs written via `_write_paragraph`; a run with `run.table` set emits an `<hp:tbl>` subtree inside the `<hp:run>`. Table `id` attribute assigned from a per-section running counter (deterministic, unique within the section).

- [ ] **Step 1: Write failing test `tests/test_section_writer_tables.py`**

```python
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text, Table, TableRow, Tc
from hwp2hwpx.constants import NS


def _hp(t):
    return "{%s}%s" % (NS["hp"], t)


def _section_with_table():
    cell = Tc(col_addr=0, row_addr=0, col_span=2, row_span=1, width=100, height=50,
              border_fill_id=5, valign="CENTER",
              paras=[Para(id=0, para_pr_id=0,
                          runs=[Run(char_pr_id=3, texts=[Text("셀")])])])
    table = Table(id=0, row_cnt=1, col_cnt=2, cell_spacing=0, border_fill_id=4,
                  width=100, height=50, rows=[TableRow(cells=[cell])])
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[], table=table)])
    return Section(paras=[para])


def test_table_emitted_inside_run():
    root = etree.fromstring(section_xml(_section_with_table()))
    tbl = root.find(".//" + _hp("tbl"))
    assert tbl is not None
    assert tbl.get("rowCnt") == "1" and tbl.get("colCnt") == "2"
    assert tbl.get("borderFillIDRef") == "4"
    # tbl lives inside a run
    assert tbl.getparent().tag == _hp("run")
    tc = tbl.find(".//" + _hp("tc"))
    assert tc.get("borderFillIDRef") == "5"
    assert tc.find(_hp("cellAddr")).get("colAddr") == "0"
    assert tc.find(_hp("cellSpan")).get("colSpan") == "2"
    assert tc.find(_hp("cellSz")).get("width") == "100"
    # cell paragraph text is present in the subList
    assert tc.find(_hp("subList")) is not None
    texts = [t.text for t in tc.iter(_hp("t"))]
    assert "셀" in texts


def test_table_id_is_set_and_wellformed():
    root = etree.fromstring(section_xml(_section_with_table()))
    tbl = root.find(".//" + _hp("tbl"))
    assert tbl.get("id") is not None and tbl.get("id") != ""
    assert tbl.find(_hp("sz")) is not None
    assert tbl.find(_hp("pos")) is not None


def test_plain_paragraph_unchanged():
    from hwp2hwpx.owpml.model import Section as S, Para as P, Run as R, Text as T
    root = etree.fromstring(section_xml(S(paras=[P(id=0, para_pr_id=1,
                                                   runs=[R(char_pr_id=2, texts=[T("x")])])])))
    p = root.find(_hp("p"))
    assert p.get("paraPrIDRef") == "1"
    assert p.find(_hp("run")).find(_hp("t")).text == "x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_section_writer_tables.py -v`
Expected: FAIL (no `<hp:tbl>` emitted).

- [ ] **Step 3: Rewrite `hwp2hwpx/owpml/section_writer.py`**

```python
"""Serialize an OWPML Section to Contents/sectionN.xml."""
from lxml import etree
from ..constants import NS, XML_DECL

_NSMAP = {k: v for k, v in NS.items()}


def _hs(tag):
    return "{%s}%s" % (NS["hs"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _write_run(p_el, run, state):
    r = etree.SubElement(p_el, _hp("run"))
    r.set("charPrIDRef", str(run.char_pr_id))
    for t in run.texts:
        te = etree.SubElement(r, _hp("t"))
        te.text = t.content
    if getattr(run, "table", None) is not None:
        _write_table(r, run.table, state)


def _write_paragraph(parent_el, para, state):
    p = etree.SubElement(parent_el, _hp("p"))
    p.set("id", str(para.id))
    p.set("paraPrIDRef", str(para.para_pr_id))
    p.set("styleIDRef", str(para.style_id))
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")
    for run in para.runs:
        _write_run(p, run, state)


def _write_table(run_el, table, state):
    state["tbl_id"] += 1
    t = etree.SubElement(run_el, _hp("tbl"))
    t.set("id", str(state["tbl_id"]))
    for k, v in (("zOrder", "0"), ("numberingType", "TABLE"),
                 ("textWrap", "TOP_AND_BOTTOM"), ("textFlow", "BOTH_SIDES"),
                 ("lock", "0"), ("dropcapstyle", "None"), ("pageBreak", "NONE"),
                 ("repeatHeader", "1")):
        t.set(k, v)
    t.set("rowCnt", str(table.row_cnt))
    t.set("colCnt", str(table.col_cnt))
    t.set("cellSpacing", str(table.cell_spacing))
    t.set("borderFillIDRef", str(table.border_fill_id))
    t.set("noAdjust", "0")
    sz = etree.SubElement(t, _hp("sz"))
    sz.set("width", str(table.width))
    sz.set("widthRelTo", "ABSOLUTE")
    sz.set("height", str(table.height))
    sz.set("heightRelTo", "ABSOLUTE")
    sz.set("protect", "0")
    pos = etree.SubElement(t, _hp("pos"))
    for k, v in (("treatAsChar", "1"), ("affectLSpacing", "0"),
                 ("flowWithText", "1"), ("allowOverlap", "0"),
                 ("holdAnchorAndSO", "0"), ("vertRelTo", "PARA"),
                 ("horzRelTo", "COLUMN"), ("vertAlign", "TOP"),
                 ("horzAlign", "LEFT")):
        pos.set(k, v)
    for tag in ("outMargin", "inMargin"):
        m = etree.SubElement(t, _hp(tag))
        for side in ("left", "right", "top", "bottom"):
            m.set(side, "141")
    for row in table.rows:
        tr = etree.SubElement(t, _hp("tr"))
        for cell in row.cells:
            _write_cell(tr, cell, state)


def _write_cell(tr_el, cell, state):
    tc = etree.SubElement(tr_el, _hp("tc"))
    tc.set("name", "")
    tc.set("header", "0")
    tc.set("hasMargin", "0")
    tc.set("protect", "0")
    tc.set("editable", "0")
    tc.set("dirty", "0")
    tc.set("borderFillIDRef", str(cell.border_fill_id))
    sub = etree.SubElement(tc, _hp("subList"))
    for k, v in (("id", ""), ("textDirection", "HORIZONTAL"), ("lineWrap", "BREAK"),
                 ("vertAlign", cell.valign), ("linkListIDRef", "0"),
                 ("linkListNextIDRef", "0"), ("textWidth", "0"),
                 ("textHeight", "0"), ("hasTextRef", "0"), ("hasNumRef", "0")):
        sub.set(k, v)
    for para in cell.paras:
        _write_paragraph(sub, para, state)
    ca = etree.SubElement(tc, _hp("cellAddr"))
    ca.set("colAddr", str(cell.col_addr))
    ca.set("rowAddr", str(cell.row_addr))
    cspan = etree.SubElement(tc, _hp("cellSpan"))
    cspan.set("colSpan", str(cell.col_span))
    cspan.set("rowSpan", str(cell.row_span))
    csz = etree.SubElement(tc, _hp("cellSz"))
    csz.set("width", str(cell.width))
    csz.set("height", str(cell.height))
    cm = etree.SubElement(tc, _hp("cellMargin"))
    for side in ("left", "right", "top", "bottom"):
        cm.set(side, "141")


def section_xml(section):
    root = etree.Element(_hs("sec"), nsmap=_NSMAP)
    state = {"tbl_id": 0}
    for para in section.paras:
        _write_paragraph(root, para, state)
    return XML_DECL + etree.tostring(root, encoding="UTF-8")
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_section_writer_tables.py tests/test_section_writer.py -v`
Expected: PASS (new + milestone-1 section tests).

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py tests/test_section_writer_tables.py
git commit -m "feat: emit hp:tbl (tables) in section writer"
```

---

### Task 9: End-to-end fidelity + no-dangling-ref + smoke

**Files:**
- Create: `tests/test_convert_tables.py`

**Interfaces:**
- Consumes: `convert.convert`, `fidelity` helpers.
- Produces: end-to-end assertions that tables now appear in the real conversion, no `borderFillIDRef` dangles, and fidelity improved.

- [ ] **Step 1: Write test `tests/test_convert_tables.py`**

```python
import zipfile
from lxml import etree
from hwp2hwpx.convert import convert
from hwp2hwpx.constants import NS

SAMPLE = "samples/3.과업지시서_070.hwp"


def _hp(t):
    return "{%s}%s" % (NS["hp"], t)


def _hh(t):
    return "{%s}%s" % (NS["hh"], t)


def _convert(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE, str(out))
    with zipfile.ZipFile(out) as z:
        return (etree.fromstring(z.read("Contents/section0.xml")),
                etree.fromstring(z.read("Contents/header.xml")))


def test_tables_and_cells_present(tmp_path):
    sec, _ = _convert(tmp_path)
    assert len(sec.findall(".//" + _hp("tbl"))) == 33
    assert len(sec.findall(".//" + _hp("tc"))) > 300      # ~353 cells


def test_cell_text_recovered(tmp_path):
    sec, _ = _convert(tmp_path)
    # some cell subList contains real text
    texts = [t.text or "" for tc in sec.iter(_hp("tc")) for t in tc.iter(_hp("t"))]
    assert any(s.strip() for s in texts)


def test_no_dangling_borderfill_ref(tmp_path):
    sec, head = _convert(tmp_path)
    defined = {bf.get("id") for bf in head.iter(_hh("borderFill"))}
    refs = {e.get("borderFillIDRef") for e in sec.iter()
            if e.get("borderFillIDRef") is not None}
    assert refs and refs <= defined       # every ref resolves to a defined borderFill


def test_section_is_wellformed_and_tbl_inside_run(tmp_path):
    sec, _ = _convert(tmp_path)
    tbl = sec.find(".//" + _hp("tbl"))
    assert tbl.getparent().tag == _hp("run")
```

- [ ] **Step 2: Run the tables end-to-end test**

Run: `.venv/bin/pytest tests/test_convert_tables.py -v`
Expected: PASS (33 tables, >300 cells, cell text present, no dangling refs).

- [ ] **Step 3: Print the improved fidelity report** (informational)

Run:
```bash
.venv/bin/python -c "
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import report
import tempfile, os
out=os.path.join(tempfile.mkdtemp(),'o.hwpx')
convert('samples/3.과업지시서_070.hwp', out)
print(report(out, 'samples/3.과업지시서_070.hwpx'))
"
```
Expected: `Contents/section0.xml` match materially higher than the ~19.9% baseline (tc/cellAddr/cellSpan/subList no longer in the top-missing list), and header.xml match up (borderFills now present). Record the new numbers in the commit message or report.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: all pass (milestone-1 + tables).

- [ ] **Step 5: Manual smoke — verify it still opens** (verification-before-completion)

Run:
```bash
.venv/bin/hwp2hwpx "samples/4.제안요청서_070.hwp" -o /tmp/tables_out.hwpx && .venv/bin/python -c "import zipfile; z=zipfile.ZipFile('/tmp/tables_out.hwpx'); s=z.read('Contents/section0.xml'); print('tbl count:', s.count(b'<hp:tbl'))"
```
Expected: prints a non-zero `tbl count`. If Hancom Office is available, open `/tmp/tables_out.hwpx` and confirm tables render with borders and cell text.

- [ ] **Step 6: Commit**

```bash
git add tests/test_convert_tables.py
git commit -m "test: end-to-end table conversion + fidelity + no dangling refs"
```

---

## Follow-up plans (not in this plan)

Driven by the updated harness backlog after tables land:
1. **paraPr/charPr full attributes** (margins, lineSpacing, per-language font refs) — biggest remaining header gap.
2. **linesegarray** layout metadata (body + cells).
3. **Images / bin-data** (`BinData/`, `hp:pic`).
4. **Styles & numbering** (real `hh:styles`/`hh:numberings`, replacing the clamp-to-0).
5. **Headers/footers, master pages, shapes.**

## Self-Review notes

- **Spec coverage:** models (Tasks 1–2), reader borderFills (Task 3) + tables (Task 6), mapper borderFills (Task 4) + tables/paragraph-reuse (Task 7), writer borderFills (Task 5) + tables (Task 8), end-to-end/fidelity/no-dangling-ref/smoke (Task 9). Merged cells (colSpan/rowSpan) covered in Tasks 6/7/8 tests. Real borders + fills covered in Tasks 3/4/5. Recursion (cell paras reuse) covered by `parse_paragraph`/`map_paragraph`. Deferred items (linesegarray, per-language fonts) explicitly out of scope.
- **Type consistency:** HWP-side `HwpBorder/HwpBorderFill/HwpTable/HwpTableRow/HwpTableCell` and `HwpRun.table`/`HwpDocInfo.border_fills` used identically across Tasks 1/3/6/7. OWPML-side `Border/BorderFill/Tc/TableRow/Table` and `Run.table`/`Header.border_fills` consistent across Tasks 2/4/5/7/8. `map_paragraph(hpar, para_id)`, `map_table(hwp_table)`, `map_border_fills(hwp_bfs)`, `parse_paragraph(para_el)`, `_parse_table(tc_el)`, `_parse_border_fills(id_mappings)` each defined once and referenced with matching signatures. Field-name mapping (HWP `col`/`row`/`col_span` → OWPML `col_addr`/`row_addr`/`col_span`; HWP `rows`/`cols` → OWPML `row_cnt`/`col_cnt`) is explicit in Task 7's `map_table`.
- **Import cycle:** `body.py` top-level does NOT import `table.py`; `map_paragraph` imports `map_table` lazily inside the function. `table.py` top-imports `map_paragraph` from `body`. No cycle at load time. (Verified reasoning in Task 7.)
- **Placeholder scan:** no TBD/TODO; every code step is complete.
