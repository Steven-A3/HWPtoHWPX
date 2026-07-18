# Canonical Null-BorderFill Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a document's first `borderFill` is not Hancom's canonical null, prepend the canonical null at id=1 and shift every `borderFillIDRef` +1 — matching Hancom's reserved-null convention — while leaving conforming documents byte-identical.

**Architecture:** One document-level normalization pass `normalize_borderfill_null(doc)` in a new module `hwp2hwpx/mapper/borderfill_null.py`, called at the tail of `map_document` once the whole `OwpmlDocument` is assembled. It detects the canonical null at `border_fills[0]`; if absent, prepends it, renumbers borderFill ids, and offsets every `borderFillIDRef`-carrying field (`char_pr`, `para_pr`, `page_border_fill`, `table`, `cell`) by +1 via a recursive walk that reaches tables/cells nested in cells and in drawing text-boxes.

**Tech Stack:** Python 3.9, lxml, pytest. Pure-Python; no new dependencies.

## Global Constraints

- **Python 3.9 floor:** no `X | None` unions; `field(default_factory=...)` for mutable dataclass defaults.
- **Run tests via `.venv/bin/python -m pytest`** — plain `python` lacks `hwp5proc`.
- **No new dependencies.**
- **Samples are private and git-ignored.** Locate samples by number/prefix glob (`glob.glob("samples/3.*.hwp")[0]`, `glob.glob("samples/20131106*.hwp")[0]`, `glob.glob("samples/★131008*.hwp")[0]`); never hard-code full Korean filenames. Refer to samples by number/tag (3, 4, 2013, ★131008).
- **The canonical null (byte-exact):** four side borders `type="NONE"`; `diagonal` `type="SOLID" width="0.1 mm" color="#000000"`; no fill. Fed through the existing `header_writer` it serializes identically to Hancom's inserted id=1.
- **Uniform +1 on ALL refs** is required to preserve reference semantics after the insert (a ref to source-fill-k must still resolve to it, now at id k+1). It is NOT expected to make header refs match Hancom — `charPr` refs are a pre-existing hardcoded `1` and `paraPr` refs have a pre-existing sentinel divergence; both are score-neutral and OUT OF SCOPE. Only **section0** refs become byte-faithful to Hancom.
- **The offset must be exhaustive.** The ref-carrying fields are exactly (from the five `borderFillIDRef` writer emission sites): `header.char_prs[].border_fill_id`, `header.para_prs[].border_fill_id`, each section's `sec_pr.page_border_fills[].border_fill_id`, tables' `border_fill_id`, cells' `border_fill_id`. Tables/cells may be nested inside other cells and inside drawing text-boxes — the walk must recurse.

---

### Task 1: Detection + normalization pass (unit-tested on synthetic models)

**Files:**
- Create: `hwp2hwpx/mapper/borderfill_null.py`
- Test: `tests/test_borderfill_null.py`

**Interfaces:**
- Consumes: `BorderFill`, `Border`, `Table`, `Rect`, `Container` from `hwp2hwpx/owpml/model.py`. `OwpmlDocument` shape: `doc.header.border_fills` (list of `BorderFill(id, borders, fill_color, gradation)`), `doc.header.char_prs`/`para_prs` (each has `.border_fill_id`), `doc.sections` (each `Section` has `.sec_pr` which may be `None`; `sec_pr.page_border_fills` is a list of items with `.border_fill_id`; `.paras`). A `Para` has `.runs`; a `Run` has `.texts` (interleaved stream). A `Table` has `.border_fill_id` and `.rows`; a `TableRow` has `.cells`; a `Tc` (cell) has `.border_fill_id` and `.paras`. A `Rect` has `.draw_text` (may be `None`); `DrawText` has `.sub_list` (may be `None`); `SubList` has `.paras`. A `Container` has `.children` (a list of shapes).
- Produces:
  - `normalize_borderfill_null(doc) -> OwpmlDocument` — mutates and returns `doc`.
  - `_is_canonical_null(bf) -> bool`
  - `_canonical_null() -> BorderFill`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_borderfill_null.py`:

```python
from hwp2hwpx.owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Metadata,
    BorderFill, Border, Table, TableRow, Tc, Rect, DrawText, SubList, Container,
    CharPr, ParaPr, SecPr, PageBorderFill,
)
from hwp2hwpx.mapper.borderfill_null import (
    normalize_borderfill_null, _is_canonical_null, _canonical_null,
)


def _null_bf(id=1):
    return BorderFill(id=id, borders=[
        Border(kind="left", type="NONE", width="0.1 mm", color="#000000"),
        Border(kind="right", type="NONE", width="0.1 mm", color="#000000"),
        Border(kind="top", type="NONE", width="0.1 mm", color="#000000"),
        Border(kind="bottom", type="NONE", width="0.1 mm", color="#000000"),
        Border(kind="diagonal", type="SOLID", width="0.1 mm", color="#000000"),
    ], fill_color=None, gradation=None)


def _null_but_filled(id=1):
    bf = _null_bf(id)
    bf.fill_color = "#FF0000"
    return bf


def test_is_canonical_null_true():
    assert _is_canonical_null(_null_bf()) is True


def test_is_canonical_null_false_when_filled():
    assert _is_canonical_null(_null_but_filled()) is False


def test_is_canonical_null_false_when_side_border_present():
    bf = _null_bf()
    bf.borders[0].type = "SOLID"   # left border now visible
    assert _is_canonical_null(bf) is False


def test_canonical_null_matches_detector():
    assert _is_canonical_null(_canonical_null()) is True


def _doc(first_bf):
    # header: 2 borderFills; a charPr ref=1, a paraPr ref=2
    header = Header(
        border_fills=[first_bf, _null_bf(id=2)],
        char_prs=[CharPr(id=0, border_fill_id=1)],
        para_prs=[ParaPr(id=0, border_fill_id=2)],
    )
    # a top-level table (ref=1) whose cell (ref=2) holds a nested table (ref=1)
    nested_tbl = Table(border_fill_id=1, rows=[TableRow(cells=[Tc(border_fill_id=2)])])
    nested_para = Para(id=1, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[nested_tbl])])
    cell = Tc(border_fill_id=2, paras=[nested_para])
    tbl = Table(border_fill_id=1, rows=[TableRow(cells=[cell])])
    # a drawing text-box (Rect) whose nested para has a run with a table (ref=1)
    box_tbl = Table(border_fill_id=1, rows=[TableRow(cells=[Tc(border_fill_id=2)])])
    box_para = Para(id=2, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[box_tbl])])
    rect = Rect(draw_text=DrawText(sub_list=SubList(paras=[box_para])))
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[tbl, rect])])
    sec = Section(paras=[para],
                  sec_pr=SecPr(page_border_fills=[PageBorderFill(border_fill_id=1)]))
    return OwpmlDocument(header=header, sections=[sec], metadata=Metadata(title="t"))


def _all_refs(doc):
    refs = [cp.border_fill_id for cp in doc.header.char_prs]
    refs += [pp.border_fill_id for pp in doc.header.para_prs]
    for sec in doc.sections:
        refs += [p.border_fill_id for p in sec.sec_pr.page_border_fills]
    def walk(paras):
        for para in paras:
            for run in para.runs:
                for item in run.texts:
                    if isinstance(item, Table):
                        refs.append(item.border_fill_id)
                        for row in item.rows:
                            for c in row.cells:
                                refs.append(c.border_fill_id)
                                walk(c.paras)
                    elif isinstance(item, Rect) and item.draw_text and item.draw_text.sub_list:
                        walk(item.draw_text.sub_list.paras)
                    elif isinstance(item, Container):
                        pass
    for sec in doc.sections:
        walk(sec.paras)
    return refs


def test_noop_when_first_is_canonical():
    doc = _doc(_null_bf(id=1))
    before_count = len(doc.header.border_fills)
    before_refs = _all_refs(doc)
    normalize_borderfill_null(doc)
    assert len(doc.header.border_fills) == before_count
    assert _all_refs(doc) == before_refs


def test_insert_and_offset_when_first_not_canonical():
    doc = _doc(_null_but_filled(id=1))
    before_refs = _all_refs(doc)
    normalize_borderfill_null(doc)
    # a null was prepended and ids renumbered 1..N+1
    assert len(doc.header.border_fills) == 3
    assert _is_canonical_null(doc.header.border_fills[0])
    assert [bf.id for bf in doc.header.border_fills] == [1, 2, 3]
    # every ref shifted +1, none missed (incl. nested table/cell and drawing box)
    assert _all_refs(doc) == [r + 1 for r in before_refs]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_borderfill_null.py -q`
Expected: FAIL — `ModuleNotFoundError: hwp2hwpx.mapper.borderfill_null`.

- [ ] **Step 3: Implement the module**

Create `hwp2hwpx/mapper/borderfill_null.py`:

```python
"""Reproduce Hancom's reserved canonical-null borderFill at id=1.

Hancom guarantees the borderFill at id=1 is a canonical null (all side borders
NONE, a SOLID diagonal, no fill). When a document's first source borderFill is
not that, Hancom prepends the null and shifts every borderFillIDRef +1. This
pass reproduces that transform; documents whose first fill is already the
canonical null are left untouched.
"""
from ..owpml.model import BorderFill, Border, Table, Rect, Container


def _canonical_null():
    return BorderFill(
        id=1,
        borders=[
            Border(kind="left", type="NONE", width="0.1 mm", color="#000000"),
            Border(kind="right", type="NONE", width="0.1 mm", color="#000000"),
            Border(kind="top", type="NONE", width="0.1 mm", color="#000000"),
            Border(kind="bottom", type="NONE", width="0.1 mm", color="#000000"),
            Border(kind="diagonal", type="SOLID", width="0.1 mm", color="#000000"),
        ],
        fill_color=None,
        gradation=None,
    )


def _is_canonical_null(bf):
    by_kind = {b.kind: b for b in bf.borders}
    sides_none = all(by_kind.get(k) is not None and by_kind[k].type == "NONE"
                     for k in ("left", "right", "top", "bottom"))
    diag = by_kind.get("diagonal")
    diag_ok = (diag is not None and diag.type == "SOLID"
               and diag.width == "0.1 mm" and diag.color == "#000000")
    no_fill = (not bf.fill_color) and bf.gradation is None
    return sides_none and diag_ok and no_fill


def _offset_paras(paras, delta):
    for para in paras:
        for run in para.runs:
            for item in run.texts:
                _offset_item(item, delta)


def _offset_item(item, delta):
    if isinstance(item, Table):
        item.border_fill_id += delta
        for row in item.rows:
            for cell in row.cells:
                cell.border_fill_id += delta
                _offset_paras(cell.paras, delta)
    elif isinstance(item, Rect):
        if item.draw_text is not None and item.draw_text.sub_list is not None:
            _offset_paras(item.draw_text.sub_list.paras, delta)
    elif isinstance(item, Container):
        for child in item.children:
            _offset_item(child, delta)


def normalize_borderfill_null(doc):
    bfs = doc.header.border_fills
    if not bfs or _is_canonical_null(bfs[0]):
        return doc
    delta = 1
    doc.header.border_fills = [_canonical_null()] + list(bfs)
    for i, bf in enumerate(doc.header.border_fills):
        bf.id = i + 1
    for cp in doc.header.char_prs:
        cp.border_fill_id += delta
    for pp in doc.header.para_prs:
        pp.border_fill_id += delta
    for sec in doc.sections:
        if sec.sec_pr is not None:
            for pbf in sec.sec_pr.page_border_fills:
                pbf.border_fill_id += delta
        _offset_paras(sec.paras, delta)
    return doc
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_borderfill_null.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/borderfill_null.py tests/test_borderfill_null.py
git commit -m "feat: canonical null-borderFill normalization pass"
```

---

### Task 2: Wire into map_document + real-sample regression/fidelity gates

**Files:**
- Modify: `hwp2hwpx/mapper/body.py` (import + call at the tail of `map_document`)
- Test: `tests/test_borderfill_null_fidelity.py` (create)

**Interfaces:**
- Consumes: `normalize_borderfill_null` from Task 1; `map_document(hwp_doc, title, bin_index)` in `hwp2hwpx/mapper/body.py` (currently ends `return OwpmlDocument(header=header, sections=sections, metadata=metadata)`); `convert(hwp_path, out_path)` from `hwp2hwpx/convert.py`; `unzip_parts` from `hwp2hwpx/fidelity/xmlnorm.py`.
- Produces: `map_document` now returns a normalized document (null-inserted when the source first fill isn't canonical).

- [ ] **Step 1: Write the failing fidelity/regression tests**

Create `tests/test_borderfill_null_fidelity.py`:

```python
import glob
import re
import tempfile
import os

import pytest
from lxml import etree

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _convert(pre):
    hwp = glob.glob(pre + "*.hwp")[0]
    ref = glob.glob(pre + "*.hwpx")[0]
    td = tempfile.mkdtemp()
    out = os.path.join(td, "out.hwpx")
    convert(hwp, out)
    return unzip_parts(out), unzip_parts(ref)


def _local(t):
    return t.rsplit("}", 1)[-1]


def _count(xml, tag):
    root = etree.fromstring(xml)
    return sum(1 for e in root.iter() if _local(e.tag) == tag)


def _section0_refs(parts):
    return re.findall(rb'borderFillIDRef="(\d+)"', parts["Contents/section0.xml"])


NO_INSERT = ["samples/3.", "samples/4.", "samples/★131008"]


@pytest.mark.parametrize("pre", NO_INSERT)
def test_no_insert_docs_match_hancom_section0_refs(pre):
    ours, theirs = _convert(pre)
    # borderFill count equal, section0 refs byte-identical to Hancom (proves the
    # pass never misfires on a doc whose first fill is already the canonical null)
    assert _count(ours["Contents/header.xml"], "borderFill") == \
        _count(theirs["Contents/header.xml"], "borderFill")
    assert _section0_refs(ours) == _section0_refs(theirs)


def test_2013_inserts_null_and_section0_refs_match_hancom():
    ours, theirs = _convert("samples/20131106")
    o_bf = _count(ours["Contents/header.xml"], "borderFill")
    t_bf = _count(theirs["Contents/header.xml"], "borderFill")
    assert o_bf == t_bf == 68           # 67 source + 1 prepended null
    # id=1 is the canonical null: all side borders NONE, no fillBrush
    root = etree.fromstring(ours["Contents/header.xml"])
    bf1 = [e for e in root.iter() if _local(e.tag) == "borderFill"][0]
    kinds = [_local(c.tag) for c in bf1]
    assert "fillBrush" not in kinds
    for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
        el = next(c for c in bf1 if _local(c.tag) == side)
        assert el.get("type") == "NONE"
    # every section0 borderFillIDRef matches Hancom exactly
    assert _section0_refs(ours) == _section0_refs(theirs)
    assert len(_section0_refs(ours)) == 379
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_borderfill_null_fidelity.py -q`
Expected: FAIL — the 2013 test fails (`borderFill` count is 67, not 68; section0 refs are off by one) because the pass is not yet wired into `map_document`. The three NO_INSERT tests should already pass (current behavior already matches Hancom on those).

- [ ] **Step 3: Wire the pass into `map_document`**

In `hwp2hwpx/mapper/body.py`, add the import near the other mapper imports (alongside `from .border_fill import map_border_fills`):

```python
from .borderfill_null import normalize_borderfill_null
```

Then change the final line of `map_document` from:

```python
    return OwpmlDocument(header=header, sections=sections, metadata=metadata)
```

to:

```python
    doc = OwpmlDocument(header=header, sections=sections, metadata=metadata)
    return normalize_borderfill_null(doc)
```

- [ ] **Step 4: Run the fidelity tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_borderfill_null_fidelity.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full suite; update any test that encoded 2013's pre-insert state**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS. Only 2013's mapped/written output changed (borderFill 67→68, refs +1). If a pre-existing test encoded 2013's old borderFill count or old `borderFillIDRef` values at the mapped/written level, update it to the new correct (Hancom-matching) values — these are legitimate corrections, not regressions. Reader-level borderFill tests (e.g. `tests/test_reader_borderfills.py`, which asserts sample 3's count of 52 before mapping) are unaffected because this pass runs in the mapper, not the reader; do not change them. If a test genuinely conflicts with the spec, stop and report it rather than forcing it green.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/mapper/body.py tests/test_borderfill_null_fidelity.py
git commit -m "feat: apply null-borderFill normalization in map_document"
```

---

## Self-Review

- **Spec coverage:** canonical-null detection (Task 1 `_is_canonical_null`) ✔; byte-exact null construction (`_canonical_null`) ✔; conditional insert + id renumber + exhaustive +1 offset across char_pr/para_pr/page_border_fill/table/cell with recursion into nested cells and drawing text-boxes (Task 1 `normalize_borderfill_null` + `_offset_paras`/`_offset_item`) ✔; wiring at `map_document` tail (Task 2) ✔; no-op regression on 3/4/★131008 and insert + section0-matches-Hancom on 2013 (Task 2 tests) ✔; header refs NOT gated against Hancom (per spec Scope) ✔.
- **Placeholder scan:** none — every step carries exact code/commands/expected output.
- **Type consistency:** `normalize_borderfill_null`/`_is_canonical_null`/`_canonical_null` defined in Task 1 and consumed by name in Task 2; model field names (`border_fills`, `char_prs`, `para_prs`, `sec_pr.page_border_fills`, `Table.rows`, `TableRow.cells`, `Tc.paras`, `Rect.draw_text.sub_list.paras`, `Container.children`) match `hwp2hwpx/owpml/model.py`.
- **Non-goals honored:** no change to `<hc:diagonal>` emission, fillBrush distribution, or the pre-existing char_pr/para_pr header-ref mapping.
