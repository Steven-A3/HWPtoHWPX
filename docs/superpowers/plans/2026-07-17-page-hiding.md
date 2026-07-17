# pageHiding Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `<hp:ctrl><hp:pageHiding .../></hp:ctrl>` for each HWP `PageHide` record, as a leading run-level control before `<hp:t>`.

**Architecture:** All 4 layers. Model adds `HwpPageHide`/`PageHiding` and a `ctrls` list on `HwpRun`/`Run`. Reader parses `<PageHide>` and attaches it to the following text run. Mapper passes `ctrls` through. Writer emits `<hp:ctrl><hp:pageHiding/></hp:ctrl>` before `<hp:t>`.

**Tech Stack:** Python 3.9+ floor, pyhwp `hwp5proc xml`, lxml, pytest.

## Global Constraints

- **Python 3.9 floor:** no `X | None`; use `field(default_factory=list)` for mutable defaults; forward-ref-string annotations for dataclass forward references.
- **Tests run with `.venv/bin/python -m pytest`** — plain python lacks `hwp5proc` (~13 spurious failures). Every command below uses `.venv/bin/python -m pytest`.
- **Fidelity scoring is element-count per tag** — each `PageHide` adds one `ctrl` and one `pageHiding`; attribute values are guarded by unit tests.
- **Attribute map:** `header→hideHeader`, `footer→hideFooter`, `basepage→hideMasterPage`, `pageborder→hideBorder`, `pagefill→hideFill`, `pagenumber→hidePageNum`.
- **Placement:** `<hp:ctrl>` is a run-level child emitted BEFORE `<hp:t>` (child order `ctrl[, ctrl], t`); `PageHide` attaches to the first content-bearing run built after it.
- **Samples:** `samples/3.과업지시서_070.hwp` and `samples/4.제안요청서_070.hwp` each have 2 `PageHide`. This milestone CHANGES sample 3's `section0.xml`.

---

### Task 1: Models + writer emission

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (add `HwpPageHide`; `HwpRun.ctrls`)
- Modify: `hwp2hwpx/owpml/model.py` (add `PageHiding`; `Run.ctrls`)
- Modify: `hwp2hwpx/owpml/section_writer.py` (`_write_run` emits `run.ctrls`)
- Test: `tests/test_page_hiding_writer.py` (Create)

**Interfaces:**
- Produces: `HwpPageHide(hide_header=0, hide_footer=0, hide_master_page=0, hide_border=0, hide_fill=0, hide_page_num=0)`; `HwpRun.ctrls: list`; `PageHiding(...)` (same six fields); `Run.ctrls: list`; `_write_run` emits `<hp:ctrl><hp:pageHiding/></hp:ctrl>` before `<hp:t>`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_page_hiding_writer.py
from lxml import etree
from hwp2hwpx.constants import NS
from hwp2hwpx.owpml.model import Run, Text, PageHiding
from hwp2hwpx.owpml.section_writer import _write_run


def _run_el(run):
    p = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"], "hc": NS["hc"]})
    _write_run(p, run, state=None)
    return p[0]


def _localnames(el):
    return [etree.QName(c).localname for c in el]


def test_pagehiding_emits_ctrl_before_t():
    run = Run(char_pr_id=48, texts=[Text("hi")],
              ctrls=[PageHiding(hide_page_num=1)])
    r = _run_el(run)
    assert _localnames(r) == ["ctrl", "t"]          # ctrl before t
    ph = r.find("{%s}ctrl/{%s}pageHiding" % (NS["hp"], NS["hp"]))
    assert ph is not None
    assert ph.get("hidePageNum") == "1"
    assert ph.get("hideHeader") == "0"


def test_two_pagehidings_emit_two_ctrls():
    run = Run(char_pr_id=48, texts=[Text("hi")],
              ctrls=[PageHiding(hide_page_num=1), PageHiding(hide_page_num=1)])
    r = _run_el(run)
    assert _localnames(r) == ["ctrl", "ctrl", "t"]


def test_no_ctrls_unchanged():
    run = Run(char_pr_id=5, texts=[Text("hi")])
    r = _run_el(run)
    assert _localnames(r) == ["t"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_page_hiding_writer.py -v`
Expected: FAIL — `PageHiding` not importable / `Run` has no `ctrls`.

- [ ] **Step 3: Add the models**

In `hwp2hwpx/hwpmodel/model.py`, add near the other small dataclasses:

```python
@dataclass
class HwpPageHide:
    hide_header: int = 0
    hide_footer: int = 0
    hide_master_page: int = 0
    hide_border: int = 0
    hide_fill: int = 0
    hide_page_num: int = 0
```

And add a field to `HwpRun` (after `drawing`):

```python
    ctrls: list = field(default_factory=list)
```

In `hwp2hwpx/owpml/model.py`, add near `Control`:

```python
@dataclass
class PageHiding:
    hide_header: int = 0
    hide_footer: int = 0
    hide_master_page: int = 0
    hide_border: int = 0
    hide_fill: int = 0
    hide_page_num: int = 0
```

And add a field to `Run` (after `drawing`):

```python
    ctrls: list = field(default_factory=list)
```

(`field` is already imported in both modules.)

- [ ] **Step 4: Emit ctrls in `_write_run`**

In `hwp2hwpx/owpml/section_writer.py`, import `PageHiding`:

```python
from ..owpml.model import Control, Pic, MarkpenBegin, MarkpenEnd, PageHiding
```

In `_write_run`, right after `r.set("charPrIDRef", str(run.char_pr_id))` and BEFORE `if run.texts:`, emit the leading ctrls:

```python
    for c in getattr(run, "ctrls", ()):
        ctrl = etree.SubElement(r, _hp("ctrl"))
        ph = etree.SubElement(ctrl, _hp("pageHiding"))
        ph.set("hideHeader", str(c.hide_header))
        ph.set("hideFooter", str(c.hide_footer))
        ph.set("hideMasterPage", str(c.hide_master_page))
        ph.set("hideBorder", str(c.hide_border))
        ph.set("hideFill", str(c.hide_fill))
        ph.set("hidePageNum", str(c.hide_page_num))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_page_hiding_writer.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (no run has `ctrls` yet — the mapper isn't wired until Task 2 — so output is unchanged).

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py hwp2hwpx/owpml/section_writer.py tests/test_page_hiding_writer.py
git commit -m "feat: pageHiding model + writer emits ctrl/pageHiding before hp:t"
```

---

### Task 2: Reader parses PageHide + mapper passthrough

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py` (`parse_paragraph`; add `_parse_page_hide`)
- Modify: `hwp2hwpx/mapper/body.py` (map `HwpRun.ctrls` → `Run.ctrls`)
- Test: `tests/test_page_hiding_reader.py` (Create)

**Interfaces:**
- Consumes: `HwpPageHide`, `HwpRun.ctrls`, `PageHiding`, `Run.ctrls` (Task 1).
- Produces: `parse_paragraph` attaches parsed `HwpPageHide` (as leading ctrls) to the first content run; `map_paragraph` maps each run's `ctrls` to `Run.ctrls`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_page_hiding_reader.py
import glob
from lxml import etree
from hwp2hwpx.hwpmodel.reader import parse_paragraph, read_document, hwp5_xml
from hwp2hwpx.mapper.body import map_paragraph


def _para(inner):
    xml = ('<Paragraph parashape-id="0" style-id="0"><LineSeg>%s</LineSeg>'
           '</Paragraph>' % inner)
    return parse_paragraph(etree.fromstring(xml))


def test_pagehide_attaches_to_following_text_run():
    p = _para('<PageHide basepage="0" header="0" footer="0" pageborder="0" '
              'pagefill="0" pagenumber="1"/>'
              '<Text charshape-id="48">hi</Text>')
    run = p.runs[0]
    assert len(run.ctrls) == 1
    assert run.ctrls[0].hide_page_num == 1
    assert run.ctrls[0].hide_header == 0


def test_two_pagehides_attach():
    p = _para('<PageHide pagenumber="1"/><PageHide pagenumber="1"/>'
              '<Text charshape-id="48">hi</Text>')
    assert len(p.runs[0].ctrls) == 2


def test_no_pagehide_means_no_ctrls():
    p = _para('<Text charshape-id="48">hi</Text>')
    assert p.runs[0].ctrls == []


def test_pagehide_marks_paragraph_markpen_unsafe():
    p = _para('<PageHide pagenumber="1"/><Text charshape-id="48">hi</Text>')
    assert p.markpen_unsafe is True


def test_mapper_maps_ctrls():
    from hwp2hwpx.hwpmodel.model import HwpRun, HwpPageHide, HwpParagraph
    hpar = HwpParagraph(para_shape_id=0,
                        runs=[HwpRun(char_shape_id=48, contents=["hi"],
                                     ctrls=[HwpPageHide(hide_page_num=1)])])
    para = map_paragraph(hpar, 0)
    assert len(para.runs[0].ctrls) == 1
    assert para.runs[0].ctrls[0].hide_page_num == 1


def test_sample3_has_two_pagehides_attached():
    doc = read_document(hwp5_xml(glob.glob("samples/3.*.hwp")[0]))
    def walk(paras):
        for p in paras:
            for run in p.runs:
                yield len(run.ctrls)
                if run.table is not None:
                    for row in run.table.table_rows:
                        for cell in row.cells:
                            yield from walk(cell.paragraphs)
    assert sum(walk(doc.sections[0].paragraphs)) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_page_hiding_reader.py -v`
Expected: FAIL — `parse_paragraph` doesn't parse `PageHide` yet.

- [ ] **Step 3: Parse `PageHide` in the reader**

In `hwp2hwpx/hwpmodel/reader.py`, import `HwpPageHide` (add to the existing `from .model import (...)` block), and add a parser near `_parse_page_def`:

```python
def _parse_page_hide(el):
    return HwpPageHide(
        hide_header=_int(el.get("header")),
        hide_footer=_int(el.get("footer")),
        hide_master_page=_int(el.get("basepage")),
        hide_border=_int(el.get("pageborder")),
        hide_fill=_int(el.get("pagefill")),
        hide_page_num=_int(el.get("pagenumber")),
    )
```

In `parse_paragraph`, add a `pending_ctrls` accumulator and attach it in `flush()`. Change the accumulator init block (near `markpen_unsafe = False` / `break_cs = None`):

```python
    pending_ctrls = []
```

Update `flush()` to attach and clear pending ctrls:

```python
    def flush():
        nonlocal cur_cs, cur_contents, pending_ctrls
        if cur_contents:
            runs.append(HwpRun(char_shape_id=cur_cs, contents=cur_contents,
                               ctrls=pending_ctrls))
            pending_ctrls = []
        cur_cs = None
        cur_contents = []
```

Add a `PageHide` branch in the `for child in para_el.findall("LineSeg/*"):` loop (alongside the Text/ControlChar/TableControl/GShapeObjectControl branches):

```python
        elif child.tag == "PageHide":
            pending_ctrls.append(_parse_page_hide(child))
            markpen_unsafe = True   # extended control occupies char positions
```

- [ ] **Step 4: Map ctrls in the mapper**

In `hwp2hwpx/mapper/body.py`, import `PageHiding` (add to the `from ..owpml.model import (...)` block), and add a helper + wire it into `map_paragraph`:

```python
def _map_ctrls(ctrls):
    out = []
    for c in ctrls:
        out.append(PageHiding(
            hide_header=c.hide_header, hide_footer=c.hide_footer,
            hide_master_page=c.hide_master_page, hide_border=c.hide_border,
            hide_fill=c.hide_fill, hide_page_num=c.hide_page_num))
    return out
```

In `map_paragraph`, add `ctrls=_map_ctrls(r.ctrls)` to each `Run(...)` construction (the table, drawing, and text-run cases), e.g. the text-run case becomes:

```python
        else:
            runs.append(Run(char_pr_id=r.char_shape_id,
                            texts=_map_contents(r.contents),
                            ctrls=_map_ctrls(r.ctrls)))
```

(Apply the same `ctrls=_map_ctrls(r.ctrls)` to the table and drawing `Run(...)` constructions so no ctrls are dropped.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_page_hiding_reader.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Run the full suite to see the expected sample-3 baseline break**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass EXCEPT `tests/test_convert_markpen.py::test_sample3_section_unchanged`, which now fails (sample 3's `section0.xml` gained 2 `<hp:ctrl><hp:pageHiding/></hp:ctrl>`). Expected — fixed in Task 3. If ANY OTHER test fails, stop and report it.

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py hwp2hwpx/mapper/body.py tests/test_page_hiding_reader.py
git commit -m "feat: reader parses PageHide, mapper passes pageHiding ctrls through"
```

---

### Task 3: End-to-end fidelity + re-baseline the sample-3 guard

**Files:**
- Modify: `tests/test_convert_markpen.py` (re-baseline `test_sample3_section_unchanged`)
- Test: `tests/test_convert_page_hiding.py` (Create)

**Interfaces:**
- Consumes: the full `convert()` pipeline (Tasks 1–2); `score_part`/`unzip_parts`.

- [ ] **Step 1: Re-baseline the markpen sample-3 no-change guard**

Run this to capture the new sample-3 `section0.xml` bytes:

```bash
.venv/bin/python -c "import glob,hashlib; from hwp2hwpx.convert import convert; from hwp2hwpx.fidelity.xmlnorm import unzip_parts; convert(glob.glob('samples/3.*.hwp')[0],'/tmp/_s3.hwpx'); b=unzip_parts('/tmp/_s3.hwpx')['Contents/section0.xml']; print(len(b), hashlib.sha256(b).hexdigest())"
```

In `tests/test_convert_markpen.py`, update `test_sample3_section_unchanged` to the printed `len` and `sha256` prefix (first 16 hex chars) and refresh its comment to name the pageHiding milestone:

```python
def test_sample3_section_unchanged(tmp_path):
    # Sample 3 has no markpen. Baseline refreshed for the pageHiding milestone
    # (adds 2 <hp:ctrl><hp:pageHiding/></hp:ctrl>): len <LEN>, sha256 <PREFIX>.
    out = tmp_path / "s3.hwpx"
    convert(S3, str(out))
    body = unzip_parts(str(out))["Contents/section0.xml"]
    import hashlib
    assert len(body) == <LEN>
    assert hashlib.sha256(body).hexdigest().startswith("<PREFIX>")
```

- [ ] **Step 2: Run the re-baselined test**

Run: `.venv/bin/python -m pytest tests/test_convert_markpen.py::test_sample3_section_unchanged -v`
Expected: PASS.

- [ ] **Step 3: Write the end-to-end fidelity tests**

```python
# tests/test_convert_page_hiding.py
import glob
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

PAIRS = [("samples/3.", None), ("samples/4.", None)]


def _score(prefix, tmp_path):
    hwp = glob.glob(prefix + "*.hwp")[0]
    ref = glob.glob(prefix + "*.hwpx")[0]
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(ref)["Contents/section0.xml"]
    return score_part(ours, theirs)


def test_sample3_pagehiding_present(tmp_path):
    s = _score("samples/3.", tmp_path)
    assert s["missing"].get("pageHiding", 0) == 0


def test_sample4_pagehiding_present(tmp_path):
    s = _score("samples/4.", tmp_path)
    assert s["missing"].get("pageHiding", 0) == 0


def test_sample4_pagehiding_serialization(tmp_path):
    hwp = glob.glob("samples/4.*.hwp")[0]
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    xml = unzip_parts(str(out))["Contents/section0.xml"].decode("utf-8")
    assert '<hp:ctrl><hp:pageHiding hideHeader="0" hideFooter="0" hideMasterPage="0" hideBorder="0" hideFill="0" hidePageNum="1"/></hp:ctrl>' in xml
```

- [ ] **Step 4: Run the end-to-end tests**

Run: `.venv/bin/python -m pytest tests/test_convert_page_hiding.py -v`
Expected: PASS (3 tests). If the serialization test fails, print the actual `<hp:pageHiding` substring and reconcile the attribute order (lxml preserves set-order; the writer sets them header→footer→masterPage→border→fill→pageNum).

- [ ] **Step 5: Run the full suite (all green)**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, including the re-baselined markpen guard and the markpen/trailing-empty-run/inline-t tests (unchanged).

- [ ] **Step 6: Commit**

```bash
git add tests/test_convert_page_hiding.py tests/test_convert_markpen.py
git commit -m "test: end-to-end pageHiding + re-baseline sample-3 guard"
```

---

## Self-Review (author)

- **Spec coverage:** models + writer (Task 1); reader + mapper (Task 2); e2e + re-baseline (Task 3). Every spec section maps to a task.
- **Type consistency:** `HwpPageHide`/`PageHiding` share the six field names; `HwpRun.ctrls`/`Run.ctrls`; `_parse_page_hide`, `_map_ctrls`. Attribute map is applied once, in `_parse_page_hide`.
- **Placeholders:** none except the deliberately-captured-live sample-3 baseline in Task 3 Step 1 (`<LEN>`/`<PREFIX>`), which the implementer fills from the printed command output.
- **Ordering:** models+writer (dormant) → reader+mapper (lights it up) → e2e avoids any transient crash; the writer tolerates `ctrls` before the reader produces them. The one expected break (sample-3 byte guard) is re-baselined in Task 3, not weakened.
- **Interaction:** `PageHide` sets `markpen_unsafe` (it occupies char positions the mapper doesn't count), preserving the markpen "skip rather than mis-assign" invariant.
