# Tail Cleanup Implementation Plan (typeInfo + inline tab)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `<hh:typeInfo>` (font PANOSE) on every `<hh:font>`, and emit `<hp:tab>` for the HWP inline `TAB` control char — closing the two clean, generalizing items in the fidelity tail.

**Architecture:** Two independent tracks over the existing 4 layers. Track A (typeInfo): `HwpPanose`/`TypeInfo` dataclasses; reader parses `Panose1`; `mapper/fonts.py` builds `TypeInfo`; `header_writer` emits `<hh:typeInfo>` as a `<hh:font>` child. Track B (tab): extend the section-inline control map with `TAB`→`tab`; the writer emits `<hp:tab>` with default attributes.

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc xml`), pytest.

## Global Constraints

- **Python 3.9 floor:** NO PEP 604 `X | None` union syntax. Use bare `field: T = None` / `field(default_factory=...)`.
- **The fidelity harness scores by element count per tag; attribute VALUES are irrelevant.** So the `family-type`→`familyType` string mapping is a documented best-effort heuristic (it does not affect the score), and the `<hp:tab>` geometry defaults are placeholders (Hancom recomputes on open).
- **typeInfo mapping:** `family-type`→`familyType` via `{1: "FCAT_MYUNGJO", 2: "FCAT_GOTHIC"}`, default `"FCAT_GOTHIC"`; `weight`→`weight`, `proportion`→`proportion`, `contrast`→`contrast`, `stroke-variation`→`strokeVariation`, `arm-style`→`armStyle`, `letterform`→`letterform`, `midline`→`midline`, `x-height`→`xHeight`; drop `serif-style`.
- **typeInfo emitted on every `<hh:font>`** that has a `Panose1` (all do); it is an additive child — the existing font attributes (`id`/`face`/`type`/`isEmbedded`) are unchanged.
- **tab:** `<hp:tab width="0" leader="0" type="0"/>` as mixed content in `<hp:t>`; only the `tab` control carries attributes (`fwSpace`/`lineBreak` stay empty).
- **Test runner:** `.venv/bin/python -m pytest` — plain `python` lacks `hwp5proc` (~13 spurious failures). Current suite: 172 passing.
- **Validate on BOTH samples** (`samples/3.*.hwp` and `samples/4.*.hwp`).
- **Out of scope:** `substFont`, `subscript`, images/shapes.

---

### Task 1: Model dataclasses for PANOSE / typeInfo

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (`HwpPanose`, `HwpFont.panose`)
- Modify: `hwp2hwpx/owpml/model.py` (`TypeInfo`, `Font.type_info`)
- Test: `tests/test_model_typeinfo.py`

**Interfaces:**
- Produces: `HwpPanose(family_type:int=0, weight:int=0, proportion:int=0, contrast:int=0, stroke_variation:int=0, arm_style:int=0, letterform:int=0, midline:int=0, x_height:int=0)`; `HwpFont.panose=None`. `TypeInfo(family_type:str="FCAT_GOTHIC", weight:int=0, proportion:int=0, contrast:int=0, stroke_variation:int=0, arm_style:int=0, letterform:int=0, midline:int=0, x_height:int=0)`; `Font.type_info=None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_typeinfo.py
from hwp2hwpx.hwpmodel.model import HwpPanose, HwpFont
from hwp2hwpx.owpml.model import TypeInfo, Font


def test_hwp_panose_defaults():
    p = HwpPanose()
    assert (p.family_type, p.weight, p.proportion, p.contrast, p.stroke_variation,
            p.arm_style, p.letterform, p.midline, p.x_height) == (0,) * 9
    assert HwpFont(index=0, name="굴림").panose is None


def test_owpml_typeinfo_defaults():
    t = TypeInfo(family_type="FCAT_MYUNGJO", weight=6, x_height=1)
    assert t.family_type == "FCAT_MYUNGJO"
    assert t.weight == 6 and t.x_height == 1
    assert Font(id=0, face="굴림").type_info is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_typeinfo.py -v`
Expected: FAIL (ImportError on HwpPanose / TypeInfo)

- [ ] **Step 3: Add HWP-side model** in `hwp2hwpx/hwpmodel/model.py`

Add this dataclass immediately before `HwpFont`:

```python
@dataclass
class HwpPanose:
    family_type: int = 0
    weight: int = 0
    proportion: int = 0
    contrast: int = 0
    stroke_variation: int = 0
    arm_style: int = 0
    letterform: int = 0
    midline: int = 0
    x_height: int = 0
```

Change `HwpFont` to add `panose` (keep existing fields):

```python
@dataclass
class HwpFont:
    index: int
    name: str
    panose: "HwpPanose" = None
```

- [ ] **Step 4: Add OWPML-side model** in `hwp2hwpx/owpml/model.py`

Add this dataclass immediately before `Font`:

```python
@dataclass
class TypeInfo:
    family_type: str = "FCAT_GOTHIC"
    weight: int = 0
    proportion: int = 0
    contrast: int = 0
    stroke_variation: int = 0
    arm_style: int = 0
    letterform: int = 0
    midline: int = 0
    x_height: int = 0
```

Change `Font` to add `type_info` (keep existing fields):

```python
@dataclass
class Font:
    id: int
    face: str
    type: str = "TTF"
    is_embedded: bool = False
    type_info: "TypeInfo" = None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_typeinfo.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py tests/test_model_typeinfo.py
git commit -m "feat: HwpPanose/TypeInfo model dataclasses"
```

---

### Task 2: Reader parses Panose1 into HwpFont

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`
- Test: `tests/test_reader_panose.py`

**Interfaces:**
- Consumes: `HwpPanose`, `HwpFont` (Task 1), existing `_int`.
- Produces: `read_docinfo` sets `HwpFont.panose` from each `FaceName`'s `Panose1` child (None when absent).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader_panose.py
from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _fonts():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read()).fonts


def test_every_font_has_panose():
    fonts = _fonts()
    assert len(fonts) == 65
    assert all(f.panose is not None for f in fonts)


def test_panose_values_for_known_font():
    fonts = _fonts()
    # font 0 is 굴림체: Panose1 family-type=2, weight=6, x-height=1
    p = fonts[0].panose
    assert fonts[0].name == "굴림체"
    assert p.family_type == 2
    assert p.weight == 6
    assert p.x_height == 1
    assert p.stroke_variation == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reader_panose.py -v`
Expected: FAIL (panose is None)

- [ ] **Step 3: Add a Panose parse helper** in `hwp2hwpx/hwpmodel/reader.py`

Add `HwpPanose` to the existing `from .model import (...)` block.

Add this helper (near `_font_group_offsets`):

```python
def _parse_panose(face_el):
    p = face_el.find("Panose1")
    if p is None:
        return None
    return HwpPanose(
        family_type=_int(p.get("family-type")),
        weight=_int(p.get("weight")),
        proportion=_int(p.get("proportion")),
        contrast=_int(p.get("contrast")),
        stroke_variation=_int(p.get("stroke-variation")),
        arm_style=_int(p.get("arm-style")),
        letterform=_int(p.get("letterform")),
        midline=_int(p.get("midline")),
        x_height=_int(p.get("x-height")),
    )
```

- [ ] **Step 4: Populate `panose` in the FaceName loop**

Change the `fonts = [...]` list comprehension in `read_docinfo` to set `panose`:

```python
    fonts = [HwpFont(index=i, name=el.get("name") or "",
                     panose=_parse_panose(el))
             for i, el in enumerate(id_mappings.findall("FaceName"))]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_reader_panose.py tests/test_reader_docinfo.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_panose.py
git commit -m "feat: reader parses FaceName Panose1"
```

---

### Task 3: Mapper builds typeInfo + writer emits it

**Files:**
- Modify: `hwp2hwpx/mapper/fonts.py`
- Modify: `hwp2hwpx/owpml/header_writer.py`
- Test: `tests/test_mapper_fonts.py` (extend), `tests/test_header_typeinfo.py`

**Interfaces:**
- Consumes: `HwpFont.panose` (Task 1/2), `TypeInfo`/`Font` (Task 1).
- Produces: `map_fonts` sets `Font.type_info` from `panose` (family-type→FCAT string, others passthrough); `header_xml` emits a `<hh:typeInfo>` child on each `<hh:font>` that has `type_info`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_header_typeinfo.py
from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, Font, CharPr, ParaPr, TypeInfo
from hwp2hwpx.constants import NS


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def test_font_emits_typeinfo_child():
    header = Header(
        fonts_by_lang={"HANGUL": [Font(id=0, face="굴림",
            type_info=TypeInfo(family_type="FCAT_GOTHIC", weight=6, proportion=9,
                               contrast=0, stroke_variation=1, arm_style=1,
                               letterform=1, midline=1, x_height=1))]},
        char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)],
    )
    root = etree.fromstring(header_xml(header))
    font = next(root.iter(_hh("font")))
    assert font.get("face") == "굴림"          # existing attrs intact
    ti = font.find(_hh("typeInfo"))
    assert ti is not None
    assert ti.get("familyType") == "FCAT_GOTHIC"
    assert ti.get("weight") == "6"
    assert ti.get("proportion") == "9"
    assert ti.get("strokeVariation") == "1"
    assert ti.get("armStyle") == "1"
    assert ti.get("xHeight") == "1"


def test_font_without_typeinfo_emits_none():
    header = Header(fonts_by_lang={"HANGUL": [Font(id=0, face="굴림")]},
                    char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)])
    root = etree.fromstring(header_xml(header))
    font = next(root.iter(_hh("font")))
    assert font.find(_hh("typeInfo")) is None
```

```python
# tests/test_mapper_fonts_typeinfo.py
from hwp2hwpx.mapper.fonts import map_fonts
from hwp2hwpx.hwpmodel.model import HwpFont, HwpPanose


def _font(ft):
    return HwpFont(index=0, name="X",
                   panose=HwpPanose(family_type=ft, weight=6, x_height=1))


def test_family_type_mapping():
    assert map_fonts([_font(2)])["HANGUL"][0].type_info.family_type == "FCAT_GOTHIC"
    assert map_fonts([_font(1)])["HANGUL"][0].type_info.family_type == "FCAT_MYUNGJO"
    assert map_fonts([_font(99)])["HANGUL"][0].type_info.family_type == "FCAT_GOTHIC"


def test_type_info_fields_passthrough():
    ti = map_fonts([_font(2)])["HANGUL"][0].type_info
    assert ti.weight == 6
    assert ti.x_height == 1


def test_font_without_panose_has_no_type_info():
    out = map_fonts([HwpFont(index=0, name="X")])
    assert out["HANGUL"][0].type_info is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_header_typeinfo.py tests/test_mapper_fonts_typeinfo.py -v`
Expected: FAIL (no type_info; no typeInfo child)

- [ ] **Step 3: Build `type_info` in `hwp2hwpx/mapper/fonts.py`**

Replace the file contents with:

```python
"""Map HWP fonts to OWPML fontfaces."""
from ..owpml.model import Font, TypeInfo

# charPr/fontRef sets all 7 OWPML language attributes (hangul/latin/hanja/
# japanese/other/symbol/user). header_writer emits one <hh:fontface lang=...>
# bucket per key here, so every language must have a bucket or its fontRef
# dangles. We don't yet distinguish per-language fonts, so every bucket gets
# the same font list.
_LANGS = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]

# HWP Panose family-type -> OWPML typeInfo familyType. Best-effort heuristic;
# the fidelity harness scores by element count, so the string value does not
# affect the score.
_FAMILY_TYPE = {1: "FCAT_MYUNGJO", 2: "FCAT_GOTHIC"}


def _type_info(panose):
    if panose is None:
        return None
    return TypeInfo(
        family_type=_FAMILY_TYPE.get(panose.family_type, "FCAT_GOTHIC"),
        weight=panose.weight,
        proportion=panose.proportion,
        contrast=panose.contrast,
        stroke_variation=panose.stroke_variation,
        arm_style=panose.arm_style,
        letterform=panose.letterform,
        midline=panose.midline,
        x_height=panose.x_height,
    )


def map_fonts(hwp_fonts):
    fonts = [Font(id=f.index, face=f.name, type_info=_type_info(f.panose))
             for f in hwp_fonts]
    return {lang: list(fonts) for lang in _LANGS}
```

- [ ] **Step 4: Emit `<hh:typeInfo>` in `hwp2hwpx/owpml/header_writer.py`**

In the font loop, replace the `fe = etree.SubElement(...)` block (lines emitting id/face/type/isEmbedded) with a version that appends a `typeInfo` child:

```python
        for f in fonts:
            fe = etree.SubElement(ff, _hh("font"))
            fe.set("id", str(f.id))
            fe.set("face", f.face)
            fe.set("type", f.type)
            fe.set("isEmbedded", "1" if f.is_embedded else "0")
            if f.type_info is not None:
                ti = f.type_info
                te = etree.SubElement(fe, _hh("typeInfo"))
                te.set("familyType", ti.family_type)
                te.set("weight", str(ti.weight))
                te.set("proportion", str(ti.proportion))
                te.set("contrast", str(ti.contrast))
                te.set("strokeVariation", str(ti.stroke_variation))
                te.set("armStyle", str(ti.arm_style))
                te.set("letterform", str(ti.letterform))
                te.set("midline", str(ti.midline))
                te.set("xHeight", str(ti.x_height))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_header_typeinfo.py tests/test_mapper_fonts_typeinfo.py tests/test_mapper_fonts.py tests/test_header_writer.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/mapper/fonts.py hwp2hwpx/owpml/header_writer.py tests/test_header_typeinfo.py tests/test_mapper_fonts_typeinfo.py
git commit -m "feat: emit hh:typeInfo (font PANOSE) on each font"
```

---

### Task 4: Inline TAB → hp:tab

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py` (`_CONTROL_KIND`)
- Modify: `hwp2hwpx/owpml/section_writer.py` (`_write_run` control emit)
- Test: `tests/test_reader_tab.py`, `tests/test_section_writer_tab.py`

**Interfaces:**
- Consumes: `HwpControl`/`Control` (existing), the mixed-content run emitter.
- Produces: an inline `TAB` control char parses to `HwpControl("tab")`; the writer emits `<hp:tab width="0" leader="0" type="0"/>` inside `<hp:t>`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reader_tab.py
from hwp2hwpx.hwpmodel.reader import read_document
from hwp2hwpx.hwpmodel.model import HwpControl

SAMPLE2 = "samples/4.*.hwp"


def _all_controls():
    from hwp2hwpx.hwpmodel.reader import hwp5_xml
    doc = read_document(hwp5_xml(SAMPLE2))
    kinds = set()

    def walk(paras):
        for p in paras:
            for r in p.runs:
                for item in r.contents:
                    if isinstance(item, HwpControl):
                        kinds.add(item.kind)
                if r.table is not None:
                    for row in r.table.table_rows:
                        for cell in row.cells:
                            walk(cell.paragraphs)
    for sec in doc.sections:
        walk(sec.paragraphs)
    return kinds


def test_tab_control_parsed():
    assert "tab" in _all_controls()
```

```python
# tests/test_section_writer_tab.py
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text, Control
from hwp2hwpx.constants import NS


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _run_el(run):
    root = etree.fromstring(section_xml(Section(paras=[Para(id=0, para_pr_id=0, runs=[run])])))
    return next(root.iter(_hp("run")))


def test_tab_emits_hp_tab_with_attrs():
    r = _run_el(Run(char_pr_id=1, texts=[Text("가"), Control("tab"), Text("나")]))
    t = next(r.iter(_hp("t")))
    tab = t.find(_hp("tab"))
    assert tab is not None
    assert tab.get("width") == "0"
    assert tab.get("leader") == "0"
    assert tab.get("type") == "0"
    assert tab.tail == "나"


def test_fwspace_stays_empty():
    r = _run_el(Run(char_pr_id=1, texts=[Control("fwSpace")]))
    fw = next(r.iter(_hp("fwSpace")))
    assert fw.keys() == []  # no attributes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_reader_tab.py tests/test_section_writer_tab.py -v`
Expected: FAIL (tab not parsed; hp:tab has no attrs)

- [ ] **Step 3: Add `TAB` to the control map** in `hwp2hwpx/hwpmodel/reader.py`

Change `_CONTROL_KIND`:

```python
_CONTROL_KIND = {"FIXWIDTH_SPACE": "fwSpace", "LINE_BREAK": "lineBreak", "TAB": "tab"}
```

- [ ] **Step 4: Set tab attributes in the writer** in `hwp2hwpx/owpml/section_writer.py`

In `_write_run`, change the control branch (currently `last = etree.SubElement(te, _hp(item.kind))`) to:

```python
            if isinstance(item, Control):
                last = etree.SubElement(te, _hp(item.kind))
                if item.kind == "tab":
                    last.set("width", "0")
                    last.set("leader", "0")
                    last.set("type", "0")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reader_tab.py tests/test_section_writer_tab.py tests/test_section_writer_inline.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py hwp2hwpx/owpml/section_writer.py tests/test_reader_tab.py tests/test_section_writer_tab.py
git commit -m "feat: inline TAB control char -> hp:tab"
```

---

### Task 5: End-to-end / fidelity verification (both samples)

**Files:**
- Test: `tests/test_convert_tail.py`

**Interfaces:**
- Consumes: the full pipeline (`convert`) for both sample pairs.

- [ ] **Step 1: Write the fidelity/regression test**

```python
# tests/test_convert_tail.py
import zipfile
from hwp2hwpx.convert import convert

SAMPLE1 = "samples/3.*.hwp"
SAMPLE2 = "samples/4.*.hwp"


def _parts(tmp_path, src):
    out = tmp_path / "out.hwpx"
    convert(src, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return (z.read("Contents/header.xml").decode("utf-8"),
                z.read("Contents/section0.xml").decode("utf-8"))


def test_typeinfo_emitted_both_samples(tmp_path):
    for src in (SAMPLE1, SAMPLE2):
        hdr, _ = _parts(tmp_path, src)
        assert "<hh:typeInfo " in hdr
        # every font carries a typeInfo (one per <hh:font>)
        assert hdr.count("<hh:typeInfo ") == hdr.count("<hh:font ")


def test_tab_emitted_sample2(tmp_path):
    _, sec = _parts(tmp_path, SAMPLE2)
    assert "<hp:tab " in sec


def test_sample1_still_valid(tmp_path):
    hdr, sec = _parts(tmp_path, SAMPLE1)
    # typeInfo present on sample 1 too; linesegarray/tabs unaffected
    assert "<hh:typeInfo " in hdr
    assert sec.count("<hp:linesegarray") == 749
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_convert_tail.py -v`
Expected: PASS

- [ ] **Step 3: Run the full suite (regression)**

Run: `.venv/bin/python -m pytest -q`
Expected: all green (existing 172 + new tests)

- [ ] **Step 4: Measure fidelity on BOTH samples (informational)**

Run:
```bash
.venv/bin/python -c "
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import report
import tempfile, os
for h, x in [('samples/3.*.hwp','samples/3.*.hwpx'),
             ('samples/4.*.hwp','samples/4.*.hwpx')]:
    out = os.path.join(tempfile.mkdtemp(), 'out.hwpx')
    convert(h, out)
    print(h.split('/')[-1]); print(report(out, x)); print()
"
```
Expected: on both samples, `typeInfo` gone from the header miss list and `tab` gone from the section miss list; header and section match rise. Record the numbers in the commit message.

- [ ] **Step 5: Commit**

```bash
git add tests/test_convert_tail.py
git commit -m "test: end-to-end typeInfo + inline tab fidelity (both samples)"
```

---

## Self-Review

**Spec coverage:** models (Task 1), reader Panose (Task 2), mapper family-type mapping + writer typeInfo (Task 3), reader TAB kind + writer hp:tab (Task 4), both-sample fidelity (Task 5). substFont/subscript/images out of scope. Covered.

**Placeholder scan:** none — every code step contains full code.

**Type consistency:** `HwpPanose` (Task 1) produced by the reader (Task 2), consumed by `_type_info` (Task 3); `TypeInfo` (Task 1) produced by the mapper (Task 3), consumed by the writer (Task 3). `Font.type_info`/`HwpFont.panose` threaded through. TAB reuses `HwpControl`/`Control` (`kind="tab"`) already flowing through `_map_contents` (section-inline milestone) — no model change. Writer attribute names (`familyType`/`strokeVariation`/`armStyle`/`xHeight`; `width`/`leader`/`type`) match the OWPML target.
