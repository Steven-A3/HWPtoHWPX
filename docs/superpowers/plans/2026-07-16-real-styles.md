# Real Named Styles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit the document's real named styles in `header.xml` (replacing the single placeholder style id 0) and have paragraphs reference their real style id, raising header.xml fidelity from 87.4%.

**Architecture:** Extend the existing 4 layers (Reader → HWP model → Mapper → OWPML model → Writer). New `HwpStyle`/`Style` dataclasses; the reader parses `IdMappings/Style` and clamps paragraph `style_id` + style refs against known counts; a new `mapper/style.py` applies the transform; `header_writer` emits the full `<hh:styles>` block.

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc xml`), pytest.

## Global Constraints

- **Python 3.9 floor:** NO PEP 604 `X | None` union syntax. Use bare `field: T = None` / `field(default_factory=list)`.
- **Style transform (verified):** `id`=positional index; `kind="paragraph"`→`type="PARA"`, `kind` starting `"char"`→`type="CHAR"`, else `PARA`; **`local-name`→`name`** and **`name`→`engName`** (the two swap); `parashape-id`→`paraPrIDRef`; `charshape-id`→`charPrIDRef`; `next-style-id`→`nextStyleIDRef`; `lang-id`→`langID`; `lockForm="0"` constant.
- **No dangling refs:** clamp `paraPrIDRef`∈[0,paraCount-1], `charPrIDRef`∈[0,charCount-1], `nextStyleIDRef`∈[0,styleCount-1], paragraph `styleIDRef`∈[0,styleCount-1]; missing/out-of-range → 0 (or last valid).
- **Empty-styles fallback:** if the document has no `Style` elements, still emit a single default `<hh:style id="0">` so `styleIDRef="0"` resolves.
- **Test runner:** `.venv/bin/python -m pytest` — plain `python` lacks the `hwp5proc` binary and yields ~13 spurious failures. Under `.venv/bin/python` the current suite is 109 passing.
- **Out of scope:** `typeInfo`/`substFont` (font metadata inside `<hh:font>`); outline numbering.

---

### Task 1: Model dataclasses for styles

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (add `HwpStyle`, add `styles` to `HwpDocInfo`)
- Modify: `hwp2hwpx/owpml/model.py` (add `Style`, add `styles` to `Header`)
- Test: `tests/test_model_styles.py`

**Interfaces:**
- Produces: `HwpStyle(index:int, kind:str="paragraph", local_name:str="", eng_name:str="", para_shape_id:int=0, char_shape_id:int=0, next_style_id:int=0, lang_id:int=1042)`; `HwpDocInfo.styles: list`. `Style(id:int, type:str="PARA", name:str="", eng_name:str="", para_pr_id:int=0, char_pr_id:int=0, next_style_id:int=0, lang_id:int=1042, lock_form:str="0")`; `Header.styles: list`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_styles.py
from hwp2hwpx.hwpmodel.model import HwpStyle, HwpDocInfo
from hwp2hwpx.owpml.model import Style, Header


def test_hwp_style_defaults():
    s = HwpStyle(index=0)
    assert s.kind == "paragraph"
    assert s.local_name == ""
    assert s.eng_name == ""
    assert s.para_shape_id == 0
    assert s.char_shape_id == 0
    assert s.next_style_id == 0
    assert s.lang_id == 1042


def test_docinfo_has_styles_list():
    assert HwpDocInfo().styles == []


def test_owpml_style_defaults():
    s = Style(id=0)
    assert s.type == "PARA"
    assert s.name == ""
    assert s.eng_name == ""
    assert s.para_pr_id == 0
    assert s.char_pr_id == 0
    assert s.next_style_id == 0
    assert s.lang_id == 1042
    assert s.lock_form == "0"


def test_header_has_styles_list():
    assert Header().styles == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_styles.py -v`
Expected: FAIL (ImportError on HwpStyle / Style)

- [ ] **Step 3: Add `HwpStyle` and `HwpDocInfo.styles`** in `hwp2hwpx/hwpmodel/model.py`

Add this dataclass immediately after `HwpParaShape`:

```python
@dataclass
class HwpStyle:
    index: int
    kind: str = "paragraph"
    local_name: str = ""
    eng_name: str = ""
    para_shape_id: int = 0
    char_shape_id: int = 0
    next_style_id: int = 0
    lang_id: int = 1042
```

Change the `HwpDocInfo` dataclass to add a `styles` field (keep existing fields):

```python
@dataclass
class HwpDocInfo:
    fonts: list = field(default_factory=list)
    char_shapes: list = field(default_factory=list)
    para_shapes: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
    styles: list = field(default_factory=list)
```

- [ ] **Step 4: Add `Style` and `Header.styles`** in `hwp2hwpx/owpml/model.py`

Add this dataclass immediately after `ParaPr`:

```python
@dataclass
class Style:
    id: int
    type: str = "PARA"
    name: str = ""
    eng_name: str = ""
    para_pr_id: int = 0
    char_pr_id: int = 0
    next_style_id: int = 0
    lang_id: int = 1042
    lock_form: str = "0"
```

Change the `Header` dataclass to add a `styles` field (keep existing fields):

```python
@dataclass
class Header:
    fonts_by_lang: dict = field(default_factory=dict)
    char_prs: list = field(default_factory=list)
    para_prs: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
    styles: list = field(default_factory=list)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_styles.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py tests/test_model_styles.py
git commit -m "feat: HwpStyle/Style model dataclasses"
```

---

### Task 2: Reader parses styles and clamps refs

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`
- Test: `tests/test_reader_styles.py`

**Interfaces:**
- Consumes: `HwpStyle` (Task 1), existing `_int`, `read_docinfo`, `read_document`.
- Produces: `read_docinfo` fills `HwpDocInfo.styles` from `IdMappings/Style`. `read_document` clamps each paragraph's `style_id` into `[0, styleCount-1]` and each style's `para_shape_id`/`char_shape_id`/`next_style_id` into range.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader_styles.py
from hwp2hwpx.hwpmodel.reader import read_docinfo, read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _bytes():
    with open(FIXTURE, "rb") as f:
        return f.read()


def test_styles_parsed():
    di = read_docinfo(_bytes())
    assert len(di.styles) == 63
    s0 = di.styles[0]
    assert s0.local_name == "바탕글"
    assert s0.eng_name == "Normal"
    assert s0.char_shape_id == 17
    assert s0.para_shape_id == 3
    assert s0.kind == "paragraph"


def test_style_refs_in_range():
    di = read_docinfo(_bytes())
    n_char = len(di.char_shapes)
    n_para = len(di.para_shapes)
    n_style = len(di.styles)
    for s in di.styles:
        assert 0 <= s.char_shape_id < n_char
        assert 0 <= s.para_shape_id < n_para
        assert 0 <= s.next_style_id < n_style


def test_paragraph_style_ids_in_range():
    doc = read_document(_bytes())
    n_style = len(doc.docinfo.styles)
    seen = []
    for sec in doc.sections:
        for p in sec.paragraphs:
            assert 0 <= p.style_id < n_style
            seen.append(p.style_id)
    # real (non-placeholder) style ids flow through: not everything is 0
    assert any(sid != 0 for sid in seen)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reader_styles.py -v`
Expected: FAIL (di.styles empty)

- [ ] **Step 3: Import `HwpStyle` and add a parse helper** in `hwp2hwpx/hwpmodel/reader.py`

Add `HwpStyle` to the existing `from .model import (...)` block.

Add this helper after `_parse_border_fills`:

```python
def _parse_styles(id_mappings):
    out = []
    for i, el in enumerate(id_mappings.findall("Style")):
        out.append(HwpStyle(
            index=i,
            kind=(el.get("kind") or "paragraph").lower(),
            local_name=el.get("local-name") or "",
            eng_name=el.get("name") or "",
            para_shape_id=_int(el.get("parashape-id")),
            char_shape_id=_int(el.get("charshape-id")),
            next_style_id=_int(el.get("next-style-id")),
            lang_id=_int(el.get("lang-id"), 1042),
        ))
    return out
```

- [ ] **Step 4: Populate `styles` in `read_docinfo`**

In `read_docinfo`, change the final `return HwpDocInfo(...)` to include styles:

```python
    return HwpDocInfo(fonts=fonts, char_shapes=char_shapes,
                      para_shapes=para_shapes,
                      border_fills=_parse_border_fills(id_mappings),
                      styles=_parse_styles(id_mappings))
```

- [ ] **Step 5: Add clamp helpers and wire them into `read_document`**

Add these helpers after `_clamp_para_shape_border_fill_ids`:

```python
def _clamp_index(n, count):
    """Clamp a 0-based ref into [0, count-1]; empty target -> 0."""
    if count <= 0:
        return 0
    if n < 0:
        return 0
    if n >= count:
        return count - 1
    return n


def _clamp_style_refs(styles, char_count, para_count):
    """Style paraPrIDRef/charPrIDRef/nextStyleIDRef must resolve or they
    dangle in header.xml. Clamp against the known definition counts."""
    style_count = len(styles)
    for s in styles:
        s.char_shape_id = _clamp_index(s.char_shape_id, char_count)
        s.para_shape_id = _clamp_index(s.para_shape_id, para_count)
        s.next_style_id = _clamp_index(s.next_style_id, style_count)


def _clamp_paragraph_style_ids(sections, style_count):
    """Every paragraph styleIDRef must resolve to an emitted <hh:style>."""
    def _walk(paragraphs):
        for para in paragraphs:
            para.style_id = _clamp_index(para.style_id, style_count)
            for run in para.runs:
                if run.table is not None:
                    for row in run.table.table_rows:
                        for cell in row.cells:
                            _walk(cell.paragraphs)
    for sec in sections:
        _walk(sec.paragraphs)
```

In `read_document`, after the existing `_clamp_para_shape_border_fill_ids(...)` line and before `return HwpDocument(...)`, add:

```python
    _clamp_style_refs(docinfo.styles, len(docinfo.char_shapes),
                      len(docinfo.para_shapes))
    _clamp_paragraph_style_ids(sections, len(docinfo.styles))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_reader_styles.py tests/test_reader_docinfo.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_styles.py
git commit -m "feat: parse HWP styles + clamp style/paragraph refs"
```

---

### Task 3: Style mapper + real paragraph style id

**Files:**
- Create: `hwp2hwpx/mapper/style.py`
- Modify: `hwp2hwpx/mapper/body.py`
- Test: `tests/test_mapper_styles.py`

**Interfaces:**
- Consumes: `HwpStyle` (Task 1/2), `Style` (Task 1).
- Produces: `map_styles(list[HwpStyle]) -> list[Style]`. `map_document` sets `Header.styles = map_styles(di.styles)`; `map_paragraph` sets `style_id=hpar.style_id` (real, already clamped by the reader).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mapper_styles.py
from hwp2hwpx.mapper.style import map_styles
from hwp2hwpx.mapper.body import map_paragraph
from hwp2hwpx.hwpmodel.model import HwpStyle, HwpParagraph, HwpRun


def test_map_style_transform():
    src = [HwpStyle(index=0, kind="paragraph", local_name="바탕글", eng_name="Normal",
                    para_shape_id=3, char_shape_id=17, next_style_id=0, lang_id=1042)]
    out = map_styles(src)
    s = out[0]
    assert s.id == 0
    assert s.type == "PARA"
    assert s.name == "바탕글"
    assert s.eng_name == "Normal"
    assert s.para_pr_id == 3
    assert s.char_pr_id == 17
    assert s.next_style_id == 0
    assert s.lang_id == 1042
    assert s.lock_form == "0"


def test_map_style_char_kind():
    out = map_styles([HwpStyle(index=1, kind="char")])
    assert out[0].type == "CHAR"


def test_map_preserves_order_and_count():
    src = [HwpStyle(index=0, local_name="A"), HwpStyle(index=1, local_name="B")]
    out = map_styles(src)
    assert [s.id for s in out] == [0, 1]
    assert [s.name for s in out] == ["A", "B"]


def test_map_paragraph_uses_real_style_id():
    hpar = HwpParagraph(para_shape_id=2, style_id=5,
                        runs=[HwpRun(char_shape_id=0, text="x")])
    para = map_paragraph(hpar, 0)
    assert para.style_id == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mapper_styles.py -v`
Expected: FAIL (no module `mapper.style`; map_paragraph returns style_id 0)

- [ ] **Step 3: Create `hwp2hwpx/mapper/style.py`**

```python
"""Map HWP styles to OWPML styles."""
from ..owpml.model import Style


def _type(kind):
    return "CHAR" if (kind or "").lower().startswith("char") else "PARA"


def map_styles(styles):
    out = []
    for s in styles:
        out.append(Style(
            id=s.index,
            type=_type(s.kind),
            name=s.local_name,
            eng_name=s.eng_name,
            para_pr_id=s.para_shape_id,
            char_pr_id=s.char_shape_id,
            next_style_id=s.next_style_id,
            lang_id=s.lang_id,
            lock_form="0",
        ))
    return out
```

- [ ] **Step 4: Wire styles + real style id into `hwp2hwpx/mapper/body.py`**

Add the import near the other mapper imports:

```python
from .style import map_styles
```

In `map_paragraph`, change the final return to use the real style id:

```python
    return Para(id=para_id, para_pr_id=hpar.para_shape_id,
                style_id=hpar.style_id, runs=runs)
```

(Delete the `# style_id clamped to 0` comment above it.)

In `map_document`, add `styles=` to the `Header(...)` construction:

```python
    header = Header(
        fonts_by_lang=map_fonts(di.fonts),
        char_prs=map_char_shapes(di.char_shapes),
        para_prs=map_para_shapes(di.para_shapes),
        border_fills=map_border_fills(di.border_fills),
        styles=map_styles(di.styles),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_mapper_styles.py tests/test_mapper_body.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/mapper/style.py hwp2hwpx/mapper/body.py tests/test_mapper_styles.py
git commit -m "feat: map HWP styles + emit real paragraph styleIDRef"
```

---

### Task 4: Writer emits real styles block

**Files:**
- Modify: `hwp2hwpx/owpml/header_writer.py` (the default-style block near the end)
- Test: `tests/test_header_styles.py`

**Interfaces:**
- Consumes: `Header.styles` (list of `Style`), existing `_hh`.
- Produces: `<hh:styles itemCnt=N>` with one `<hh:style>` per entry carrying `id type name engName paraPrIDRef charPrIDRef nextStyleIDRef langID lockForm`. Empty `Header.styles` → single default `<hh:style id="0">` (current behavior).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_header_styles.py
from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, Font, CharPr, ParaPr, Style
from hwp2hwpx.constants import NS


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def test_header_emits_real_styles():
    header = Header(
        char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)],
        styles=[
            Style(id=0, type="PARA", name="바탕글", eng_name="Normal",
                  para_pr_id=3, char_pr_id=17, next_style_id=0, lang_id=1042),
            Style(id=1, type="PARA", name="본문", eng_name="",
                  para_pr_id=31, char_pr_id=38, next_style_id=1),
        ],
    )
    root = etree.fromstring(header_xml(header))
    styles_el = next(root.iter(_hh("styles")))
    assert styles_el.get("itemCnt") == "2"
    st = list(root.iter(_hh("style")))
    assert st[0].get("name") == "바탕글"
    assert st[0].get("engName") == "Normal"
    assert st[0].get("type") == "PARA"
    assert st[0].get("paraPrIDRef") == "3"
    assert st[0].get("charPrIDRef") == "17"
    assert st[0].get("nextStyleIDRef") == "0"
    assert st[0].get("langID") == "1042"
    assert st[0].get("lockForm") == "0"
    assert st[1].get("name") == "본문"


def test_header_empty_styles_falls_back_to_default():
    header = Header(char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)])
    root = etree.fromstring(header_xml(header))
    st = list(root.iter(_hh("style")))
    assert len(st) == 1
    assert st[0].get("id") == "0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_header_styles.py -v`
Expected: FAIL (only default style emitted; no name/engName attrs)

- [ ] **Step 3: Replace the default-style block** in `hwp2hwpx/owpml/header_writer.py`

Replace the existing block (the comment + `styles_el`/`style_el` default emission near the end, before `return XML_DECL + ...`) with:

```python
    styles_el = etree.SubElement(ref, _hh("styles"))
    if header.styles:
        styles_el.set("itemCnt", str(len(header.styles)))
        for s in header.styles:
            se = etree.SubElement(styles_el, _hh("style"))
            se.set("id", str(s.id))
            se.set("type", s.type)
            se.set("name", s.name)
            se.set("engName", s.eng_name)
            se.set("paraPrIDRef", str(s.para_pr_id))
            se.set("charPrIDRef", str(s.char_pr_id))
            se.set("nextStyleIDRef", str(s.next_style_id))
            se.set("langID", str(s.lang_id))
            se.set("lockForm", s.lock_form)
    else:
        # No styles in the document: emit a single default so every
        # paragraph's styleIDRef="0" resolves instead of dangling.
        styles_el.set("itemCnt", "1")
        style_el = etree.SubElement(styles_el, _hh("style"))
        style_el.set("id", "0")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_header_styles.py tests/test_header_writer.py -v`
Expected: PASS (new + existing header tests, including the default-style test)

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/header_writer.py tests/test_header_styles.py
git commit -m "feat: emit real hh:styles block (fallback default when empty)"
```

---

### Task 5: End-to-end / fidelity verification

**Files:**
- Test: `tests/test_convert_styles.py`

**Interfaces:**
- Consumes: the full pipeline (`convert`) and the fidelity harness.

- [ ] **Step 1: Write the fidelity/regression test**

```python
# tests/test_convert_styles.py
import zipfile
import re
from hwp2hwpx.convert import convert

SAMPLE_HWP = "samples/3.과업지시서_070.hwp"


def _out(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return (z.read("Contents/header.xml").decode("utf-8"),
                z.read("Contents/section0.xml").decode("utf-8"))


def test_real_styles_present(tmp_path):
    hdr, _ = _out(tmp_path)
    styles = re.search(r'<hh:styles itemCnt="(\d+)">', hdr)
    assert styles and int(styles.group(1)) == 63
    assert 'name="바탕글"' in hdr
    assert 'engName="Normal"' in hdr


def test_style_refs_resolve(tmp_path):
    hdr, sec = _out(tmp_path)
    style_ids = set(re.findall(r'<hh:style id="(\d+)"', hdr))
    para_ids = set(re.findall(r'<hh:paraPr id="(\d+)"', hdr))
    char_ids = set(re.findall(r'<hh:charPr id="(\d+)"', hdr))
    # every style's refs resolve
    for m in re.finditer(r'<hh:style\b[^>]*>', hdr):
        tag = m.group(0)
        pr = re.search(r'paraPrIDRef="(\d+)"', tag)
        cr = re.search(r'charPrIDRef="(\d+)"', tag)
        nr = re.search(r'nextStyleIDRef="(\d+)"', tag)
        if pr:
            assert pr.group(1) in para_ids
        if cr:
            assert cr.group(1) in char_ids
        if nr:
            assert nr.group(1) in style_ids
    # every paragraph styleIDRef resolves
    for ref in re.findall(r'styleIDRef="(\d+)"', sec):
        assert ref in style_ids


def test_real_style_ids_used(tmp_path):
    _, sec = _out(tmp_path)
    refs = set(re.findall(r'styleIDRef="(\d+)"', sec))
    assert refs, "paragraphs must carry styleIDRef"
    assert refs != {"0"}, "real (non-default) style ids should appear"
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_convert_styles.py -v`
Expected: PASS

- [ ] **Step 3: Run the full suite (regression)**

Run: `.venv/bin/python -m pytest -q`
Expected: all green (existing 109 + new tests)

- [ ] **Step 4: Measure fidelity gain (informational)**

Run:
```bash
.venv/bin/python -c "
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import report
import tempfile, os
out = os.path.join(tempfile.mkdtemp(), 'out.hwpx')
convert('samples/3.과업지시서_070.hwp', out)
print(report(out, 'samples/3.과업지시서_070.hwpx'))
"
```
Expected: `header.xml` match above 87.4%; `style` no longer in the header miss list. Record the number in the commit message.

- [ ] **Step 5: Commit**

```bash
git add tests/test_convert_styles.py
git commit -m "test: end-to-end real-styles fidelity + no dangling style refs"
```

---

## Self-Review

**Spec coverage:** Style parse (Task 2), transform incl. name/engName swap and kind→type (Task 3), refs clamped no-dangling (Task 2 reader + Task 5 assertion), real paragraph styleIDRef (Task 3 body + Task 2 clamp), writer real block + empty fallback (Task 4), fidelity/style-count (Task 5). typeInfo/tab/linesegarray explicitly out of scope. Covered.

**Placeholder scan:** none — every code step contains full code.

**Type consistency:** `HwpStyle` fields (Task 1) parsed in Task 2, consumed by `map_styles` in Task 3; `Style` fields (Task 1) produced in Task 3, consumed by the writer in Task 4. `_clamp_index` (Task 2) used by both `_clamp_style_refs` and `_clamp_paragraph_style_ids`. `Header.styles` produced in Task 3, consumed in Task 4. `map_paragraph` signature unchanged (still `(hpar, para_id)`); only its returned `style_id` changes. Field names `para_pr_id`/`char_pr_id`/`next_style_id`/`lang_id`/`lock_form` consistent between model, mapper, and writer.
