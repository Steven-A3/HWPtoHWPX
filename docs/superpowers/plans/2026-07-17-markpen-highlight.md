# Text Highlighter (markpen) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit HWP text-highlighter (markpen) spans as Hancom's `<hp:markpenBegin color="…"/>`/`<hp:markpenEnd/>` inline markers inside `<hp:t>`, sourced from HWP paragraph range-tag records (`kind=2`).

**Architecture:** Extend the existing 4-layer pipeline. A new binmodel-based reader step (`hwpmodel/rangetags.py`) reads range tags pyhwp's XML dump omits and attaches `kind=2` spans to each `HwpParagraph` by depth-first paragraph index. A new mapper step (`mapper/markpen.py`) injects begin/end markers into the OWPML run text stream at the recorded character offsets. The writer emits them via the mixed-content mechanism `<hp:t>` already uses for inline controls.

**Tech Stack:** Python 3.9+ floor, pyhwp (`hwp5proc` CLI + `hwp5.xmlmodel.Hwp5File` binmodel API), lxml, pytest.

## Global Constraints

- **Python 3.9 floor:** never use `X | None`; use forward-ref-string annotations for dataclass defaults (`x: "T" = None`), `field(default_factory=list)` for mutable defaults. No new dependencies (pyhwp/lxml already present).
- **Tests run with `.venv/bin/python -m pytest`** — plain `python`/`python3` lacks `hwp5proc` and yields ~13 spurious failures. Every test command in this plan uses `.venv/bin/python -m pytest`.
- **Fidelity scoring is element-count per tag** (`matched = Σ min(our_count, their_count)`); attribute values do not affect score, so value correctness is guarded by unit tests and one exact-serialization assertion, not by the score.
- **markpen = range tag `kind==2` only.** `data` (bits 0–23) is the color; emit `color = "#%06X" % data`. Ignore all other `kind` values.
- **Marker placement at a run/item boundary:** `markpenBegin` attaches to the **start of the following** item/run; `markpenEnd` attaches to the **end of the preceding** item/run. At one gap, ends precede begins. (Verified against Hancom's sample-4 export.)
- **Both OWPML namespaces:** markpen markers are `hp:` (`_hp("markpenBegin")` / `_hp("markpenEnd")`).
- **Sample paths:** `samples/3.과업지시서_070.hwp` (no markpen — must stay byte-identical) and `samples/4.제안요청서_070.hwp` (5 markpen spans).

---

### Task 1: Models — HwpRangeTag, HwpParagraph.markpens, OWPML MarkpenBegin/MarkpenEnd

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py`
- Modify: `hwp2hwpx/owpml/model.py`
- Test: `tests/test_model_markpen.py` (Create)

**Interfaces:**
- Produces:
  - `HwpRangeTag(start: int = 0, end: int = 0, color: str = "#FFFFFF")` (hwpmodel)
  - `HwpParagraph.markpens: list` (new field, `field(default_factory=list)`)
  - `MarkpenBegin(color: str = "#FFFFFF")`, `MarkpenEnd()` (owpml model)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_markpen.py
from hwp2hwpx.hwpmodel.model import HwpRangeTag, HwpParagraph
from hwp2hwpx.owpml.model import MarkpenBegin, MarkpenEnd


def test_range_tag_fields():
    rt = HwpRangeTag(start=16, end=34, color="#FFFFFF")
    assert (rt.start, rt.end, rt.color) == (16, 34, "#FFFFFF")


def test_paragraph_markpens_default_is_independent_empty_list():
    a = HwpParagraph(para_shape_id=0)
    b = HwpParagraph(para_shape_id=0)
    a.markpens.append(HwpRangeTag(1, 2, "#FFFFFF"))
    assert a.markpens != b.markpens and b.markpens == []


def test_owpml_markpen_markers():
    assert MarkpenBegin(color="#00FF00").color == "#00FF00"
    assert MarkpenBegin().color == "#FFFFFF"
    MarkpenEnd()  # constructs with no args
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_markpen.py -v`
Expected: FAIL with `ImportError` (`HwpRangeTag` / `MarkpenBegin` not defined).

- [ ] **Step 3: Add the hwpmodel dataclasses**

In `hwp2hwpx/hwpmodel/model.py`, add near the other small dataclasses:

```python
@dataclass
class HwpRangeTag:
    start: int = 0
    end: int = 0
    color: str = "#FFFFFF"
```

And add a field to `HwpParagraph` (keep it consistent with the existing field style; place after the existing fields):

```python
    markpens: list = field(default_factory=list)
```

(`field` and `dataclass` are already imported in this module — confirm the import line already includes `field`; it is used elsewhere in the file.)

- [ ] **Step 4: Add the OWPML markers**

In `hwp2hwpx/owpml/model.py`, add near `Text`/`Control`:

```python
@dataclass
class MarkpenBegin:
    color: str = "#FFFFFF"


@dataclass
class MarkpenEnd:
    pass
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_markpen.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full suite (no regressions from a new field)**

Run: `.venv/bin/python -m pytest -q`
Expected: all pre-existing tests still pass (adding a defaulted field must not break anything).

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py tests/test_model_markpen.py
git commit -m "feat: markpen model — HwpRangeTag, HwpParagraph.markpens, OWPML MarkpenBegin/End"
```

---

### Task 2: Writer — emit markpenBegin/markpenEnd inside hp:t

**Files:**
- Modify: `hwp2hwpx/owpml/section_writer.py:21-45` (`_write_run`)
- Test: `tests/test_section_writer_markpen.py` (Create)

**Interfaces:**
- Consumes: `MarkpenBegin`, `MarkpenEnd` (Task 1).
- Produces: `_write_run` handles `MarkpenBegin`/`MarkpenEnd` items in `run.texts` exactly like `Control` — a `SubElement` of `hp:t` whose following text goes to its `.tail`.

**Why writer before mapper:** the writer must tolerate the new item types before the mapper ever emits them, so the suite never passes through a transient crash state (as happened when a mapper produced `Pic` before writer dispatch existed).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_section_writer_markpen.py
from lxml import etree
from hwp2hwpx.constants import NS
from hwp2hwpx.owpml.model import Para, Run, Text, MarkpenBegin, MarkpenEnd
from hwp2hwpx.owpml.section_writer import _write_run


def _run_xml(run):
    p = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"], "hc": NS["hc"]})
    _write_run(p, run, state=None)
    return etree.tostring(p, encoding="unicode")


def test_markpen_markers_emit_inside_t_with_tail_text():
    run = Run(char_pr_id=96, texts=[
        Text("낙찰, "), MarkpenBegin(color="#FFFFFF"),
        Text("계약체결"), MarkpenEnd(),
    ])
    xml = _run_xml(run)
    assert '<hp:markpenBegin color="#FFFFFF"/>' in xml
    assert '<hp:markpenEnd/>' in xml
    # text before the begin marker stays on hp:t; text after begin is its tail
    assert "낙찰, <hp:markpenBegin" in xml
    assert 'color="#FFFFFF"/>계약체결<hp:markpenEnd/>' in xml
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_section_writer_markpen.py -v`
Expected: FAIL — current `_write_run` treats non-`Control` items as `Text` and calls `.content`, raising `AttributeError` on `MarkpenBegin`.

- [ ] **Step 3: Implement marker handling in `_write_run`**

In `hwp2hwpx/owpml/section_writer.py`, update the import and the `run.texts` loop. Change the import line:

```python
from ..owpml.model import Control, Pic, MarkpenBegin, MarkpenEnd
```

Replace the body of the `if run.texts:` loop (lines ~24-38) so markers are handled alongside `Control`:

```python
    if run.texts:
        te = etree.SubElement(r, _hp("t"))
        last = None  # last inline child; text after it goes to its .tail
        for item in run.texts:
            if isinstance(item, Control):
                last = etree.SubElement(te, _hp(item.kind))
                if item.kind == "tab":
                    last.set("width", "0")
                    last.set("leader", "0")
                    last.set("type", "0")
            elif isinstance(item, MarkpenBegin):
                last = etree.SubElement(te, _hp("markpenBegin"))
                last.set("color", item.color)
            elif isinstance(item, MarkpenEnd):
                last = etree.SubElement(te, _hp("markpenEnd"))
            else:  # Text
                if last is None:
                    te.text = (te.text or "") + item.content
                else:
                    last.tail = (last.tail or "") + item.content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_section_writer_markpen.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (no mapper emits markers yet, so existing output is unchanged).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py tests/test_section_writer_markpen.py
git commit -m "feat: section writer emits markpenBegin/markpenEnd inside hp:t"
```

---

### Task 3: Mapper — apply_markpens injection + wire into map_paragraph

**Files:**
- Create: `hwp2hwpx/mapper/markpen.py`
- Modify: `hwp2hwpx/mapper/body.py:34-55` (`map_paragraph`)
- Test: `tests/test_mapper_markpen.py` (Create)

**Interfaces:**
- Consumes: OWPML `Run`, `Text`, `Control`, `MarkpenBegin`, `MarkpenEnd` (Task 1); `HwpRangeTag` (Task 1).
- Produces: `apply_markpens(runs: list, markpens: list) -> list` — mutates and returns `runs`, injecting markers into `run.texts`. No-op when `markpens` is empty or when any run carries a `table`/`drawing`.

**Char-width model (verified against sample 4):** offset advances by `len(item.content)` for a `Text` item and by `1` for a `Control` item. `markpenBegin(color)` is inserted at absolute offset `start`; `markpenEnd` at absolute offset `end`. At a gap that is an item boundary: begins lead the following item, ends trail the preceding item. At a gap strictly inside a `Text`, split the string and emit ends then begins.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_mapper_markpen.py
from hwp2hwpx.owpml.model import Run, Text, Control, MarkpenBegin, MarkpenEnd
from hwp2hwpx.hwpmodel.model import HwpRangeTag
from hwp2hwpx.mapper.markpen import apply_markpens


def _render(runs):
    """Flatten runs to a debug string: text, <B color>, <E>, <ctrl kind>."""
    out = []
    for r in runs:
        seg = []
        for it in r.texts:
            if isinstance(it, Text):
                seg.append(it.content)
            elif isinstance(it, MarkpenBegin):
                seg.append("<B %s>" % it.color)
            elif isinstance(it, MarkpenEnd):
                seg.append("<E>")
            elif isinstance(it, Control):
                seg.append("<c %s>" % it.kind)
        out.append("".join(seg))
    return out


def test_no_markpens_is_noop():
    runs = [Run(char_pr_id=1, texts=[Text("abcdef")])]
    apply_markpens(runs, [])
    assert _render(runs) == ["abcdef"]


def test_split_inside_single_text():
    # highlight chars [2:5] of "abcdef" -> ab <B> cde <E> f
    runs = [Run(char_pr_id=1, texts=[Text("abcdef")])]
    apply_markpens(runs, [HwpRangeTag(2, 5, "#FFFFFF")])
    assert _render(runs) == ["ab<B #FFFFFF>cde<E>f"]


def test_boundary_begin_leads_next_run_end_trails_prev_run():
    # two runs "abc"|"def"; span [3:5] -> begin at the run boundary (offset 3)
    # must lead run 2; end at offset 5 trails inside run 2.
    runs = [Run(char_pr_id=1, texts=[Text("abc")]),
            Run(char_pr_id=2, texts=[Text("def")])]
    apply_markpens(runs, [HwpRangeTag(3, 5, "#FFFFFF")])
    assert _render(runs) == ["abc", "<B #FFFFFF>de<E>f"]


def test_end_at_run_boundary_trails_preceding_run():
    # span [1:3] over runs "abc"|"def"; end at offset 3 (boundary) trails run 1.
    runs = [Run(char_pr_id=1, texts=[Text("abc")]),
            Run(char_pr_id=2, texts=[Text("def")])]
    apply_markpens(runs, [HwpRangeTag(1, 3, "#FFFFFF")])
    assert _render(runs) == ["a<B #FFFFFF>bc<E>", "def"]


def test_control_counts_as_width_one():
    # "ab" <tab> "cd"; the control is width 1, so offset 3 is the start of "cd".
    # Span [3:5] therefore highlights the whole "cd": begin leads it, end trails.
    runs = [Run(char_pr_id=1, texts=[Text("ab"), Control("tab"), Text("cd")])]
    apply_markpens(runs, [HwpRangeTag(3, 5, "#FFFFFF")])
    assert _render(runs) == ["ab<c tab><B #FFFFFF>cd<E>"]


def test_skips_paragraph_with_table_or_drawing_run():
    runs = [Run(char_pr_id=1, texts=[Text("abcdef")]),
            Run(char_pr_id=2, texts=[], table=object())]
    apply_markpens(runs, [HwpRangeTag(2, 5, "#FFFFFF")])
    assert _render(runs)[0] == "abcdef"  # unchanged: non-text run present
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_mapper_markpen.py -v`
Expected: FAIL — `hwp2hwpx.mapper.markpen` does not exist.

- [ ] **Step 3: Implement `apply_markpens`**

```python
# hwp2hwpx/mapper/markpen.py
"""Inject markpen (text-highlighter) markers into a paragraph's OWPML runs.

HWP stores highlighting as range-tag spans over paragraph character offsets
(kind=2). This walks the already-mapped OWPML runs, tracks a cumulative char
offset (a Text contributes its code-unit length, a Control contributes 1), and
inserts MarkpenBegin/MarkpenEnd markers at the span endpoints. At an item
boundary a begin leads the following item and an end trails the preceding one;
strictly inside a Text the string is split. Paragraphs containing a table or
drawing run are skipped (their runs have no text and no reliable char width)."""
from collections import defaultdict
from ..owpml.model import Text, MarkpenBegin, MarkpenEnd


def _has_non_text_run(runs):
    return any(getattr(r, "table", None) is not None
               or getattr(r, "drawing", None) is not None for r in runs)


def apply_markpens(runs, markpens):
    if not markpens or _has_non_text_run(runs):
        return runs
    begins = defaultdict(list)   # offset -> [color, ...]
    ends = defaultdict(int)      # offset -> count
    for mp in markpens:
        begins[mp.start].append(mp.color)
        ends[mp.end] += 1

    offset = 0
    for r in runs:
        new_texts = []
        for it in r.texts:
            width = len(it.content) if isinstance(it, Text) else 1
            # begins at the item-start gap lead this item
            for color in begins.pop(offset, []):
                new_texts.append(MarkpenBegin(color=color))
            if isinstance(it, Text):
                s = it.content
                prev = 0
                for k in range(1, width):        # strictly-internal gaps
                    g = offset + k
                    if g in ends or g in begins:
                        if k > prev:
                            new_texts.append(Text(s[prev:k]))
                        prev = k
                        for _ in range(ends.pop(g, 0)):
                            new_texts.append(MarkpenEnd())
                        for color in begins.pop(g, []):
                            new_texts.append(MarkpenBegin(color=color))
                if width > prev:
                    new_texts.append(Text(s[prev:]))
            else:
                new_texts.append(it)
            offset += width
            # ends at the item-end gap trail this item
            for _ in range(ends.pop(offset, 0)):
                new_texts.append(MarkpenEnd())
        r.texts = new_texts
    return runs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mapper_markpen.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Wire into `map_paragraph`**

In `hwp2hwpx/mapper/body.py`, add the import at the top:

```python
from .markpen import apply_markpens
```

In `map_paragraph`, after the `if not runs:` fallback block and before `return Para(...)`, apply markpens:

```python
    apply_markpens(runs, getattr(hpar, "markpens", []))
    return Para(id=para_id, para_pr_id=hpar.para_shape_id,
                style_id=hpar.style_id, runs=runs,
                line_segs=_map_line_segs(hpar.line_segs))
```

(`getattr` with a default keeps the mapper safe for any `HwpParagraph`-shaped input in existing tests that predates the field.)

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. `markpens` is still empty everywhere (reader not wired until Task 4), so `apply_markpens` is a no-op and output is unchanged.

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/mapper/markpen.py hwp2hwpx/mapper/body.py tests/test_mapper_markpen.py
git commit -m "feat: mapper injects markpen markers into run text stream"
```

---

### Task 4: Reader — extract range tags from binmodel and attach to paragraphs

**Files:**
- Create: `hwp2hwpx/hwpmodel/rangetags.py`
- Modify: `hwp2hwpx/convert.py`
- Test: `tests/test_reader_markpen.py` (Create)

**Interfaces:**
- Consumes: `HwpRangeTag` (Task 1); `HwpDocument`/`HwpSection`/`HwpParagraph`/`HwpRun` (existing); `hwp5.xmlmodel.Hwp5File` (pyhwp).
- Produces:
  - `extract_markpens(hwp_path) -> list[dict[int, list[HwpRangeTag]]]` — one dict per bodytext section: `{dfs_para_index: [HwpRangeTag, ...]}`, `kind==2` only.
  - `attach_range_tags(hwp_path, hwp_doc) -> None` — mutates `hwp_doc`, setting `paragraph.markpens` by DFS index; fail-safe on any error or per-section count mismatch.
- Wired: `convert()` calls `attach_range_tags(hwp_path, hwp_doc)` after `read_document` and before `map_document`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reader_markpen.py
import glob
import pytest
from hwp2hwpx.hwpmodel.reader import read_document, hwp5_xml
from hwp2hwpx.hwpmodel.rangetags import extract_markpens, attach_range_tags

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]


def _para_text(p):
    out = []
    for r in p.runs:
        for c in r.contents:
            if isinstance(c, str):
                out.append(c)
    return "".join(out)


def test_sample4_yields_five_white_markpen_spans():
    secs = extract_markpens(S4)
    spans = [s for buckets in secs for lst in buckets.values() for s in lst]
    assert len(spans) == 5
    assert all(s.color == "#FFFFFF" for s in spans)


def test_sample3_has_no_markpen():
    secs = extract_markpens(S3)
    assert all(len(buckets) == 0 for buckets in secs)


def test_attach_lands_on_correct_paragraphs():
    doc = read_document(hwp5_xml(S4))
    attach_range_tags(S4, doc)
    highlighted = [p for p in _dfs(doc.sections[0].paragraphs) if p.markpens]
    texts = [_para_text(p) for p in highlighted]
    assert any(t.startswith("2. 위 사업의 입찰") for t in texts)
    assert any(t.startswith("3. 또한 계약 체결과 이행") for t in texts)
    # total attached spans == 5
    assert sum(len(p.markpens) for p in highlighted) == 5


def test_attach_is_fail_safe_when_binmodel_unavailable(tmp_path):
    doc = read_document(hwp5_xml(S4))
    # a non-HWP path must not raise and must leave markpens empty
    attach_range_tags(str(tmp_path / "nope.hwp"), doc)
    assert all(not p.markpens for p in _dfs(doc.sections[0].paragraphs))


def _dfs(paras):
    for p in paras:
        yield p
        for run in p.runs:
            if getattr(run, "table", None) is not None:
                for row in run.table.table_rows:
                    for cell in row.cells:
                        yield from _dfs(cell.paragraphs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_reader_markpen.py -v`
Expected: FAIL — `hwp2hwpx.hwpmodel.rangetags` does not exist.

- [ ] **Step 3: Implement `rangetags.py`**

```python
# hwp2hwpx/hwpmodel/rangetags.py
"""Read HWP paragraph range-tag records (markpen highlighter) via pyhwp's
binmodel API and attach them to parsed paragraphs.

`hwp5proc xml` (the reader's main source) omits range tags entirely, so this is
the one reader path that reads the binary model directly. Only kind==2 tags
(the markpen highlighter) are kept; `data` is the RGB color. Range tags are
keyed by depth-first paragraph index, which matches the order the binmodel emits
`Paragraph` records (level 0 section paragraphs, level>=2 table-cell paragraphs)
and the order `read_document`/`parse_paragraph` build the parsed tree."""
from .model import HwpRangeTag

_MARKPEN_KIND = 2


def _dfs_paragraphs(paragraphs):
    """Parsed paragraphs in binmodel DFS order: a paragraph, then the cell
    paragraphs of each table it contains, recursively."""
    for para in paragraphs:
        yield para
        for run in para.runs:
            table = getattr(run, "table", None)
            if table is not None:
                for row in table.table_rows:
                    for cell in row.cells:
                        yield from _dfs_paragraphs(cell.paragraphs)


def extract_markpens(hwp_path):
    """One dict per bodytext section: {dfs_para_index: [HwpRangeTag, ...]}.
    kind==2 only. Returns [] on any read failure (fail-safe)."""
    try:
        from hwp5.xmlmodel import Hwp5File
        f = Hwp5File(hwp_path)
    except Exception:
        return []
    out = []
    try:
        for sec_name in f.bodytext:
            stream = f.bodytext[sec_name]
            buckets = {}
            para_idx = -1
            for model in stream.models():
                name = model["type"].__name__
                if name == "Paragraph":
                    para_idx += 1
                elif name == "ParaRangeTag":
                    spans = []
                    for rt in model["content"]["range_tags"]:
                        tag = rt["tag"]
                        if tag.kind == _MARKPEN_KIND:
                            spans.append(HwpRangeTag(
                                start=rt["start"], end=rt["end"],
                                color="#%06X" % tag.data))
                    if spans:
                        buckets.setdefault(para_idx, []).extend(spans)
            out.append(buckets)
    except Exception:
        return []
    return out


def attach_range_tags(hwp_path, hwp_doc):
    """Attach kind==2 range tags to hwp_doc paragraphs by DFS index. Fail-safe:
    on any error, or a per-section paragraph-count mismatch, that section's
    paragraphs keep empty `markpens` rather than risk mis-assignment."""
    sections_buckets = extract_markpens(hwp_path)
    if not sections_buckets:
        return
    for sec, buckets in zip(hwp_doc.sections, sections_buckets):
        flat = list(_dfs_paragraphs(sec.paragraphs))
        if not buckets:
            continue
        if max(buckets) >= len(flat):
            continue  # count/index mismatch -> skip this section, fail-safe
        for idx, spans in buckets.items():
            flat[idx].markpens = list(spans)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reader_markpen.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Wire into `convert()`**

In `hwp2hwpx/convert.py`, add the import and call `attach_range_tags` after `read_document`:

```python
from .hwpmodel.rangetags import attach_range_tags
```

```python
def convert(hwp_path, out_path):
    xml = hwp5_xml(hwp_path)
    hwp_doc = read_document(xml)
    attach_range_tags(hwp_path, hwp_doc)
    title = os.path.splitext(os.path.basename(hwp_path))[0]
    owpml_doc = map_document(hwp_doc, title=title)
    owpml_doc.bin_items = extract_bin_items(hwp_path, hwp_doc)
    write_hwpx(owpml_doc, out_path)
```

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. Sample 4 now emits markpen markers end-to-end; sample 3 unchanged.

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/hwpmodel/rangetags.py hwp2hwpx/convert.py tests/test_reader_markpen.py
git commit -m "feat: reader extracts markpen range tags from binmodel, attaches by DFS index"
```

---

### Task 5: End-to-end fidelity — markpen on sample 4, no-change guard on sample 3

**Files:**
- Test: `tests/test_convert_markpen.py` (Create)

**Interfaces:**
- Consumes: the full `convert()` pipeline (Tasks 1–4); `score_part`/`unzip_parts` fidelity helpers.

- [ ] **Step 1: Write the end-to-end tests**

```python
# tests/test_convert_markpen.py
import glob
import pytest
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]
S4_REF = glob.glob("samples/4.*.hwpx")[0]


def test_markpen_markers_leave_section_miss_list(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    assert missing.get("markpenBegin", 0) == 0
    assert missing.get("markpenEnd", 0) == 0


def test_markpen_exact_serialization_of_known_run(tmp_path):
    # The highlighted run for "계약체결 ... 준공" must serialize exactly as Hancom does.
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    xml = unzip_parts(str(out))["Contents/section0.xml"].decode("utf-8")
    assert ('<hp:markpenBegin color="#FFFFFF"/>계약체결 및 이행 등의 과정(준공'
            '<hp:markpenEnd/>') in xml


def test_section_match_rises_sample4(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    assert score_part(ours, theirs)["match"] > 0.992


def test_sample3_section_unchanged(tmp_path):
    # Sample 3 has no markpen; its section0.xml must be byte-identical to the
    # pre-milestone output (captured baseline sha256 acadcafbfd08135a, len 496492).
    out = tmp_path / "s3.hwpx"
    convert(S3, str(out))
    body = unzip_parts(str(out))["Contents/section0.xml"]
    import hashlib
    assert len(body) == 496492
    assert hashlib.sha256(body).hexdigest().startswith("acadcafbfd08135a")
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_convert_markpen.py -v`
Expected: PASS (4 tests). If `test_section_match_rises_sample4` or the exact-serialization test fails, the marker offsets are wrong — debug the char-width model in `apply_markpens` before proceeding.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (previous total + the new markpen tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_convert_markpen.py
git commit -m "test: end-to-end markpen on sample 4 + sample 3 no-change guard"
```

---

## Self-Review (author)

- **Spec coverage:** model (T1), writer (T2), mapper injection (T3), reader binmodel + correlation + convert wiring (T4), end-to-end fidelity + no-change guard (T5) — every spec section maps to a task.
- **Type consistency:** `HwpRangeTag(start,end,color)`, `HwpParagraph.markpens`, `MarkpenBegin(color)`/`MarkpenEnd`, `apply_markpens(runs, markpens)`, `extract_markpens(hwp_path)`, `attach_range_tags(hwp_path, hwp_doc)` — names identical across tasks.
- **Placeholders:** none; every code step carries verified code (extraction, correlation, and injection were each run against sample 4 and reproduce Hancom's serialization exactly; sample-3 baseline hash captured live).
- **Ordering:** models → writer → mapper → reader/convert → e2e avoids any transient crash state (writer tolerates the new items before the mapper emits them; the reader lights the feature up last).
