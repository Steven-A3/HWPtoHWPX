# paraPr Fidelity + BorderFill ID Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit the full `<hh:paraPr>` (margins, line spacing, heading, break settings, border) and correct the BorderFill id base to 1-based (matching Hancom), raising header.xml fidelity and fixing table border refs.

**Architecture:** Extend the existing Reader → HWP model → Mapper → OWPML model → Writer pipeline: parse the full `ParaShape`, map it (margins ÷2, lineSpacing ratio→PERCENT, border ref raw), and serialize the full paraPr subtree. Separately, make BorderFill definition ids 1-based and use raw (unshifted) refs.

**Tech Stack:** Python 3.9+ (dev 3.11), lxml, pyhwp, pytest.

## Global Constraints

- Python **3.9+** only. Deps: stdlib, lxml, pyhwp, pytest. `.venv/bin/pytest`. hwp5proc auto-located.
- All prior tests (milestone 1 + tables, 75 total) MUST stay green. Output MUST still open in Hancom.
- **Verified ground truth (use verbatim):**
  - Hancom `hh:borderFill` ids are **1..52** (1-based). HWP `borderfill-id` refs are 1..52. Correct base: def id = positional index **+ 1**; refs use the **raw** HWP value (no −1 shift).
  - `hh:paraPr` attrs: `id tabPrIDRef condense="0" fontLineHeight="0" snapToGrid="1" suppressLineNumbers="0" checked="0"`. Children in order: `hh:align(horizontal, vertical="BASELINE")`, `hh:heading(type="NONE" idRef="0" level=…)`, `hh:breakSetting(breakLatinWord="KEEP_WORD" breakNonLatinWord="BREAK_WORD" widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK")`, `hh:autoSpacing(eAsianEng="0" eAsianNum="0")`, `hp:switch` → `hp:case(hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar")` and `hp:default`, each containing `hh:margin` (children `hc:intent/left/right/prev/next` each `value=… unit="HWPUNIT"`) + `hh:lineSpacing(type value unit="HWPUNIT")`; then `hh:border(borderFillIDRef offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0")`.
  - **Transforms (verified):** `hc:intent` = HWP `indent` ÷ 2; `hc:left/right/prev/next` = HWP `doubled-margin-left/right/top/bottom` ÷ 2 (sign preserved; sample values even). `hh:lineSpacing type="PERCENT" value=` HWP `linespacing` when `linespacing-type="ratio"`. `hh:border/@borderFillIDRef` = HWP `borderfill-id` (raw, 1-based).
  - `hh:tabProperties` in refList (after charProperties, before paraProperties). Minimal default child: `<hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/>`. `tabPrIDRef` clamped to `0` this milestone.
  - refList order: fontfaces → borderFills → charProperties → **tabProperties** → paraProperties → styles.
- Units are HWPUNIT. Margins/indent can be negative.

## Files touched

```
hwp2hwpx/hwpmodel/model.py     # HwpParaShape gains indent/margins/linespacing/border_fill_id/level
hwp2hwpx/owpml/model.py        # ParaPr gains intent/margins/lineSpacing/border_fill_id/heading/tab_pr_id
hwp2hwpx/hwpmodel/reader.py    # borderfill refs raw (remove -1 shift); clamp to [1,count]; full ParaShape parse
hwp2hwpx/mapper/border_fill.py # BorderFill.id = index + 1
hwp2hwpx/mapper/para_pr.py     # full paraPr mapping
hwp2hwpx/owpml/header_writer.py# full <hh:paraPr> subtree + <hh:tabProperties>
```

---

### Task 1: BorderFill id base → 1-based (defs +1, raw refs)

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py` (remove `_border_fill_id` shift; use raw `_int`; retune clamp to `[1, count]`)
- Modify: `hwp2hwpx/mapper/border_fill.py` (`id = bf.index + 1`)
- Modify: `tests/test_mapper_borderfill.py` (id expectation)
- Modify: `tests/test_reader_borderfill_clamp.py` (new 1-based semantics)

**Interfaces:**
- Produces: `map_border_fills` returns `BorderFill`s with ids `1..N`. Reader stores table/cell/para `border_fill_id` = raw HWP value (1-based), clamped into `[1, N]` (values `<1` → 1).

- [ ] **Step 1: Update `tests/test_mapper_borderfill.py`** — change the id assertion to 1-based.

Replace `assert out[0].id == 2` with:
```python
    assert out[0].id == 3          # 1-based: source index 2 -> id 3
```

- [ ] **Step 2: Run it to confirm it now FAILS** (mapper still emits 0-based)

Run: `.venv/bin/pytest tests/test_mapper_borderfill.py -v`
Expected: FAIL (`out[0].id` is 2, not 3).

- [ ] **Step 3: Edit `hwp2hwpx/mapper/border_fill.py`** — make def ids 1-based.

Change the append line:
```python
        out.append(BorderFill(id=bf.index + 1, borders=borders, fill_color=bf.fill_color))
```

- [ ] **Step 4: Run mapper test** — Run: `.venv/bin/pytest tests/test_mapper_borderfill.py -v` — Expected: PASS.

- [ ] **Step 5: Replace `tests/test_reader_borderfill_clamp.py`** with the 1-based semantics test:

```python
"""Table/cell borderfill-id refs are raw (1-based) and clamped into [1, N]."""
from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _tables():
    with open(FIXTURE, "rb") as f:
        doc = read_document(f.read())
    return [r.table for s in doc.sections for p in s.paragraphs
            for r in p.runs if r.table is not None]


def test_refs_are_raw_1_based_in_range():
    # every cell border_fill_id is within the defined 1..52 range (no dangling, no -1 shift)
    ids = [c.border_fill_id for t in _tables() for row in t.table_rows for c in row.cells]
    assert ids
    assert all(1 <= i <= 52 for i in ids)


def test_first_table_cell_ref_matches_hwp_raw():
    # first table's body borderfill-id is 4 in the fixture (raw, unshifted)
    assert _tables()[0].border_fill_id == 4
```

- [ ] **Step 6: Run it to confirm FAIL** (reader still shifts −1, so body id would be 3 not 4)

Run: `.venv/bin/pytest tests/test_reader_borderfill_clamp.py -v`
Expected: FAIL (`border_fill_id == 3`).

- [ ] **Step 7: Edit `hwp2hwpx/hwpmodel/reader.py`** — remove the `_border_fill_id` shift, use raw, retune clamp.

Replace the `_border_fill_id` function (the `n - 1 if n > 0 else 0` version) with:
```python
def _border_fill_id(v):
    """HWP5 borderfill-id is 1-based and equals the OWPML borderFill id we
    emit (definition id = document-order index + 1). Use the raw value; a
    missing/<1 value falls back to the first definition (id 1)."""
    n = _int(v, 0)
    return n if n >= 1 else 1
```

In `_clamp_table_border_fill_ids`, change the bounds to `[1, count]` (1-based). Replace its body's `last`/`_clamp` with:
```python
    if border_fill_count <= 0:
        return
    last = border_fill_count  # ids are 1..count

    def _clamp(n):
        if n < 1:
            return 1
        if n > last:
            return last
        return n
```
(Leave the `_walk_table`/`_walk_paragraphs` traversal unchanged.)

- [ ] **Step 8: Run the reader clamp test** — Run: `.venv/bin/pytest tests/test_reader_borderfill_clamp.py -v` — Expected: PASS.

- [ ] **Step 9: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass. Tables tests still hold (`cell.border_fill_id > 0` true; no-dangling `refs ⊆ defined` holds since defs are now 1..52 and refs 1..52).

- [ ] **Step 10: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py hwp2hwpx/mapper/border_fill.py tests/test_mapper_borderfill.py tests/test_reader_borderfill_clamp.py
git commit -m "fix: borderFill ids are 1-based to match Hancom (defs +1, raw refs)"
```

---

### Task 2: Model fields — HwpParaShape + ParaPr

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (`HwpParaShape` fields)
- Modify: `hwp2hwpx/owpml/model.py` (`ParaPr` fields)
- Create: `tests/test_parapr_model_fields.py`

**Interfaces:**
- `HwpParaShape(index, align="LEFT", indent=0, margin_left=0, margin_right=0, margin_top=0, margin_bottom=0, line_spacing=100, line_spacing_type="ratio", border_fill_id=1, level=0)`.
- `ParaPr(id, align="LEFT", heading_type="NONE", heading_level=0, intent=0, margin_left=0, margin_right=0, margin_prev=0, margin_next=0, line_spacing=100, line_spacing_type="PERCENT", border_fill_id=1, tab_pr_id=0)`.

- [ ] **Step 1: Write failing test `tests/test_parapr_model_fields.py`**

```python
from hwp2hwpx.hwpmodel.model import HwpParaShape
from hwp2hwpx.owpml.model import ParaPr


def test_hwp_para_shape_new_fields():
    s = HwpParaShape(index=1, align="CENTER", indent=-4000, margin_left=2000,
                     margin_right=2000, margin_top=0, margin_bottom=0,
                     line_spacing=140, line_spacing_type="ratio",
                     border_fill_id=2, level=0)
    assert s.indent == -4000 and s.margin_left == 2000
    assert s.line_spacing == 140 and s.border_fill_id == 2


def test_para_pr_new_fields_have_defaults():
    p = ParaPr(id=0)
    assert p.intent == 0 and p.margin_prev == 0
    assert p.line_spacing == 100 and p.line_spacing_type == "PERCENT"
    assert p.border_fill_id == 1 and p.tab_pr_id == 0
    # existing 2-arg construction still works
    assert ParaPr(id=3, align="RIGHT").align == "RIGHT"
```

- [ ] **Step 2: Run to verify FAIL** — Run: `.venv/bin/pytest tests/test_parapr_model_fields.py -v` — Expected: FAIL (`TypeError`/`AttributeError`).

- [ ] **Step 3: Edit `hwp2hwpx/hwpmodel/model.py`** — replace the `HwpParaShape` dataclass:

```python
@dataclass
class HwpParaShape:
    index: int
    align: str = "LEFT"
    indent: int = 0
    margin_left: int = 0
    margin_right: int = 0
    margin_top: int = 0
    margin_bottom: int = 0
    line_spacing: int = 100
    line_spacing_type: str = "ratio"
    border_fill_id: int = 1
    level: int = 0
```

- [ ] **Step 4: Edit `hwp2hwpx/owpml/model.py`** — replace the `ParaPr` dataclass:

```python
@dataclass
class ParaPr:
    id: int
    align: str = "LEFT"
    heading_type: str = "NONE"
    heading_level: int = 0
    intent: int = 0
    margin_left: int = 0
    margin_right: int = 0
    margin_prev: int = 0
    margin_next: int = 0
    line_spacing: int = 100
    line_spacing_type: str = "PERCENT"
    border_fill_id: int = 1
    tab_pr_id: int = 0
```

- [ ] **Step 5: Run to verify PASS** — Run: `.venv/bin/pytest tests/test_parapr_model_fields.py -v` — Expected: PASS.

- [ ] **Step 6: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass (existing `ParaPr(id=…, align=…)` calls unaffected).

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py tests/test_parapr_model_fields.py
git commit -m "feat: paraShape/paraPr model fields for margins, line spacing, border"
```

---

### Task 3: Reader — parse full ParaShape

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py` (the `para_shapes` loop in `read_docinfo`)
- Create: `tests/test_reader_parashape.py`

**Interfaces:**
- Produces: `read_docinfo(...).para_shapes[i]` carries raw `indent`, `margin_left/right/top/bottom` (from `doubled-margin-*`), `line_spacing`, `line_spacing_type`, `border_fill_id` (raw), `level` for each `ParaShape` (positional index == id).

- [ ] **Step 1: Write failing test `tests/test_reader_parashape.py`**

```python
from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _ps():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read()).para_shapes


def test_para_shape_count():
    assert len(_ps()) == 126


def test_para_shape_11_raw_values():
    # verified from the fixture: indent -4000, doubled margins 2000/2000/0/0,
    # linespacing 140 ratio, borderfill-id present
    s = _ps()[11]
    assert s.indent == -4000
    assert s.margin_left == 2000 and s.margin_right == 2000
    assert s.line_spacing == 140 and s.line_spacing_type == "ratio"
    assert s.border_fill_id >= 1


def test_para_shape_14_center_align_and_linespacing_180():
    s = _ps()[14]
    assert s.align == "CENTER"
    assert s.line_spacing == 180
```

- [ ] **Step 2: Run to verify FAIL** — Run: `.venv/bin/pytest tests/test_reader_parashape.py -v` — Expected: FAIL (fields still default 0).

- [ ] **Step 3: Edit `hwp2hwpx/hwpmodel/reader.py`** — replace the `para_shapes` loop in `read_docinfo`:

```python
    para_shapes = []
    for i, el in enumerate(id_mappings.findall("ParaShape")):
        raw = (el.get("align") or "left").lower()
        para_shapes.append(HwpParaShape(
            index=i,
            align=_ALIGN_MAP.get(raw, "LEFT"),
            indent=_int(el.get("indent")),
            margin_left=_int(el.get("doubled-margin-left")),
            margin_right=_int(el.get("doubled-margin-right")),
            margin_top=_int(el.get("doubled-margin-top")),
            margin_bottom=_int(el.get("doubled-margin-bottom")),
            line_spacing=_int(el.get("linespacing"), 100),
            line_spacing_type=el.get("linespacing-type") or "ratio",
            border_fill_id=_border_fill_id(el.get("borderfill-id")),
            level=_int(el.get("level")),
        ))
```

- [ ] **Step 4: Run to verify PASS** — Run: `.venv/bin/pytest tests/test_reader_parashape.py -v` — Expected: PASS (3 tests). If a value differs, inspect the fixture to reconcile — do NOT weaken.

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_parashape.py
git commit -m "feat: parse full HWP ParaShape (margins, line spacing, border)"
```

---

### Task 4: Mapper — full map_para_shapes

**Files:**
- Modify: `hwp2hwpx/mapper/para_pr.py`
- Create: `tests/test_mapper_parapr_full.py`

**Interfaces:**
- Produces: `map_para_shapes(shapes) -> list[ParaPr]` with `intent`/margins halved (sign preserved, toward zero), `line_spacing_type` ratio→PERCENT, `border_fill_id` = raw, `heading_type="NONE"`/`heading_level=level`, `tab_pr_id=0`.

- [ ] **Step 1: Write failing test `tests/test_mapper_parapr_full.py`**

```python
from hwp2hwpx.mapper.para_pr import map_para_shapes
from hwp2hwpx.hwpmodel.model import HwpParaShape


def test_margins_halved_sign_preserved():
    out = map_para_shapes([HwpParaShape(index=0, indent=-4000, margin_left=2000,
                                        margin_right=2000, margin_top=0, margin_bottom=0)])
    p = out[0]
    assert p.intent == -2000
    assert p.margin_left == 1000 and p.margin_right == 1000
    assert p.margin_prev == 0 and p.margin_next == 0


def test_linespacing_ratio_to_percent_and_border_raw():
    out = map_para_shapes([HwpParaShape(index=2, line_spacing=140,
                                        line_spacing_type="ratio", border_fill_id=13)])
    p = out[0]
    assert p.id == 2
    assert p.line_spacing == 140 and p.line_spacing_type == "PERCENT"
    assert p.border_fill_id == 13          # raw, 1-based, no shift
    assert p.tab_pr_id == 0                # clamped
    assert p.heading_type == "NONE"


def test_odd_negative_halves_toward_zero():
    out = map_para_shapes([HwpParaShape(index=0, indent=-4001)])
    assert out[0].intent == -2000          # toward zero, not -2001
```

- [ ] **Step 2: Run to verify FAIL** — Run: `.venv/bin/pytest tests/test_mapper_parapr_full.py -v` — Expected: FAIL.

- [ ] **Step 3: Rewrite `hwp2hwpx/mapper/para_pr.py`**

```python
"""Map HWP paragraph shapes to OWPML paraPr."""
from ..owpml.model import ParaPr

_LS_TYPE = {"ratio": "PERCENT", "fixed": "FIXED",
            "atleast": "AT_LEAST", "at-least": "AT_LEAST"}


def _half(v):
    """Halve toward zero, preserving sign (HWP stores margins doubled)."""
    return -((-v) // 2) if v < 0 else v // 2


def map_para_shapes(shapes):
    out = []
    for s in shapes:
        out.append(ParaPr(
            id=s.index,
            align=s.align,
            heading_type="NONE",
            heading_level=s.level,
            intent=_half(s.indent),
            margin_left=_half(s.margin_left),
            margin_right=_half(s.margin_right),
            margin_prev=_half(s.margin_top),
            margin_next=_half(s.margin_bottom),
            line_spacing=s.line_spacing,
            line_spacing_type=_LS_TYPE.get((s.line_spacing_type or "ratio").lower(),
                                           "PERCENT"),
            border_fill_id=s.border_fill_id if s.border_fill_id >= 1 else 1,
            tab_pr_id=0,
        ))
    return out
```

- [ ] **Step 4: Run to verify PASS** — Run: `.venv/bin/pytest tests/test_mapper_parapr_full.py tests/test_mapper_parapr.py -v` — Expected: PASS (new + milestone-1 parapr test; the latter only checks id+align, still valid).

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/mapper/para_pr.py tests/test_mapper_parapr_full.py
git commit -m "feat: full paraPr mapping (margins/2, lineSpacing, border, heading)"
```

---

### Task 5: Writer — full `<hh:paraPr>` + `<hh:tabProperties>`

**Files:**
- Modify: `hwp2hwpx/owpml/header_writer.py`
- Create: `tests/test_header_parapr_full.py`

**Interfaces:**
- Consumes: `Header.para_prs` (full `ParaPr`).
- Produces: `header_xml` emits, per paraPr, the full subtree (align/heading/breakSetting/autoSpacing/switch(case+default: margin+lineSpacing)/border), and a `<hh:tabProperties itemCnt="1"><hh:tabPr id="0" autoTabLeft="0" autoTabRight="0"/></hh:tabProperties>` inserted after charProperties and before paraProperties.

- [ ] **Step 1: Write failing test `tests/test_header_parapr_full.py`**

```python
from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, ParaPr
from hwp2hwpx.constants import NS


def _hh(t):
    return "{%s}%s" % (NS["hh"], t)


def _hp(t):
    return "{%s}%s" % (NS["hp"], t)


def _hc(t):
    return "{%s}%s" % (NS["hc"], t)


def _header():
    return Header(para_prs=[ParaPr(id=0, align="CENTER", intent=-2000,
                                   margin_left=1000, margin_right=1000,
                                   margin_prev=0, margin_next=0,
                                   line_spacing=140, line_spacing_type="PERCENT",
                                   border_fill_id=2, heading_level=0, tab_pr_id=0)])


def test_parapr_full_subtree():
    root = etree.fromstring(header_xml(_header()))
    pp = root.find(".//" + _hh("paraPr"))
    assert pp.get("tabPrIDRef") == "0"
    assert pp.find(_hh("align")).get("horizontal") == "CENTER"
    assert pp.find(_hh("heading")).get("type") == "NONE"
    assert pp.find(_hh("breakSetting")).get("breakLatinWord") == "KEEP_WORD"
    assert pp.find(_hh("autoSpacing")) is not None
    sw = pp.find(_hp("switch"))
    assert sw is not None
    case = sw.find(_hp("case"))
    assert case.get("{%s}required-namespace" % NS["hp"]).endswith("HwpUnitChar")
    # both case and default carry margin + lineSpacing
    for branch in (case, sw.find(_hp("default"))):
        m = branch.find(_hh("margin"))
        assert m.find(_hc("intent")).get("value") == "-2000"
        assert m.find(_hc("left")).get("value") == "1000"
        ls = branch.find(_hh("lineSpacing"))
        assert ls.get("type") == "PERCENT" and ls.get("value") == "140"
    bd = pp.find(_hh("border"))
    assert bd.get("borderFillIDRef") == "2"


def test_tabproperties_present_and_ordered():
    root = etree.fromstring(header_xml(_header()))
    ref = root.find(_hh("refList"))
    order = [c.tag.rsplit("}", 1)[-1] for c in ref]
    assert order.index("charProperties") < order.index("tabProperties") < order.index("paraProperties")
    tp = root.find(".//" + _hh("tabProperties"))
    assert tp.get("itemCnt") == "1"
    assert tp.find(_hh("tabPr")).get("id") == "0"
```

- [ ] **Step 2: Run to verify FAIL** — Run: `.venv/bin/pytest tests/test_header_parapr_full.py -v` — Expected: FAIL (paraPr minimal; no tabProperties).

- [ ] **Step 3: Edit `hwp2hwpx/owpml/header_writer.py`**

Add an `_hp` helper near `_hc`:
```python
def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)
```

Add this module-level helper (e.g. above `header_xml`):
```python
def _write_margin_and_spacing(parent, pp):
    m = etree.SubElement(parent, _hh("margin"))
    for tag, val in (("intent", pp.intent), ("left", pp.margin_left),
                     ("right", pp.margin_right), ("prev", pp.margin_prev),
                     ("next", pp.margin_next)):
        e = etree.SubElement(m, _hc(tag))
        e.set("value", str(val))
        e.set("unit", "HWPUNIT")
    ls = etree.SubElement(parent, _hh("lineSpacing"))
    ls.set("type", pp.line_spacing_type)
    ls.set("value", str(pp.line_spacing))
    ls.set("unit", "HWPUNIT")
```

Insert a `tabProperties` block AFTER the `charProperties` block and BEFORE the `paraProperties` block:
```python
    tabs_el = etree.SubElement(ref, _hh("tabProperties"))
    tabs_el.set("itemCnt", "1")
    tab_el = etree.SubElement(tabs_el, _hh("tabPr"))
    tab_el.set("id", "0")
    tab_el.set("autoTabLeft", "0")
    tab_el.set("autoTabRight", "0")
```

Replace the existing `paraProperties` loop body (the `for pp in header.para_prs:` block that only sets id + align) with the full subtree:
```python
    pps = etree.SubElement(ref, _hh("paraProperties"))
    pps.set("itemCnt", str(len(header.para_prs)))
    for pp in header.para_prs:
        pe = etree.SubElement(pps, _hh("paraPr"))
        pe.set("id", str(pp.id))
        pe.set("tabPrIDRef", str(pp.tab_pr_id))
        pe.set("condense", "0")
        pe.set("fontLineHeight", "0")
        pe.set("snapToGrid", "1")
        pe.set("suppressLineNumbers", "0")
        pe.set("checked", "0")
        al = etree.SubElement(pe, _hh("align"))
        al.set("horizontal", pp.align)
        al.set("vertical", "BASELINE")
        hd = etree.SubElement(pe, _hh("heading"))
        hd.set("type", pp.heading_type)
        hd.set("idRef", "0")
        hd.set("level", str(pp.heading_level))
        bs = etree.SubElement(pe, _hh("breakSetting"))
        for k, v in (("breakLatinWord", "KEEP_WORD"),
                     ("breakNonLatinWord", "BREAK_WORD"), ("widowOrphan", "0"),
                     ("keepWithNext", "0"), ("keepLines", "0"),
                     ("pageBreakBefore", "0"), ("lineWrap", "BREAK")):
            bs.set(k, v)
        aus = etree.SubElement(pe, _hh("autoSpacing"))
        aus.set("eAsianEng", "0")
        aus.set("eAsianNum", "0")
        sw = etree.SubElement(pe, _hp("switch"))
        case = etree.SubElement(sw, _hp("case"))
        case.set("{%s}required-namespace" % NS["hp"],
                 "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar")
        _write_margin_and_spacing(case, pp)
        default = etree.SubElement(sw, _hp("default"))
        _write_margin_and_spacing(default, pp)
        bd = etree.SubElement(pe, _hh("border"))
        bd.set("borderFillIDRef", str(pp.border_fill_id))
        for k in ("offsetLeft", "offsetRight", "offsetTop", "offsetBottom"):
            bd.set(k, "0")
        bd.set("connect", "0")
        bd.set("ignoreMargin", "0")
```

- [ ] **Step 4: Run to verify PASS** — Run: `.venv/bin/pytest tests/test_header_parapr_full.py tests/test_header_writer.py -v` — Expected: PASS (new + milestone-1 header test; the latter checks fonts/charPr/align, all still present).

- [ ] **Step 5: Run full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/header_writer.py tests/test_header_parapr_full.py
git commit -m "feat: emit full hh:paraPr subtree + hh:tabProperties"
```

---

### Task 6: End-to-end fidelity + smoke

**Files:**
- Create: `tests/test_convert_parapr.py`

**Interfaces:**
- Consumes: `convert.convert`, `fidelity`.

- [ ] **Step 1: Write test `tests/test_convert_parapr.py`**

```python
import zipfile
from lxml import etree
from hwp2hwpx.convert import convert
from hwp2hwpx.constants import NS

SAMPLE = "samples/3.과업지시서_070.hwp"


def _hh(t):
    return "{%s}%s" % (NS["hh"], t)


def _hp(t):
    return "{%s}%s" % (NS["hp"], t)


def _convert(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE, str(out))
    with zipfile.ZipFile(out) as z:
        return (etree.fromstring(z.read("Contents/header.xml")),
                etree.fromstring(z.read("Contents/section0.xml")))


def test_parapr_has_margin_switch_linespacing_border(tmp_path):
    head, _ = _convert(tmp_path)
    pps = head.findall(".//" + _hh("paraPr"))
    assert len(pps) == 126
    # every paraPr carries the full structure
    for pp in pps:
        assert pp.find(_hp("switch")) is not None
        assert pp.find(_hh("border")) is not None
    # a known non-zero margin (paraShape 11: intent -2000, left 1000)
    pp11 = [p for p in pps if p.get("id") == "11"][0]
    intent = pp11.find(".//" + "{%s}intent" % NS["hc"]).get("value")
    assert intent == "-2000"


def test_borderfill_ids_are_1_based_and_no_dangling(tmp_path):
    head, sec = _convert(tmp_path)
    defined = {int(bf.get("id")) for bf in head.iter(_hh("borderFill"))}
    assert min(defined) == 1 and max(defined) == 52
    refs = {int(e.get("borderFillIDRef")) for e in list(head.iter()) + list(sec.iter())
            if e.get("borderFillIDRef") is not None}
    assert refs <= defined            # every paraPr/table/cell ref resolves


def test_tables_still_intact(tmp_path):
    _, sec = _convert(tmp_path)
    assert len(sec.findall(".//" + _hp("tbl"))) == 33
```

- [ ] **Step 2: Run the e2e test** — Run: `.venv/bin/pytest tests/test_convert_parapr.py -v` — Expected: PASS. If a dangling ref or wrong intent appears, STOP and report it as a real defect (do not weaken).

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
Expected: `header.xml` match materially higher than the ~19% baseline; `margin`/`lineSpacing`/`switch` no longer dominate the miss list. Record the new numbers in the commit message.

- [ ] **Step 4: Run the full suite** — Run: `.venv/bin/pytest -q` — Expected: all pass.

- [ ] **Step 5: Manual smoke — still opens** (verification-before-completion)

Run:
```bash
.venv/bin/hwp2hwpx "samples/4.제안요청서_070.hwp" -o /tmp/parapr_out.hwpx && .venv/bin/python -c "import zipfile; z=zipfile.ZipFile('/tmp/parapr_out.hwpx'); h=z.read('Contents/header.xml'); print('paraPr switch count:', h.count(b'<hp:switch'), '| tabProperties:', b'tabProperties' in h)"
```
Expected: non-zero switch count, `tabProperties: True`. If Hancom Office is available, open `/tmp/parapr_out.hwpx` and confirm paragraph indentation/spacing look right and tables still render.

- [ ] **Step 6: Commit**

```bash
git add tests/test_convert_parapr.py
git commit -m "test: end-to-end paraPr fidelity + 1-based borderFill refs"
```

---

## Follow-up plans (not in this plan)
1. **charPr full attributes** (milestone 3b): per-language fontRef, ratio/spacing/relSz/offset, underline/strikeout/outline/shadow.
2. **linesegarray** layout metadata.
3. Real tab definitions (replace tabPrIDRef clamp), real numbering/bullets (heading type), images, real styles.

## Self-Review notes
- **Spec coverage:** borderFill 1-based (Task 1), model fields (Task 2), reader full ParaShape (Task 3), mapper margins÷2/lineSpacing/border/heading/tab clamp (Task 4), writer full paraPr subtree + tabProperties + refList order (Task 5), e2e fidelity + no-dangling + tables-intact + smoke (Task 6). Margin transform (÷2, sign) verified in Tasks 4/6; lineSpacing ratio→PERCENT in Tasks 4/5/6; border ref raw/1-based in Tasks 1/4/6.
- **Type consistency:** `HwpParaShape` fields (indent/margin_left/right/top/bottom/line_spacing/line_spacing_type/border_fill_id/level) defined in Task 2, parsed in Task 3, consumed in Task 4. `ParaPr` fields (intent/margin_left/right/prev/next/line_spacing/line_spacing_type/border_fill_id/heading_type/heading_level/tab_pr_id) defined in Task 2, produced in Task 4, consumed in Task 5. `_border_fill_id` (raw, ≥1) and `_clamp` ([1,count]) consistent in Task 1/3. `map_border_fills` id=index+1 (Task 1) matches raw refs (Task 1/3).
- **Placeholder scan:** none; every step has complete code. Existing-test updates (test_mapper_borderfill, test_reader_borderfill_clamp) are explicit in Task 1.
