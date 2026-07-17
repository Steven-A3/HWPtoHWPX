# Subscript charPr Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `<hh:subscript/>` in each `<hh:charPr>` whose HWP `CharShape` has `charshapeflags` bit 16 set.

**Architecture:** Four minimal edits — `HwpCharShape.subscript` / `CharPr.subscript` (models), read bit 16 (reader), pass through (mapper), append `<hh:subscript/>` after `<hh:shadow>` (writer). Header-only; `section0.xml` is unchanged.

**Tech Stack:** Python 3.9+ floor, pyhwp `hwp5proc xml`, lxml, pytest.

## Global Constraints

- **Python 3.9 floor:** no `X | None`.
- **Tests run with `.venv/bin/python -m pytest`** — plain python lacks `hwp5proc` (~13 spurious failures). Every command below uses `.venv/bin/python -m pytest`.
- **Fidelity scoring is element-count per tag** — each `<hh:subscript/>` adds one `subscript` element.
- **The rule:** `subscript = ((charshapeflags >> 16) & 1) == 1`. Only bit 16 → `<hh:subscript/>`. Superscript (bit 17) is a non-goal (absent in samples, unverified).
- **Placement:** `<hh:subscript/>` is an empty element, the charPr's LAST child (after `<hh:shadow>`).
- **Header-only:** this milestone changes only `header.xml`; `section0.xml` is byte-unchanged (no re-baseline needed). Verified counts: sample 3 has 3 subscript charPrs (ids 58/59/60), sample 4 has 4 (ids 131–134).

---

### Task 1: Models + reader + mapper + writer

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (`HwpCharShape.subscript`)
- Modify: `hwp2hwpx/owpml/model.py` (`CharPr.subscript`)
- Modify: `hwp2hwpx/hwpmodel/reader.py` (CharShape parse in `read_docinfo`)
- Modify: `hwp2hwpx/mapper/char_pr.py` (`map_char_shapes`)
- Modify: `hwp2hwpx/owpml/header_writer.py` (charPr emission)
- Test: `tests/test_subscript_charpr.py` (Create)

**Interfaces:**
- Produces: `HwpCharShape.subscript: bool`, `CharPr.subscript: bool`; reader sets it from `charshapeflags` bit 16; mapper passes it through; `_write_char_properties` (or the charPr loop in `header_writer`) emits `<hh:subscript/>` last when true.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_subscript_charpr.py
import glob
from lxml import etree
from hwp2hwpx.constants import NS
from hwp2hwpx.hwpmodel.reader import read_docinfo, hwp5_xml
from hwp2hwpx.hwpmodel.model import HwpCharShape
from hwp2hwpx.owpml.model import CharPr, Header
from hwp2hwpx.mapper.char_pr import map_char_shapes
from hwp2hwpx.owpml.header_writer import header_xml


def test_reader_sets_subscript_from_flag_bit16():
    di = read_docinfo(hwp5_xml(glob.glob("samples/3.*.hwp")[0]))
    assert di.char_shapes[58].subscript is True
    assert di.char_shapes[59].subscript is True
    assert di.char_shapes[0].subscript is False


def test_mapper_passes_subscript_through():
    cps = map_char_shapes([HwpCharShape(index=0, base_size=1000, subscript=True),
                           HwpCharShape(index=1, base_size=1000)])
    assert cps[0].subscript is True and cps[1].subscript is False


def test_writer_emits_subscript_as_last_child():
    header = Header(char_prs=[CharPr(id=0, subscript=True)])
    xml = header_xml(header)
    root = etree.fromstring(xml)
    ce = root.find(".//{%s}charPr" % NS["hh"])
    kids = [etree.QName(c).localname for c in ce]
    assert kids[-1] == "subscript"
    assert ce.find("{%s}subscript" % NS["hh"]) is not None


def test_writer_no_subscript_when_false():
    header = Header(char_prs=[CharPr(id=0, subscript=False)])
    xml = header_xml(header)
    root = etree.fromstring(xml)
    ce = root.find(".//{%s}charPr" % NS["hh"])
    assert ce.find("{%s}subscript" % NS["hh"]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_subscript_charpr.py -v`
Expected: FAIL — `HwpCharShape`/`CharPr` have no `subscript`.

- [ ] **Step 3: Add the model fields**

In `hwp2hwpx/hwpmodel/model.py`, in `HwpCharShape`, after `shadow_offset_y`:

```python
    subscript: bool = False
```

In `hwp2hwpx/owpml/model.py`, in `CharPr`, after `shadow_offset_y`:

```python
    subscript: bool = False
```

- [ ] **Step 4: Read bit 16 in the reader**

In `hwp2hwpx/hwpmodel/reader.py`, in the `char_shapes.append(HwpCharShape(...))` call inside `read_docinfo`, add after `shadow_offset_y=_shadow_space(el, "y"),`:

```python
            subscript=((_hex_int(el.get("charshapeflags")) >> 16) & 1) == 1,
```

(`_hex_int` is already defined in this module.)

- [ ] **Step 5: Pass through in the mapper**

In `hwp2hwpx/mapper/char_pr.py`, in the `CharPr(...)` construction, after `shadow_offset_y=cs.shadow_offset_y,`:

```python
            subscript=cs.subscript,
```

- [ ] **Step 6: Emit in the writer**

In `hwp2hwpx/owpml/header_writer.py`, in the charPr loop, immediately after the `<hh:shadow>` block (the `sh.set("offsetY", ...)` line):

```python
        if cp.subscript:
            etree.SubElement(ce, _hh("subscript"))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_subscript_charpr.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. `section0.xml` is unchanged (subscript is header-only), so no existing section guard breaks.

- [ ] **Step 9: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py hwp2hwpx/hwpmodel/reader.py hwp2hwpx/mapper/char_pr.py hwp2hwpx/owpml/header_writer.py tests/test_subscript_charpr.py
git commit -m "feat: emit hh:subscript for charPr with charshapeflags bit 16"
```

---

### Task 2: End-to-end fidelity

**Files:**
- Test: `tests/test_convert_subscript.py` (Create)

**Interfaces:**
- Consumes: the full `convert()` pipeline (Task 1); `score_part`/`unzip_parts`.

- [ ] **Step 1: Write the end-to-end tests**

```python
# tests/test_convert_subscript.py
import glob
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _score(prefix, part, tmp_path):
    hwp = glob.glob(prefix + "*.hwp")[0]
    ref = glob.glob(prefix + "*.hwpx")[0]
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return score_part(unzip_parts(str(out))[part], unzip_parts(ref)[part])


def test_sample3_subscript_present(tmp_path):
    s = _score("samples/3.", "Contents/header.xml", tmp_path)
    assert s["missing"].get("subscript", 0) == 0


def test_sample4_subscript_present(tmp_path):
    s = _score("samples/4.", "Contents/header.xml", tmp_path)
    assert s["missing"].get("subscript", 0) == 0


def test_sample3_header_match_rises(tmp_path):
    s = _score("samples/3.", "Contents/header.xml", tmp_path)
    assert s["match"] > 0.9987


def test_sample3_section_unchanged_by_subscript(tmp_path):
    # subscript is header-only; section0 must have no missing subscript and
    # remain at its pre-milestone match (>= 0.9994).
    s = _score("samples/3.", "Contents/section0.xml", tmp_path)
    assert s["match"] > 0.9993
```

- [ ] **Step 2: Run the end-to-end tests**

Run: `.venv/bin/python -m pytest tests/test_convert_subscript.py -v`
Expected: PASS (4 tests). Sample 3 header ≈ 0.9988, sample 4 header ≈ 0.9960; both `subscript` miss 0.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_convert_subscript.py
git commit -m "test: end-to-end subscript charPr on both samples"
```

---

## Self-Review (author)

- **Spec coverage:** models + reader + mapper + writer + unit tests (Task 1); end-to-end fidelity (Task 2). Every spec section maps to a task.
- **Type consistency:** `HwpCharShape.subscript` / `CharPr.subscript` (bool); reader uses `_hex_int` + bit 16; writer appends `_hh("subscript")` after shadow.
- **Placeholders:** none; the change was prototyped end-to-end (s3 header 0.9982→0.9988, s4 0.9954→0.9960; both subscript miss → 0; sections unchanged).
- **Regression:** header-only, so no section byte guard is touched; no re-baseline needed.
