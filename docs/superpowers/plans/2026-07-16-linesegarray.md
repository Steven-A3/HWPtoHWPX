# linesegarray (per-line layout) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `<hp:linesegarray>` (one per paragraph) with `<hp:lineseg>` (one per HWP `LineSeg`), raising section0.xml from 73.1% toward ~99%.

**Architecture:** Extend the existing 4 layers. `HwpLineSeg`/`LineSeg` dataclasses; the reader captures each paragraph's `LineSeg` geometry; the mapper passes them through; `_write_paragraph` emits `<hp:linesegarray>` after the runs.

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc xml`), pytest.

## Global Constraints

- **Python 3.9 floor:** NO PEP 604 `X | None` union syntax. Use bare `field: T = None` / `field(default_factory=list)`.
- **LineSeg attribute mapping (HWP → OWPML, done in the reader):** `chpos`→`text_pos`, `y`→`vert_pos`, `height`→`vert_size`, `height-text`→`text_height`, `height-baseline`→`baseline`, `space-below`→`spacing`, `x`→`horz_pos`, `width`→`horz_size`, `lineseg-flags` (hex string) → `flags` = `int(value, 16)` with fallback 0.
- **Writer attribute names:** `<hp:lineseg textpos vertpos vertsize textheight baseline spacing horzpos horzsize flags/>`.
- **`<hp:linesegarray>` is emitted after all `<hp:run>` children, only when the paragraph has ≥1 line seg.** Applies to body and cell paragraphs (same `_write_paragraph`).
- **Counts to hit:** section0 `linesegarray`==749, `lineseg`==922 (match Hancom exactly).
- **Test runner:** `.venv/bin/python -m pytest` — plain `python` lacks `hwp5proc` (~13 spurious failures). Current suite: 159 passing.
- **Out of scope:** `<hp:ctrl>`, `pageBorderFill`, `autoNumFormat`.

---

### Task 1: Model dataclasses for line segments

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (`HwpLineSeg`, `HwpParagraph.line_segs`)
- Modify: `hwp2hwpx/owpml/model.py` (`LineSeg`, `Para.line_segs`)
- Test: `tests/test_model_lineseg.py`

**Interfaces:**
- Produces: `HwpLineSeg(text_pos:int=0, vert_pos:int=0, vert_size:int=0, text_height:int=0, baseline:int=0, spacing:int=0, horz_pos:int=0, horz_size:int=0, flags:int=0)`; `HwpParagraph.line_segs:list`. `LineSeg(...)` with the same 9 fields; `Para.line_segs:list`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_lineseg.py
from hwp2hwpx.hwpmodel.model import HwpLineSeg, HwpParagraph
from hwp2hwpx.owpml.model import LineSeg, Para


def test_hwp_lineseg_defaults():
    ls = HwpLineSeg()
    assert (ls.text_pos, ls.vert_pos, ls.vert_size, ls.text_height, ls.baseline,
            ls.spacing, ls.horz_pos, ls.horz_size, ls.flags) == (0,) * 9


def test_hwp_paragraph_line_segs_default():
    assert HwpParagraph(para_shape_id=0).line_segs == []


def test_owpml_lineseg_and_para():
    ls = LineSeg(text_pos=1, vert_pos=2, vert_size=3, text_height=4, baseline=5,
                 spacing=6, horz_pos=7, horz_size=8, flags=9)
    assert ls.horz_size == 8 and ls.flags == 9
    assert Para(id=0, para_pr_id=0).line_segs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_lineseg.py -v`
Expected: FAIL (ImportError on HwpLineSeg / LineSeg)

- [ ] **Step 3: Add HWP-side model** in `hwp2hwpx/hwpmodel/model.py`

Add this dataclass immediately after `HwpControl` (or before `HwpParagraph`):

```python
@dataclass
class HwpLineSeg:
    text_pos: int = 0
    vert_pos: int = 0
    vert_size: int = 0
    text_height: int = 0
    baseline: int = 0
    spacing: int = 0
    horz_pos: int = 0
    horz_size: int = 0
    flags: int = 0
```

Add `line_segs` to `HwpParagraph` (keep existing fields):

```python
@dataclass
class HwpParagraph:
    para_shape_id: int
    style_id: int = 0
    runs: list = field(default_factory=list)
    line_segs: list = field(default_factory=list)
```

- [ ] **Step 4: Add OWPML-side model** in `hwp2hwpx/owpml/model.py`

Add this dataclass immediately after `Text` / `Control` (before `Run`):

```python
@dataclass
class LineSeg:
    text_pos: int = 0
    vert_pos: int = 0
    vert_size: int = 0
    text_height: int = 0
    baseline: int = 0
    spacing: int = 0
    horz_pos: int = 0
    horz_size: int = 0
    flags: int = 0
```

Add `line_segs` to `Para` (keep existing fields):

```python
@dataclass
class Para:
    id: int
    para_pr_id: int
    style_id: int = 0
    runs: list = field(default_factory=list)
    line_segs: list = field(default_factory=list)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_lineseg.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py tests/test_model_lineseg.py
git commit -m "feat: HwpLineSeg/LineSeg model dataclasses"
```

---

### Task 2: Reader captures per-paragraph LineSeg geometry

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py` (`parse_paragraph`)
- Test: `tests/test_reader_lineseg.py`

**Interfaces:**
- Consumes: `HwpLineSeg` (Task 1), existing `_int`.
- Produces: `parse_paragraph` sets `HwpParagraph.line_segs` from `para_el.findall("LineSeg")`, mapping HWP attrs to `HwpLineSeg` fields; `flags = int(lineseg-flags, 16)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader_lineseg.py
from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _paras():
    with open(FIXTURE, "rb") as f:
        doc = read_document(f.read())
    # include cell paragraphs
    out = []

    def walk(paras):
        for p in paras:
            out.append(p)
            for r in p.runs:
                if r.table is not None:
                    for row in r.table.table_rows:
                        for cell in row.cells:
                            walk(cell.paragraphs)
    for sec in doc.sections:
        walk(sec.paragraphs)
    return out


def test_every_paragraph_has_line_segs():
    paras = _paras()
    assert len(paras) == 749
    assert all(len(p.line_segs) >= 1 for p in paras)
    assert sum(len(p.line_segs) for p in paras) == 922


def test_lineseg_flags_hex_to_decimal():
    # first paragraph, first line seg: lineseg-flags="00060000" -> 393216
    paras = _paras()
    first = paras[0].line_segs[0]
    assert first.flags == int("00060000", 16) == 393216


def test_lineseg_geometry_fields_are_ints():
    ls = _paras()[0].line_segs[0]
    for v in (ls.text_pos, ls.vert_pos, ls.vert_size, ls.text_height,
              ls.baseline, ls.spacing, ls.horz_pos, ls.horz_size):
        assert isinstance(v, int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reader_lineseg.py -v`
Expected: FAIL (line_segs empty)

- [ ] **Step 3: Add a LineSeg parse helper** in `hwp2hwpx/hwpmodel/reader.py`

Add `HwpLineSeg` to the existing `from .model import (...)` block.

Add this helper just above `parse_paragraph`:

```python
def _hex_int(v):
    try:
        return int(v, 16)
    except (TypeError, ValueError):
        return 0


def _parse_line_segs(para_el):
    out = []
    for el in para_el.findall("LineSeg"):
        out.append(HwpLineSeg(
            text_pos=_int(el.get("chpos")),
            vert_pos=_int(el.get("y")),
            vert_size=_int(el.get("height")),
            text_height=_int(el.get("height-text")),
            baseline=_int(el.get("height-baseline")),
            spacing=_int(el.get("space-below")),
            horz_pos=_int(el.get("x")),
            horz_size=_int(el.get("width")),
            flags=_hex_int(el.get("lineseg-flags")),
        ))
    return out
```

- [ ] **Step 4: Set `line_segs` in `parse_paragraph`'s return**

Change the `return HwpParagraph(...)` at the end of `parse_paragraph` to:

```python
    return HwpParagraph(
        para_shape_id=_int(para_el.get("parashape-id")),
        style_id=_int(para_el.get("style-id")),
        runs=runs,
        line_segs=_parse_line_segs(para_el),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_reader_lineseg.py tests/test_reader_body.py tests/test_reader_inline.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_lineseg.py
git commit -m "feat: reader captures per-paragraph LineSeg geometry"
```

---

### Task 3: Mapper passes line segs through

**Files:**
- Modify: `hwp2hwpx/mapper/body.py` (`map_paragraph`)
- Test: `tests/test_mapper_lineseg.py`

**Interfaces:**
- Consumes: `HwpLineSeg` (Task 1/2), `LineSeg` (Task 1).
- Produces: `map_paragraph` sets `Para.line_segs = [LineSeg(...) for each HwpLineSeg]` (field-for-field).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mapper_lineseg.py
from hwp2hwpx.mapper.body import map_paragraph
from hwp2hwpx.hwpmodel.model import HwpParagraph, HwpLineSeg


def test_line_segs_mapped_field_for_field():
    hpar = HwpParagraph(para_shape_id=0, style_id=0, runs=[], line_segs=[
        HwpLineSeg(text_pos=0, vert_pos=10, vert_size=1800, text_height=1800,
                   baseline=1530, spacing=1080, horz_pos=0, horz_size=35816,
                   flags=393216),
    ])
    para = map_paragraph(hpar, 0)
    assert len(para.line_segs) == 1
    ls = para.line_segs[0]
    assert ls.vert_pos == 10
    assert ls.horz_size == 35816
    assert ls.flags == 393216
    assert ls.baseline == 1530


def test_no_line_segs_maps_to_empty():
    para = map_paragraph(HwpParagraph(para_shape_id=0), 0)
    assert para.line_segs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mapper_lineseg.py -v`
Expected: FAIL (Para.line_segs empty)

- [ ] **Step 3: Map line segs** in `hwp2hwpx/mapper/body.py`

Add `LineSeg` to the owpml-model import line (currently `OwpmlDocument, Header, Section, Para, Run, Text, Metadata, Control`), i.e. add `LineSeg`.

Add a helper above `map_paragraph`:

```python
def _map_line_segs(line_segs):
    return [LineSeg(
        text_pos=ls.text_pos, vert_pos=ls.vert_pos, vert_size=ls.vert_size,
        text_height=ls.text_height, baseline=ls.baseline, spacing=ls.spacing,
        horz_pos=ls.horz_pos, horz_size=ls.horz_size, flags=ls.flags,
    ) for ls in line_segs]
```

Change the `return Para(...)` in `map_paragraph` to include `line_segs`:

```python
    return Para(id=para_id, para_pr_id=hpar.para_shape_id,
                style_id=hpar.style_id, runs=runs,
                line_segs=_map_line_segs(hpar.line_segs))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_mapper_lineseg.py tests/test_mapper_body.py tests/test_mapper_inline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/body.py tests/test_mapper_lineseg.py
git commit -m "feat: mapper passes line segs to Para"
```

---

### Task 4: Writer emits linesegarray

**Files:**
- Modify: `hwp2hwpx/owpml/section_writer.py` (`_write_paragraph`)
- Test: `tests/test_section_writer_lineseg.py`

**Interfaces:**
- Consumes: `Para.line_segs` (list of `LineSeg`), existing `_hp`.
- Produces: `<hp:linesegarray>` after the runs (only when `para.line_segs` non-empty), one `<hp:lineseg>` per entry with 9 attributes.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_section_writer_lineseg.py
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text, LineSeg
from hwp2hwpx.constants import NS


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _p_el(para):
    root = etree.fromstring(section_xml(Section(paras=[para])))
    return next(root.iter(_hp("p")))


def test_linesegarray_after_runs_with_attrs():
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=1, texts=[Text("가")])],
                line_segs=[LineSeg(text_pos=0, vert_pos=10, vert_size=1800,
                                   text_height=1800, baseline=1530, spacing=1080,
                                   horz_pos=0, horz_size=35816, flags=393216)])
    p = _p_el(para)
    children = [etree.QName(c).localname for c in p]
    assert children == ["run", "linesegarray"]  # linesegarray follows the run
    lsa = p.find(_hp("linesegarray"))
    segs = lsa.findall(_hp("lineseg"))
    assert len(segs) == 1
    s = segs[0]
    assert s.get("textpos") == "0"
    assert s.get("vertpos") == "10"
    assert s.get("vertsize") == "1800"
    assert s.get("textheight") == "1800"
    assert s.get("baseline") == "1530"
    assert s.get("spacing") == "1080"
    assert s.get("horzpos") == "0"
    assert s.get("horzsize") == "35816"
    assert s.get("flags") == "393216"


def test_multiple_line_segs():
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[])],
                line_segs=[LineSeg(vert_pos=0), LineSeg(vert_pos=1800)])
    p = _p_el(para)
    segs = list(p.iter(_hp("lineseg")))
    assert [s.get("vertpos") for s in segs] == ["0", "1800"]


def test_no_linesegarray_when_empty():
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[])], line_segs=[])
    p = _p_el(para)
    assert p.find(_hp("linesegarray")) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_section_writer_lineseg.py -v`
Expected: FAIL (no linesegarray emitted)

- [ ] **Step 3: Emit linesegarray** in `hwp2hwpx/owpml/section_writer.py`

In `_write_paragraph`, after the `for run in para.runs: _write_run(...)` loop and before the function returns, add:

```python
    if para.line_segs:
        lsa = etree.SubElement(p, _hp("linesegarray"))
        for ls in para.line_segs:
            seg = etree.SubElement(lsa, _hp("lineseg"))
            seg.set("textpos", str(ls.text_pos))
            seg.set("vertpos", str(ls.vert_pos))
            seg.set("vertsize", str(ls.vert_size))
            seg.set("textheight", str(ls.text_height))
            seg.set("baseline", str(ls.baseline))
            seg.set("spacing", str(ls.spacing))
            seg.set("horzpos", str(ls.horz_pos))
            seg.set("horzsize", str(ls.horz_size))
            seg.set("flags", str(ls.flags))
```

(The exact insertion point: `_write_paragraph` currently ends with the `for run in para.runs:` loop; append this block right after that loop, inside the function.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_section_writer_lineseg.py tests/test_section_writer.py tests/test_section_writer_inline.py tests/test_section_writer_tables.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py tests/test_section_writer_lineseg.py
git commit -m "feat: emit hp:linesegarray after runs in each paragraph"
```

---

### Task 5: End-to-end / fidelity verification

**Files:**
- Test: `tests/test_convert_lineseg.py`

**Interfaces:**
- Consumes: the full pipeline (`convert`) and the fidelity harness.

- [ ] **Step 1: Write the fidelity/regression test**

```python
# tests/test_convert_lineseg.py
import zipfile
from hwp2hwpx.convert import convert

SAMPLE_HWP = "samples/3.*.hwp"


def _section(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def test_linesegarray_and_lineseg_counts_match_hancom(tmp_path):
    sec = _section(tmp_path)
    assert sec.count("<hp:linesegarray") == 749
    # trailing space so "<hp:lineseg " does not also match "<hp:linesegarray"
    assert sec.count("<hp:lineseg ") == 922


def test_linesegarray_is_child_of_p(tmp_path):
    from lxml import etree
    from hwp2hwpx.constants import NS
    sec = _section(tmp_path).encode("utf-8")
    root = etree.fromstring(sec)
    hp = "{%s}" % NS["hp"]
    # every linesegarray's parent is an hp:p
    for lsa in root.iter(hp + "linesegarray"):
        assert etree.QName(lsa.getparent()).localname == "p"
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_convert_lineseg.py -v`
Expected: PASS

- [ ] **Step 3: Run the full suite (regression)**

Run: `.venv/bin/python -m pytest -q`
Expected: all green (existing 159 + new tests)

- [ ] **Step 4: Measure fidelity gain (informational)**

Run:
```bash
.venv/bin/python -c "
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import report
import tempfile, os
out = os.path.join(tempfile.mkdtemp(), 'out.hwpx')
convert('samples/3.*.hwp', out)
print(report(out, 'samples/3.*.hwpx'))
"
```
Expected: `section0.xml` match ~99%; `lineseg`/`linesegarray` gone from the section miss list. Record the number in the commit message.

- [ ] **Step 5: Commit**

```bash
git add tests/test_convert_lineseg.py
git commit -m "test: end-to-end linesegarray fidelity (749/922 counts)"
```

---

## Self-Review

**Spec coverage:** models (Task 1), reader capture + flags hex→decimal (Task 2), mapper passthrough (Task 3), writer linesegarray-after-runs + empty guard (Task 4), fidelity counts 749/922 + parent-is-p (Task 5). ctrl/pageBorderFill/autoNumFormat out of scope. Covered.

**Placeholder scan:** none — every code step contains full code.

**Type consistency:** `HwpLineSeg` (Task 1) produced by the reader (Task 2), consumed by `_map_line_segs` (Task 3); `LineSeg` (Task 1) produced by the mapper (Task 3), consumed by the writer (Task 4). `HwpParagraph.line_segs`/`Para.line_segs` threaded through. Field names (`text_pos`/`vert_pos`/`vert_size`/`text_height`/`baseline`/`spacing`/`horz_pos`/`horz_size`/`flags`) identical across both models, reader, mapper, writer. Writer attribute names (`textpos`/`vertpos`/…) match the OWPML target. `map_paragraph` signature unchanged `(hpar, para_id)`.
