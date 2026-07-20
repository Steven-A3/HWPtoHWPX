# Trailing Empty `<hp:t>` for Inline-Object Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Append a trailing empty `<hp:t/>` inside a run that carries an inline (`treatAsChar=1`) object — a table (always inline in our output) or a drawing with `pos.treat_as_char == 1`.

**Architecture:** Writer-only. In `_write_run`, after the object dispatch, append an empty `<hp:t>` element when an inline object was written. No model/mapper change.

**Tech Stack:** Python 3.9+ floor, lxml, pytest.

## Global Constraints

- **Python 3.9 floor:** no `X | None`.
- **Tests run with `.venv/bin/python -m pytest`** — plain `python`/`python3` lacks `hwp5proc` (~13 spurious failures). Every command below uses `.venv/bin/python -m pytest`.
- **Fidelity scoring is element-count per tag** — the trailing empty `<hp:t>` adds one `t` element; extra `t` never lowers the score (`min(ours, theirs)`).
- **The rule:** in `_write_run`, after writing the object, append `etree.SubElement(r, _hp("t"))` iff the run carries a `table` OR a `drawing` whose `pos.treat_as_char == 1`. The empty `<hp:t>` is the run's last child.
- **Object runs have empty `texts`** (guaranteed by the reader/mapper), so the text branch never emits a `<hp:t>` for them — no double `<hp:t>`.
- **Samples:** `samples/3.*.hwp` (t 33 → 0) and `samples/4.*.hwp` (t 25 → 0). This milestone CHANGES sample 3's `section0.xml`.

---

### Task 1: Writer — trailing empty `<hp:t>` for inline-object runs

**Files:**
- Modify: `hwp2hwpx/owpml/section_writer.py` (add `_run_has_inline_object` helper; call it in `_write_run`)
- Test: `tests/test_section_writer_inline_t.py` (Create)

**Interfaces:**
- Consumes: OWPML `Run`, `Table`, `Pic`, `Line`, `ShapePos` (existing).
- Produces: `_run_has_inline_object(run) -> bool` (True for a table run or a drawing run with `pos.treat_as_char == 1`); `_write_run` appends a trailing empty `<hp:t/>` when it is True.

**Design note:** `_write_table`/`_write_pic` require fully-populated objects and a real `state`, so unit tests exercise the pure `_run_has_inline_object` decision (minimal objects, no serialization); the actual `<hp:t/>` serialization is covered end-to-end in Task 2.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_section_writer_inline_t.py
from hwp2hwpx.owpml.model import Run, Text, Table, Pic, Line, ShapePos
from hwp2hwpx.owpml.section_writer import _run_has_inline_object


def test_table_run_is_inline():
    assert _run_has_inline_object(Run(char_pr_id=0, texts=[], table=Table())) is True


def test_inline_pic_run_is_inline():
    run = Run(char_pr_id=0, texts=[], drawing=Pic(pos=ShapePos(treat_as_char=1)))
    assert _run_has_inline_object(run) is True


def test_floating_line_run_is_not_inline():
    run = Run(char_pr_id=0, texts=[], drawing=Line(pos=ShapePos(treat_as_char=0)))
    assert _run_has_inline_object(run) is False


def test_plain_text_run_is_not_inline():
    assert _run_has_inline_object(Run(char_pr_id=5, texts=[Text("가나다")])) is False


def test_drawing_with_no_pos_is_not_inline():
    run = Run(char_pr_id=0, texts=[], drawing=Pic(pos=None))
    assert _run_has_inline_object(run) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_section_writer_inline_t.py -v`
Expected: FAIL with `ImportError` — `_run_has_inline_object` does not exist yet.

- [ ] **Step 3: Implement the helper and call it in `_write_run`**

In `hwp2hwpx/owpml/section_writer.py`, add the helper near the top (after the `_hc` helper):

```python
def _run_has_inline_object(run):
    """True when the run carries an inline (treatAsChar=1) object — a table
    (always emitted inline) or a drawing whose pos.treat_as_char is 1. Such a
    run gets a trailing empty <hp:t/> anchor, matching Hancom."""
    if getattr(run, "table", None) is not None:
        return True
    d = getattr(run, "drawing", None)
    if d is not None:
        pos = getattr(d, "pos", None)
        return pos is not None and getattr(pos, "treat_as_char", 0) == 1
    return False
```

The current object dispatch in `_write_run` is:

```python
    if getattr(run, "table", None) is not None:
        _write_table(r, run.table, state)
    if getattr(run, "drawing", None) is not None:
        if isinstance(run.drawing, Pic):
            _write_pic(r, run.drawing)
        else:
            _write_line(r, run.drawing)
```

Append the anchor after it:

```python
    if getattr(run, "table", None) is not None:
        _write_table(r, run.table, state)
    if getattr(run, "drawing", None) is not None:
        if isinstance(run.drawing, Pic):
            _write_pic(r, run.drawing)
        else:
            _write_line(r, run.drawing)
    if _run_has_inline_object(run):
        # inline object anchor: Hancom writes a trailing empty <hp:t/> here.
        etree.SubElement(r, _hp("t"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_section_writer_inline_t.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full suite to see the expected sample-3 baseline break**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass EXCEPT `tests/test_convert_markpen.py::test_sample3_section_unchanged`, which now fails because sample 3's `section0.xml` legitimately changed (33 empty `<hp:t>` added). That is expected and is fixed in Task 2. If ANY OTHER test fails (e.g. a table/picture serialization test), stop and report it — it is not expected.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py tests/test_section_writer_inline_t.py
git commit -m "feat: writer emits trailing empty hp:t for inline-object runs"
```

---

### Task 2: End-to-end fidelity + re-baseline the sample-3 guard

**Files:**
- Modify: `tests/test_convert_markpen.py` (re-baseline `test_sample3_section_unchanged`)
- Test: `tests/test_convert_inline_t.py` (Create)

**Interfaces:**
- Consumes: the full `convert()` pipeline (Task 1); `score_part`/`unzip_parts`.

- [ ] **Step 1: Re-baseline the markpen sample-3 no-change guard**

This milestone changes sample 3's `section0.xml` (adds 33 empty `<hp:t>`), so the trailing-empty-run-era baseline is stale. In `tests/test_convert_markpen.py`, update `test_sample3_section_unchanged` to the new baseline (captured live: len 496827, sha256 prefix `022bef521a01b5c1`) and refresh its comment:

```python
def test_sample3_section_unchanged(tmp_path):
    # Sample 3 has no markpen. Baseline refreshed for the inline-object empty-<hp:t>
    # milestone (adds 33 inline-table anchor <hp:t>): sha256 022bef521a01b5c1,
    # len 496827. Still guards that markpen itself makes no further change.
    out = tmp_path / "s3.hwpx"
    convert(S3, str(out))
    body = unzip_parts(str(out))["Contents/section0.xml"]
    import hashlib
    assert len(body) == 496827
    assert hashlib.sha256(body).hexdigest().startswith("022bef521a01b5c1")
```

- [ ] **Step 2: Run the re-baselined test**

Run: `.venv/bin/python -m pytest tests/test_convert_markpen.py::test_sample3_section_unchanged -v`
Expected: PASS. If it fails, the actual bytes differ — print the real `len(body)` and `hashlib.sha256(body).hexdigest()` and use those EXACT values (do not weaken the assertion).

- [ ] **Step 3: Write the end-to-end fidelity tests**

```python
# tests/test_convert_inline_t.py
import glob
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]
S3_REF = glob.glob("samples/3.*.hwpx")[0]
S4_REF = glob.glob("samples/4.*.hwpx")[0]


def _section(hwp, tmp_path):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return unzip_parts(str(out))["Contents/section0.xml"]


def test_sample3_no_missing_t_and_match_rises(tmp_path):
    ours = _section(S3, tmp_path)
    theirs = unzip_parts(S3_REF)["Contents/section0.xml"]
    s = score_part(ours, theirs)
    assert s["missing"].get("t", 0) == 0
    assert s["match"] > 0.998


def test_sample4_no_missing_t_and_match_rises(tmp_path):
    ours = _section(S4, tmp_path)
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    s = score_part(ours, theirs)
    assert s["missing"].get("t", 0) == 0
    assert s["match"] > 0.999


def test_sample4_inline_pic_run_has_trailing_empty_t(tmp_path):
    # each inline <hp:pic> run ends with a bare <hp:t/> anchor.
    xml = _section(S4, tmp_path).decode("utf-8")
    assert "</hp:pic><hp:t/></hp:run>" in xml
```

- [ ] **Step 4: Run the end-to-end tests**

Run: `.venv/bin/python -m pytest tests/test_convert_inline_t.py -v`
Expected: PASS (3 tests). If `test_sample4_inline_pic_run_has_trailing_empty_t` fails, print the actual serialization around `</hp:pic>` and reconcile (the anchor must be a bare `<hp:t/>`; note lxml self-closes empty elements).

- [ ] **Step 5: Run the full suite (all green)**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, including the re-baselined markpen guard, the markpen marker tests, and the trailing-empty-run tests (unchanged).

- [ ] **Step 6: Commit**

```bash
git add tests/test_convert_inline_t.py tests/test_convert_markpen.py
git commit -m "test: end-to-end inline-object empty hp:t + re-baseline sample-3 guard"
```

---

## Self-Review (author)

- **Spec coverage:** writer rule + unit tests (Task 1); end-to-end fidelity + sample-3 re-baseline (Task 2). Every spec section maps to a task.
- **Type consistency:** `run.drawing.pos.treat_as_char` matches `ShapePos.treat_as_char`; `Pic`/`Line` both carry `pos`. `_write_run` appends via `etree.SubElement(r, _hp("t"))`.
- **Placeholders:** none; the rule and its effect were prototyped end-to-end (s3 0.9937→0.9988, s4 0.9963→0.9994; both `t` miss → 0) and the sample-3 baseline (496827 / 022bef521a01b5c1) captured live.
- **Regression handling:** the one expected break (markpen sample-3 byte-identity) is explicitly re-baselined in Task 2, not silently weakened; markpen marker + trailing-empty-run tests stay in the gate.
