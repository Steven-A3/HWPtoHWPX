# Header Document-Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit the six header-tail elements — `beginNum`, `compatibleDocument`>`layoutCompatibility`, `docOption`>`linkinfo`, `trackchageConfig` — on both samples. `beginNum` and `compatibleDocument targetProgram` are derived from the HWP; the other three are documented constants.

**Architecture:** Extends the 4-layer pipeline. Reader parses `DocumentProperties`/`CompatibleDocument` in `read_docinfo`; mapper maps them; `header_xml` emits `beginNum` before `refList` and the other three after `refList`.

**Tech Stack:** Python 3.9+, lxml, pyhwp, pytest.

## Global Constraints

- **Python 3.9 floor:** NO `X | None`; forward-ref-string defaults, `field(default_factory=...)`.
- **Run tests with `.venv/bin/python -m pytest`** — plain `python`/`python3` lacks `hwp5proc`.
- **Placement (verified):** `beginNum` is the FIRST child of `<hh:head>` (before `<hh:refList>`); `compatibleDocument`, `docOption`, `trackchageConfig` come AFTER `</hh:refList>`, in that order.
- **Derived values:** `beginNum` ← `DocumentProperties` (page-startnum→page, footnote-startnum→footnote, endnote-startnum→endnote, picture-startnum→pic, table-startnum→tbl, math-startnum→equation); `compatibleDocument targetProgram` ← `CompatibleDocument target` (0→`HWP201X`, default `HWP201X`).
- **Constants (documented, identical on both samples):** `layoutCompatibility` empty; `linkinfo path="" pageInherit="1" footnoteInherit="0"`; `trackchageConfig flags="56"`.
- Mapper returns non-None defaults (not None) so the writer always emits `beginNum`/`compatibleDocument` even for record-less documents.
- Samples at `samples/{3,4}.…hwp[x]` (local). Reader unit test uses the in-repo fixture `tests/fixtures/sample3.hwp5.xml`.

---

### Task 1: Models — DocProperties / Compat / BeginNum

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py`, `hwp2hwpx/owpml/model.py`
- Test: `tests/test_model_docsettings.py`

**Interfaces:**
- Produces: `HwpDocProperties`, `HwpCompatDocument`; `HwpDocInfo.doc_properties`/`.compat`. OWPML `BeginNum`, `CompatDocument`; `Header.begin_num`/`.compat`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_docsettings.py
from hwp2hwpx.hwpmodel.model import HwpDocProperties, HwpCompatDocument, HwpDocInfo
from hwp2hwpx.owpml.model import BeginNum, CompatDocument, Header


def test_hwp_docsettings_defaults():
    assert HwpDocProperties().page_start == 1
    assert HwpDocProperties().equation_start == 1
    assert HwpCompatDocument().target == 0
    di = HwpDocInfo()
    assert di.doc_properties is None and di.compat is None


def test_owpml_docsettings_defaults():
    assert BeginNum().page == 1 and BeginNum().equation == 1
    assert CompatDocument().target_program == "HWP201X"
    h = Header()
    assert h.begin_num is None and h.compat is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_docsettings.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add HWP-side dataclasses**

Add to `hwp2hwpx/hwpmodel/model.py` (near `HwpDocInfo`):

```python
@dataclass
class HwpDocProperties:
    page_start: int = 1
    footnote_start: int = 1
    endnote_start: int = 1
    pic_start: int = 1
    tbl_start: int = 1
    equation_start: int = 1


@dataclass
class HwpCompatDocument:
    target: int = 0
```

Modify `HwpDocInfo` to add the two fields (keep all existing fields):

```python
@dataclass
class HwpDocInfo:
    fonts: list = field(default_factory=list)
    char_shapes: list = field(default_factory=list)
    para_shapes: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    tab_defs: list = field(default_factory=list)
    doc_properties: "HwpDocProperties" = None
    compat: "HwpCompatDocument" = None
```

- [ ] **Step 4: Add OWPML-side dataclasses**

Add to `hwp2hwpx/owpml/model.py` (near `Header`):

```python
@dataclass
class BeginNum:
    page: int = 1
    footnote: int = 1
    endnote: int = 1
    pic: int = 1
    tbl: int = 1
    equation: int = 1


@dataclass
class CompatDocument:
    target_program: str = "HWP201X"
```

Modify `Header` to add the two fields (keep all existing fields):

```python
@dataclass
class Header:
    fonts_by_lang: dict = field(default_factory=dict)
    char_prs: list = field(default_factory=list)
    para_prs: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    tab_defs: list = field(default_factory=list)
    begin_num: "BeginNum" = None
    compat: "CompatDocument" = None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_docsettings.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py tests/test_model_docsettings.py
git commit -m "feat: DocProperties / Compat / BeginNum dataclasses"
```

---

### Task 2: Reader parses `DocumentProperties` + `CompatibleDocument`

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`
- Test: `tests/test_reader_docsettings.py`

**Interfaces:**
- Consumes: `HwpDocProperties`, `HwpCompatDocument` (Task 1); existing `_int`.
- Produces: `_parse_doc_properties(root)`, `_parse_compat(root)`; `read_docinfo` attaches `doc_properties`/`compat`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader_docsettings.py
from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _di():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read())


def test_doc_properties_parsed():
    dp = _di().doc_properties
    assert dp is not None
    assert dp.page_start == 1 and dp.footnote_start == 1 and dp.endnote_start == 1
    assert dp.pic_start == 1 and dp.tbl_start == 1 and dp.equation_start == 1


def test_compat_parsed():
    c = _di().compat
    assert c is not None and c.target == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reader_docsettings.py -v`
Expected: FAIL (`doc_properties`/`compat` are `None`).

- [ ] **Step 3: Add the parsers and wire them into `read_docinfo`**

In `hwp2hwpx/hwpmodel/reader.py`, add `HwpDocProperties, HwpCompatDocument` to the `.model` import. Add the parsers (above `read_docinfo`):

```python
def _parse_doc_properties(root):
    el = root.find(".//DocumentProperties")
    if el is None:
        return None
    return HwpDocProperties(
        page_start=_int(el.get("page-startnum"), 1),
        footnote_start=_int(el.get("footnote-startnum"), 1),
        endnote_start=_int(el.get("endnote-startnum"), 1),
        pic_start=_int(el.get("picture-startnum"), 1),
        tbl_start=_int(el.get("table-startnum"), 1),
        equation_start=_int(el.get("math-startnum"), 1),
    )


def _parse_compat(root):
    el = root.find(".//CompatibleDocument")
    if el is None:
        return None
    return HwpCompatDocument(target=_int(el.get("target")))
```

Modify the `read_docinfo` main return (the `return HwpDocInfo(fonts=..., ..., tab_defs=_parse_tab_defs(id_mappings))`) to also pass the two new records:

```python
    return HwpDocInfo(fonts=fonts, char_shapes=char_shapes,
                      para_shapes=para_shapes,
                      border_fills=_parse_border_fills(id_mappings),
                      styles=_parse_styles(id_mappings),
                      tab_defs=_parse_tab_defs(id_mappings),
                      doc_properties=_parse_doc_properties(root),
                      compat=_parse_compat(root))
```

(Match the existing keyword arguments already present in the call; only add the two new lines. `root` is already bound at the top of `read_docinfo`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_reader_docsettings.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run reader regression subset**

Run: `.venv/bin/python -m pytest tests/test_reader_docinfo.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_docsettings.py
git commit -m "feat: reader parses DocumentProperties + CompatibleDocument"
```

---

### Task 3: Mapper — BeginNum / CompatDocument

**Files:**
- Create: `hwp2hwpx/mapper/docsettings.py`
- Modify: `hwp2hwpx/mapper/body.py`
- Test: `tests/test_mapper_docsettings.py`

**Interfaces:**
- Consumes: `HwpDocProperties`/`HwpCompatDocument` (Task 1), OWPML `BeginNum`/`CompatDocument` (Task 1).
- Produces: `map_begin_num(dp) -> BeginNum`, `map_compat(c) -> CompatDocument` (both return non-None defaults for `None`); `map_document` sets `Header.begin_num`/`.compat`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mapper_docsettings.py
from hwp2hwpx.hwpmodel.model import (
    HwpDocProperties, HwpCompatDocument, HwpDocInfo, HwpDocument,
)
from hwp2hwpx.mapper.docsettings import map_begin_num, map_compat
from hwp2hwpx.mapper.body import map_document


def test_map_begin_num_passthrough():
    bn = map_begin_num(HwpDocProperties(page_start=2, footnote_start=3,
                                        endnote_start=4, pic_start=5,
                                        tbl_start=6, equation_start=7))
    assert (bn.page, bn.footnote, bn.endnote, bn.pic, bn.tbl, bn.equation) == \
        (2, 3, 4, 5, 6, 7)


def test_map_begin_num_none_defaults():
    bn = map_begin_num(None)
    assert bn.page == 1 and bn.equation == 1


def test_map_compat_target_map():
    assert map_compat(HwpCompatDocument(target=0)).target_program == "HWP201X"
    assert map_compat(HwpCompatDocument(target=99)).target_program == "HWP201X"
    assert map_compat(None).target_program == "HWP201X"


def test_map_document_attaches_docsettings():
    doc = HwpDocument(docinfo=HwpDocInfo(
        doc_properties=HwpDocProperties(page_start=9),
        compat=HwpCompatDocument(target=0)), sections=[])
    header = map_document(doc).header
    assert header.begin_num.page == 9
    assert header.compat.target_program == "HWP201X"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mapper_docsettings.py -v`
Expected: FAIL with `ModuleNotFoundError: hwp2hwpx.mapper.docsettings`.

- [ ] **Step 3: Create `hwp2hwpx/mapper/docsettings.py`**

```python
"""Map HWP document-level settings to OWPML header elements."""
from ..owpml.model import BeginNum, CompatDocument

_TARGET_PROGRAM = {0: "HWP201X"}   # observed; default HWP201X


def map_begin_num(dp):
    if dp is None:
        return BeginNum()
    return BeginNum(page=dp.page_start, footnote=dp.footnote_start,
                    endnote=dp.endnote_start, pic=dp.pic_start,
                    tbl=dp.tbl_start, equation=dp.equation_start)


def map_compat(c):
    if c is None:
        return CompatDocument()
    return CompatDocument(
        target_program=_TARGET_PROGRAM.get(c.target, "HWP201X"))
```

- [ ] **Step 4: Wire into `map_document`**

In `hwp2hwpx/mapper/body.py`: add `from .docsettings import map_begin_num, map_compat` to the imports, and set the two fields in the `Header(...)` construction inside `map_document`:

```python
    header = Header(
        fonts_by_lang=map_fonts(di.fonts),
        char_prs=map_char_shapes(di.char_shapes),
        para_prs=map_para_shapes(di.para_shapes),
        border_fills=map_border_fills(di.border_fills),
        styles=map_styles(di.styles),
        tab_defs=map_tab_defs(di.tab_defs),
        begin_num=map_begin_num(di.doc_properties),
        compat=map_compat(di.compat),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_mapper_docsettings.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Run mapper regression subset**

Run: `.venv/bin/python -m pytest tests/test_mapper_body.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/mapper/docsettings.py hwp2hwpx/mapper/body.py tests/test_mapper_docsettings.py
git commit -m "feat: map DocumentProperties/CompatibleDocument to header settings"
```

---

### Task 4: Writer emits the six header-tail elements

**Files:**
- Modify: `hwp2hwpx/owpml/header_writer.py`
- Test: `tests/test_header_writer_docsettings.py`

**Interfaces:**
- Consumes: OWPML `BeginNum`/`CompatDocument`, `Header.begin_num`/`.compat`.
- Produces: `beginNum` as `head`'s first child; `compatibleDocument`>`layoutCompatibility`, `docOption`>`linkinfo`, `trackchageConfig` after `refList`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_header_writer_docsettings.py
from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, BeginNum, CompatDocument

HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _q(t):
    return "{%s}%s" % (HH, t)


def _root(header):
    return etree.fromstring(header_xml(header).split(b"?>", 1)[1])


def test_begin_num_is_first_child_before_reflist():
    h = Header(begin_num=BeginNum(page=1, footnote=2, endnote=3, pic=4, tbl=5,
                                  equation=6))
    root = _root(h)
    assert etree.QName(root[0]).localname == "beginNum"
    bn = root[0]
    assert bn.get("page") == "1" and bn.get("footnote") == "2"
    assert bn.get("equation") == "6"
    # refList comes after beginNum
    tags = [etree.QName(c).localname for c in root]
    assert tags.index("beginNum") < tags.index("refList")


def test_tail_elements_after_reflist():
    h = Header(compat=CompatDocument(target_program="HWP201X"))
    root = _root(h)
    tags = [etree.QName(c).localname for c in root]
    for t in ("compatibleDocument", "docOption", "trackchageConfig"):
        assert t in tags and tags.index(t) > tags.index("refList")
    cd = root.find(_q("compatibleDocument"))
    assert cd.get("targetProgram") == "HWP201X"
    assert cd.find(_q("layoutCompatibility")) is not None
    li = root.find(_q("docOption")).find(_q("linkinfo"))
    assert li.get("path") == "" and li.get("pageInherit") == "1"
    assert li.get("footnoteInherit") == "0"
    assert root.find(_q("trackchageConfig")).get("flags") == "56"


def test_none_begin_num_and_compat_emit_defaults():
    root = _root(Header())
    assert root.find(_q("beginNum")).get("page") == "1"
    assert root.find(_q("compatibleDocument")).get("targetProgram") == "HWP201X"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_header_writer_docsettings.py -v`
Expected: FAIL (no `beginNum`/tail elements emitted).

- [ ] **Step 3: Emit `beginNum` first and the tail elements**

In `hwp2hwpx/owpml/header_writer.py`, add `from .model import BeginNum, CompatDocument` to the imports (alongside the existing model imports). In `header_xml`, immediately after `root.set("secCnt", str(sec_cnt))` and BEFORE `ref = etree.SubElement(root, _hh("refList"))`, emit `beginNum`:

```python
    bn = header.begin_num or BeginNum()
    be = etree.SubElement(root, _hh("beginNum"))
    be.set("page", str(bn.page))
    be.set("footnote", str(bn.footnote))
    be.set("endnote", str(bn.endnote))
    be.set("pic", str(bn.pic))
    be.set("tbl", str(bn.tbl))
    be.set("equation", str(bn.equation))
```

Immediately before `return XML_DECL + ...`, emit the tail elements as children of `root` (after the refList subtree is complete):

```python
    compat = header.compat or CompatDocument()
    cd = etree.SubElement(root, _hh("compatibleDocument"))
    cd.set("targetProgram", compat.target_program)
    etree.SubElement(cd, _hh("layoutCompatibility"))
    do = etree.SubElement(root, _hh("docOption"))
    li = etree.SubElement(do, _hh("linkinfo"))
    li.set("path", "")
    li.set("pageInherit", "1")
    li.set("footnoteInherit", "0")
    tc = etree.SubElement(root, _hh("trackchageConfig"))
    tc.set("flags", "56")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_header_writer_docsettings.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run header-writer regression subset**

Run: `.venv/bin/python -m pytest tests/test_header_writer.py -v`
Expected: PASS (existing refList/styles emission unaffected — `beginNum` is additive before it, tail is additive after).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/header_writer.py tests/test_header_writer_docsettings.py
git commit -m "feat: header emits beginNum + compatibleDocument/docOption/trackchageConfig"
```

---

### Task 5: End-to-end — six tags leave the header miss list

**Files:**
- Test: `tests/test_convert_docsettings.py`

**Interfaces:**
- Consumes: the whole pipeline via `hwp2hwpx.convert.convert`.

- [ ] **Step 1: Write the test**

```python
# tests/test_convert_docsettings.py
import zipfile
import pytest
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

PAIRS = [
    ("samples/3.과업지시서_070.hwp", "samples/3.과업지시서_070.hwpx"),
    ("samples/4.제안요청서_070.hwp", "samples/4.제안요청서_070.hwpx"),
]


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_docsettings_tags_leave_header_miss_list(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/header.xml"]
    theirs = unzip_parts(ref)["Contents/header.xml"]
    missing = score_part(ours, theirs)["missing"]
    for tag in ("beginNum", "compatibleDocument", "layoutCompatibility",
                "docOption", "linkinfo", "trackchageConfig"):
        assert missing.get(tag, 0) == 0, "%s still missing on %s" % (tag, hwp)


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_begin_num_present_all_one(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    with zipfile.ZipFile(str(out)) as z:
        h = z.read("Contents/header.xml").decode("utf-8")
    assert '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>' in h


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_header_match_high(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/header.xml"]
    theirs = unzip_parts(ref)["Contents/header.xml"]
    assert score_part(ours, theirs)["match"] > 0.998
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_convert_docsettings.py -v`
Expected: PASS (6 parametrized cases). If `test_header_match_high` fails, report the actual value (the controller decides the threshold). If a tag is still missing, the writer isn't emitting it — do NOT relax the assertion.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_convert_docsettings.py
git commit -m "test: end-to-end header doc-settings on both samples"
```

---

## Self-Review

**Spec coverage:** Reader parses `DocumentProperties`/`CompatibleDocument` (Task 2); models both sides (Task 1); mapper maps to `BeginNum`/`CompatDocument` with defaults (Task 3); writer emits `beginNum` first + the three tail elements (Task 4); e2e asserts the six tags leave the header miss list + `beginNum` values + match rise (Task 5). Two derived (beginNum, compat), three constants (layoutCompatibility empty, linkinfo, trackchange).

**Placeholder scan:** No TBD/TODO; complete code in every step; expected output on every run step.

**Type consistency:** `HwpDocProperties` fields (`page_start`…`equation_start`) used identically by reader (Task 2) and mapper (Task 3). `HwpCompatDocument.target` (int) → mapper `_TARGET_PROGRAM.get(...)`. OWPML `BeginNum`(page/footnote/endnote/pic/tbl/equation) and `CompatDocument.target_program` used identically by mapper (Task 3) and writer (Task 4). `Header.begin_num`/`.compat` set by mapper, read by writer with `or BeginNum()`/`or CompatDocument()` fallbacks so a `None` still emits valid defaults. `map_begin_num`/`map_compat` return non-None defaults, matching the "always emit" requirement.
