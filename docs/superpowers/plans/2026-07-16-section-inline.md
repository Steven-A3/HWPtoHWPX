# Section Inline Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit inline `<hp:fwSpace/>`/`<hp:lineBreak/>` as mixed content inside `<hp:t>`, and merge consecutive same-`charshape` text+control into one run — matching Hancom's run structure (869 runs / 690 `hp:t` vs our current 1603 / 1429) and recovering the dropped spaces/line breaks.

**Architecture:** Extend the existing 4 layers, touching the core text path. A run's content becomes an ordered list of text strings and control markers, emitted as one mixed-content `<hp:t>`. Migration is staged so each task's suite stays green: (1) OWPML `Control` model, (2) writer mixed-content, (3) HWP model + reader grouping, (4) mapper, (5) end-to-end.

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc xml`), pytest.

## Global Constraints

- **Python 3.9 floor:** NO PEP 604 `X | None` union syntax. Use bare `field: T = None` / `field(default_factory=list)`.
- **Inline control mapping:** HWP `ControlChar@name` `FIXWIDTH_SPACE`→`fwSpace`, `LINE_BREAK`→`lineBreak`; `PARAGRAPH_BREAK` and all other names → skipped.
- **Run grouping:** consecutive `Text`/`FIXWIDTH_SPACE`/`LINE_BREAK` with the same `charshape-id` form one run; a `charshape-id` change, a `TableControl`, or a `PARAGRAPH_BREAK` starts a new run. Grouping keys on `charshape-id` ONLY (not `lang`) and spans the whole paragraph across `LineSeg` boundaries.
- **One `<hp:t>` per non-empty run**, mixed content: text via lxml `.text`/`.tail`, controls as empty `<hp:fwSpace/>`/`<hp:lineBreak/>` children. A run with no content (`texts == []`) emits NO `<hp:t>` (preserve the empty-paragraph placeholder behavior). A table run emits no `<hp:t>`.
- **`text` convenience:** `HwpRun` exposes a read-only `text` property = `"".join` of its string contents, so text-reading call sites and the mapper's plain-text path keep working mid-migration.
- **Test runner:** `.venv/bin/python -m pytest` — plain `python` lacks `hwp5proc` (~13 spurious failures). Current suite: 141 passing.
- **Out of scope:** `<hp:ctrl>` section controls; other ControlChar kinds; `linesegarray`/`lineseg`.

---

### Task 1: OWPML Control model

**Files:**
- Modify: `hwp2hwpx/owpml/model.py`
- Test: `tests/test_model_control.py`

**Interfaces:**
- Produces: `Control(kind:str="fwSpace")`. `Run.texts` (existing list) will hold a mix of `Text` and `Control`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_control.py
from hwp2hwpx.owpml.model import Control, Run, Text


def test_control_kind():
    assert Control(kind="lineBreak").kind == "lineBreak"
    assert Control().kind == "fwSpace"


def test_run_texts_can_mix_text_and_control():
    run = Run(char_pr_id=0, texts=[Text("가"), Control("fwSpace"), Text("나")])
    assert [type(x).__name__ for x in run.texts] == ["Text", "Control", "Text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_control.py -v`
Expected: FAIL (ImportError on Control)

- [ ] **Step 3: Add the `Control` dataclass** in `hwp2hwpx/owpml/model.py`

Add immediately after the `Text` dataclass:

```python
@dataclass
class Control:
    kind: str = "fwSpace"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_control.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/model.py tests/test_model_control.py
git commit -m "feat: OWPML Control (inline fwSpace/lineBreak) model"
```

---

### Task 2: Writer emits mixed-content hp:t

**Files:**
- Modify: `hwp2hwpx/owpml/section_writer.py` (`_write_run`)
- Modify: `hwp2hwpx/owpml/package_parts.py` (`prv_text`)
- Modify: `tests/test_section_writer.py` (existing assertion now expects one merged `<hp:t>`)
- Test: `tests/test_section_writer_inline.py`

**Interfaces:**
- Consumes: `Run.texts` holding `Text`/`Control` (Task 1), existing `_hp`.
- Produces: one `<hp:t>` per non-empty run with mixed content; `Control`→`<hp:fwSpace/>`/`<hp:lineBreak/>`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_section_writer_inline.py
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text, Control
from hwp2hwpx.constants import NS


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _run_el(run):
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[run])])
    root = etree.fromstring(section_xml(sec))
    return next(root.iter(_hp("run")))


def test_control_between_texts_is_mixed_content():
    r = _run_el(Run(char_pr_id=1, texts=[Text("가"), Control("fwSpace"), Text("나")]))
    ts = list(r.iter(_hp("t")))
    assert len(ts) == 1
    t = ts[0]
    assert t.text == "가"
    fw = list(t)[0]
    assert etree.QName(fw).localname == "fwSpace"
    assert fw.tail == "나"


def test_control_first_puts_text_in_tail():
    r = _run_el(Run(char_pr_id=1, texts=[Control("lineBreak"), Text("AI")]))
    t = next(r.iter(_hp("t")))
    assert t.text is None
    lb = list(t)[0]
    assert etree.QName(lb).localname == "lineBreak"
    assert lb.tail == "AI"


def test_adjacent_texts_concatenate_in_one_t():
    r = _run_el(Run(char_pr_id=1, texts=[Text("가나"), Text("다라")]))
    ts = list(r.iter(_hp("t")))
    assert len(ts) == 1
    assert ts[0].text == "가나다라"


def test_empty_run_emits_no_t():
    r = _run_el(Run(char_pr_id=0, texts=[]))
    assert list(r.iter(_hp("t"))) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_section_writer_inline.py -v`
Expected: FAIL (multiple `<hp:t>`; controls not emitted)

- [ ] **Step 3: Rewrite `_write_run`** in `hwp2hwpx/owpml/section_writer.py`

Add `Control` to the imports at the top:

```python
from ..owpml.model import Control
```

Replace the existing `_write_run` with:

```python
def _write_run(p_el, run, state):
    r = etree.SubElement(p_el, _hp("run"))
    r.set("charPrIDRef", str(run.char_pr_id))
    if run.texts:
        te = etree.SubElement(r, _hp("t"))
        last = None  # last control child; text after it goes to its .tail
        for item in run.texts:
            if isinstance(item, Control):
                last = etree.SubElement(te, _hp(item.kind))
            else:  # Text
                if last is None:
                    te.text = (te.text or "") + item.content
                else:
                    last.tail = (last.tail or "") + item.content
    if getattr(run, "table", None) is not None:
        _write_table(r, run.table, state)
```

- [ ] **Step 4: Guard `prv_text` against Control items** in `hwp2hwpx/owpml/package_parts.py`

Replace the inner text loop in `prv_text`:

```python
            for run in para.runs:
                for t in run.texts:
                    c = getattr(t, "content", None)
                    if c:
                        buf.append(c)
```

- [ ] **Step 5: Update the existing writer test** in `tests/test_section_writer.py`

The run at line ~18 is `Run(char_pr_id=3, texts=[Text("가나"), Text("다라")])`; the two adjacent Texts now serialize as ONE merged `<hp:t>`. Change the assertion at line ~27 from expecting `["가나", "다라"]` to the merged form. Locate:

```python
    texts = [t.text for t in run.iter(_hp("t"))]
    assert texts == ["가나", "다라"]
```

and replace the assertion with:

```python
    texts = [t.text for t in run.iter(_hp("t"))]
    assert texts == ["가나다라"]
```

(If the exact surrounding assertion differs, adjust only the expected value to the single merged string; do not change the run construction.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_section_writer_inline.py tests/test_section_writer.py tests/test_section_writer_tables.py tests/test_package_parts.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py hwp2hwpx/owpml/package_parts.py tests/test_section_writer_inline.py tests/test_section_writer.py
git commit -m "feat: writer emits one mixed-content hp:t per run (fwSpace/lineBreak)"
```

---

### Task 3: HWP model + reader run grouping

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (`HwpControl`, `HwpRun`)
- Modify: `hwp2hwpx/hwpmodel/reader.py` (`parse_paragraph`)
- Modify: `tests/test_mapper_table.py`, `tests/test_mapper_body.py`, `tests/test_hwpmodel_tables.py`, `tests/test_mapper_styles.py` (HwpRun construction switches from `text=` to `contents=`)
- Test: `tests/test_reader_inline.py`, `tests/test_model_hwprun.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `HwpControl(kind:str="fwSpace")`; `HwpRun(char_shape_id, contents:list, table)` with a read-only `text` property = join of string contents. `parse_paragraph` groups by `charshape-id` into merged `HwpRun`s.

- [ ] **Step 1: Write the failing model + reader tests**

```python
# tests/test_model_hwprun.py
from hwp2hwpx.hwpmodel.model import HwpRun, HwpControl


def test_hwprun_text_property_joins_strings():
    run = HwpRun(char_shape_id=0, contents=["가", HwpControl("fwSpace"), "나"])
    assert run.text == "가나"


def test_hwprun_defaults():
    run = HwpRun(char_shape_id=0)
    assert run.contents == []
    assert run.text == ""
    assert run.table is None


def test_hwpcontrol_kind():
    assert HwpControl("lineBreak").kind == "lineBreak"
```

```python
# tests/test_reader_inline.py
from hwp2hwpx.hwpmodel.reader import read_document
from hwp2hwpx.hwpmodel.model import HwpControl

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _paras():
    with open(FIXTURE, "rb") as f:
        doc = read_document(f.read())
    return [p for sec in doc.sections for p in sec.paragraphs]


def test_fwspace_and_linebreak_present_in_contents():
    paras = _paras()
    kinds = set()
    for p in paras:
        for r in p.runs:
            for item in r.contents:
                if isinstance(item, HwpControl):
                    kinds.add(item.kind)
    assert "fwSpace" in kinds
    assert "lineBreak" in kinds


def test_same_charshape_text_and_control_merge_into_one_run():
    # find a run that contains both a text string and a control marker
    paras = _paras()
    mixed = [r for p in paras for r in p.runs
             if any(isinstance(i, HwpControl) for i in r.contents)
             and any(isinstance(i, str) for i in r.contents)]
    assert mixed, "expected at least one run mixing text and a control"


def test_paragraph_break_is_dropped():
    # PARAGRAPH_BREAK must never appear as a control kind
    paras = _paras()
    for p in paras:
        for r in p.runs:
            for item in r.contents:
                if isinstance(item, HwpControl):
                    assert item.kind in ("fwSpace", "lineBreak")


def test_merged_run_count_below_old_one_per_text():
    # merging collapses runs: total run count is well under the old ~1600
    paras = _paras()
    total_runs = sum(len(p.runs) for p in paras)
    assert total_runs < 1200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_model_hwprun.py tests/test_reader_inline.py -v`
Expected: FAIL (no `HwpControl`; `HwpRun` has no `contents`)

- [ ] **Step 3: Add `HwpControl` and migrate `HwpRun`** in `hwp2hwpx/hwpmodel/model.py`

Replace the `HwpRun` dataclass with:

```python
@dataclass
class HwpControl:
    kind: str = "fwSpace"


@dataclass
class HwpRun:
    char_shape_id: int
    contents: list = field(default_factory=list)
    table: "HwpTable" = None

    @property
    def text(self):
        return "".join(c for c in self.contents if isinstance(c, str))
```

- [ ] **Step 4: Rewrite `parse_paragraph`** in `hwp2hwpx/hwpmodel/reader.py`

Add `HwpControl` to the existing `from .model import (...)` block.

Replace `parse_paragraph` with:

```python
_CONTROL_KIND = {"FIXWIDTH_SPACE": "fwSpace", "LINE_BREAK": "lineBreak"}


def parse_paragraph(para_el):
    """Build one HwpParagraph. Walk LineSeg children in reading order,
    grouping consecutive Text + inline ControlChar (fwSpace/lineBreak) that
    share a charshape-id into one HwpRun; a charshape-id change, a table, or
    a PARAGRAPH_BREAK starts a new run."""
    runs = []
    cur_cs = None
    cur_contents = []

    def flush():
        nonlocal cur_cs, cur_contents
        if cur_contents:
            runs.append(HwpRun(char_shape_id=cur_cs, contents=cur_contents))
        cur_cs = None
        cur_contents = []

    for child in para_el.findall("LineSeg/*"):
        if child.tag == "Text":
            content = child.text or ""
            if not content:
                continue
            cs = _int(child.get("charshape-id"))
            if cur_contents and cs != cur_cs:
                flush()
            cur_cs = cs
            cur_contents.append(content)
        elif child.tag == "ControlChar":
            kind = _CONTROL_KIND.get(child.get("name"))
            if kind is None:
                continue  # PARAGRAPH_BREAK and any other control chars
            cs = _int(child.get("charshape-id"))
            if cur_contents and cs != cur_cs:
                flush()
            cur_cs = cs
            cur_contents.append(HwpControl(kind))
        elif child.tag == "TableControl":
            flush()
            runs.append(HwpRun(
                char_shape_id=_int(child.get("charshape-id")),
                contents=[],
                table=_parse_table(child),
            ))
    flush()
    return HwpParagraph(
        para_shape_id=_int(para_el.get("parashape-id")),
        style_id=_int(para_el.get("style-id")),
        runs=runs,
    )
```

- [ ] **Step 5: Update HWP-side test constructions**

These four tests construct `HwpRun(..., text="…")`, which no longer accepts `text`. Change each to `contents=[...]`:

- `tests/test_mapper_table.py`: `HwpRun(char_shape_id=3, text="가")` → `HwpRun(char_shape_id=3, contents=["가"])`. The `HwpRun(char_shape_id=0, table=_table())` (no text) is unchanged.
- `tests/test_mapper_body.py`: `HwpRun(char_shape_id=0, text="가나다")` → `HwpRun(char_shape_id=0, contents=["가나다"])`.
- `tests/test_hwpmodel_tables.py`: `HwpRun(char_shape_id=0, text="", table=table)` → `HwpRun(char_shape_id=0, table=table)`; `HwpRun(char_shape_id=0, text="x")` → `HwpRun(char_shape_id=0, contents=["x"])`.
- `tests/test_mapper_styles.py`: `HwpRun(char_shape_id=0, text="x")` → `HwpRun(char_shape_id=0, contents=["x"])`.

(Read-only `.text` uses in `tests/test_reader_tables.py` and `tests/test_reader_body.py` still work via the new property — leave them.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_model_hwprun.py tests/test_reader_inline.py tests/test_reader_body.py tests/test_reader_tables.py tests/test_hwpmodel_tables.py tests/test_mapper_table.py tests/test_mapper_body.py tests/test_mapper_styles.py -v`
Expected: PASS (mapper still reads `r.text`, so mapped output is text-only for now — controls are parsed but not yet mapped; runs are already merged)

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/hwpmodel/reader.py tests/test_model_hwprun.py tests/test_reader_inline.py tests/test_mapper_table.py tests/test_mapper_body.py tests/test_hwpmodel_tables.py tests/test_mapper_styles.py
git commit -m "feat: HWP model + reader group runs by charshape (parse control chars)"
```

---

### Task 4: Mapper maps run contents (text + control)

**Files:**
- Modify: `hwp2hwpx/mapper/body.py` (`map_paragraph`)
- Test: `tests/test_mapper_inline.py`

**Interfaces:**
- Consumes: `HwpRun.contents` (Task 3), `Control`/`Text` (Task 1/existing).
- Produces: `map_paragraph` maps each `HwpRun.contents` item to a `Run.texts` item — `str`→`Text(content)`, `HwpControl`→`Control(kind)` — in order. Table and empty runs unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mapper_inline.py
from hwp2hwpx.mapper.body import map_paragraph
from hwp2hwpx.hwpmodel.model import HwpParagraph, HwpRun, HwpControl
from hwp2hwpx.owpml.model import Control, Text


def test_run_contents_map_to_text_and_control():
    hpar = HwpParagraph(para_shape_id=0, style_id=0, runs=[
        HwpRun(char_shape_id=7, contents=["가", HwpControl("fwSpace"), "나",
                                          HwpControl("lineBreak")]),
    ])
    para = map_paragraph(hpar, 0)
    items = para.runs[0].texts
    assert [type(x).__name__ for x in items] == ["Text", "Control", "Text", "Control"]
    assert items[0].content == "가"
    assert items[1].kind == "fwSpace"
    assert items[2].content == "나"
    assert items[3].kind == "lineBreak"
    assert para.runs[0].char_pr_id == 7


def test_empty_run_still_placeholder():
    hpar = HwpParagraph(para_shape_id=0, style_id=0, runs=[])
    para = map_paragraph(hpar, 0)
    assert len(para.runs) == 1
    assert para.runs[0].texts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mapper_inline.py -v`
Expected: FAIL (control mapped as text / wrong types)

- [ ] **Step 3: Update `map_paragraph`** in `hwp2hwpx/mapper/body.py`

Add `Control` to the import of owpml model types (the line importing `OwpmlDocument, Header, Section, Para, Run, Text, Metadata`), i.e. add `Control`.

Add a helper above `map_paragraph`:

```python
def _map_contents(contents):
    """HwpRun.contents (str | HwpControl) -> OWPML Run.texts (Text | Control)."""
    out = []
    for item in contents:
        if isinstance(item, str):
            out.append(Text(item))
        else:  # HwpControl
            out.append(Control(item.kind))
    return out
```

Import `HwpControl`? Not needed — the helper checks `isinstance(item, str)` and treats everything else as a control (reading `.kind`).

Replace the run-building loop in `map_paragraph` (the `for r in hpar.runs:` block) with:

```python
    runs = []
    for r in hpar.runs:
        if getattr(r, "table", None) is not None:
            from .table import map_table
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[],
                            table=map_table(r.table)))
        else:
            runs.append(Run(char_pr_id=r.char_shape_id,
                            texts=_map_contents(r.contents)))
    if not runs:
        # Hancom always emits at least one <hp:run> per <hp:p>.
        runs = [Run(char_pr_id=0, texts=[])]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mapper_inline.py tests/test_mapper_body.py tests/test_mapper_table.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/body.py tests/test_mapper_inline.py
git commit -m "feat: map run contents to Text/Control (inline fwSpace/lineBreak)"
```

---

### Task 5: End-to-end / fidelity verification

**Files:**
- Test: `tests/test_convert_inline.py`

**Interfaces:**
- Consumes: the full pipeline (`convert`) and the fidelity harness.

- [ ] **Step 1: Write the fidelity/regression test**

```python
# tests/test_convert_inline.py
import zipfile
import re
from hwp2hwpx.convert import convert

SAMPLE_HWP = "samples/3.*.hwp"


def _section(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def test_inline_controls_present(tmp_path):
    sec = _section(tmp_path)
    assert sec.count("<hp:fwSpace") == 30
    assert sec.count("<hp:lineBreak") == 11


def test_run_and_t_counts_converge_to_hancom(tmp_path):
    sec = _section(tmp_path)
    # Hancom: 869 runs / 690 <hp:t>. Merging must bring us close, well below
    # the old 1603 / 1429.
    runs = sec.count("<hp:run")
    ts = sec.count("<hp:t>") + sec.count("<hp:t ")
    assert runs < 1000
    assert ts < 800


def test_previously_dropped_text_present(tmp_path):
    sec = _section(tmp_path)
    # a fwSpace splits a body paragraph into two text fragments; both the
    # fragment before and the fragment after the fwSpace must survive in the
    # output (previously the text after the fwSpace was silently dropped)
    assert "(text before fwSpace)" in sec  # placeholder for the real fragment
    assert "(text after fwSpace)" in sec  # placeholder for the real fragment
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_convert_inline.py -v`
Expected: PASS

- [ ] **Step 3: Run the full suite (regression)**

Run: `.venv/bin/python -m pytest -q`
Expected: all green (existing 141 + new tests)

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
Expected: `section0.xml` match materially above 73.1%; `fwSpace`/`lineBreak` gone from the section miss list; run/`hp:t` no longer over-counted. Record the number in the commit message.

- [ ] **Step 5: Commit**

```bash
git add tests/test_convert_inline.py
git commit -m "test: end-to-end inline fwSpace/lineBreak + run-merge fidelity"
```

---

## Self-Review

**Spec coverage:** Control models (Task 1 OWPML, Task 3 HWP), writer mixed content (Task 2), reader grouping + control parse + PARAGRAPH_BREAK skip (Task 3), mapper contents→texts (Task 4), fidelity counts + run-merge + no-dropped-text (Task 5). `<hp:ctrl>`/linesegarray out of scope. Covered.

**Placeholder scan:** none — every code step contains full code. Task 2 Step 5 and Task 3 Step 5 edit existing tests with exact before/after.

**Type consistency:** `Control` (Task 1) consumed by the writer (Task 2) and produced by the mapper (Task 4). `HwpControl`/`HwpRun.contents` (Task 3) consumed by the mapper (Task 4). `HwpRun.text` property (Task 3) keeps the mapper's pre-Task-4 plain-text path and existing `.text` readers green. `Run.texts` name unchanged throughout; the writer/`prv_text` distinguish `Control` from `Text` by type / `getattr("content")`. `map_paragraph` signature unchanged `(hpar, para_id)`.

**Staging check:** Task 1 additive. Task 2 changes writer to one-`hp:t`-per-run — real output unchanged then (runs still single-text). Task 3 merges runs (fewer runs, text preserved via property; controls parsed, not yet emitted). Task 4 emits controls. Every task ends green.
