# Trailing Empty Run (paragraph-mark char shape) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Append the trailing empty `<hp:run charPrIDRef=X/>` Hancom emits for a paragraph's mark (paragraph-break) char shape when it differs from the last visible run's shape.

**Architecture:** A reader-only change in `parse_paragraph`: capture the `PARAGRAPH_BREAK` control char's `charshape-id`, and after building the runs, append one empty `HwpRun` with that shape when it differs from the last contents-bearing run. The mapper and writer already turn an empty `HwpRun` into a bare `<hp:run charPrIDRef="X"/>`.

**Tech Stack:** Python 3.9+ floor, pyhwp `hwp5proc xml`, lxml, pytest.

## Global Constraints

- **Python 3.9 floor:** no `X | None`; the code below already complies.
- **Tests run with `.venv/bin/python -m pytest`** — plain `python`/`python3` lacks `hwp5proc` and yields ~13 spurious failures. Every command below uses `.venv/bin/python -m pytest`.
- **Fidelity scoring is element-count per tag** — a trailing empty run adds one `run` element and no `t`; extra runs never lower the score (`min(ours, theirs)` per tag).
- **The rule:** append a trailing empty run iff `break_cs is not None and last_cs is not None and break_cs != last_cs`, where `break_cs` = the `PARAGRAPH_BREAK` child's `charshape-id` (int) and `last_cs` = the char shape of the last run whose `contents` is non-empty. Never fires for empty paragraphs or table/drawing-terminated paragraphs.
- **Empty run shape:** `HwpRun(char_shape_id=break_cs, contents=[])` — the writer serializes a texts/table/drawing-less run as bare `<hp:run charPrIDRef="X"/>`.
- **Samples:** `samples/3.*.hwp` (gap 4 → 0) and `samples/4.*.hwp` (gap 36 → −2, over-emission score-neutral). This milestone legitimately CHANGES sample 3's `section0.xml`.

---

### Task 1: Reader — append trailing empty run for the paragraph-mark char shape

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py:435-498` (`parse_paragraph`)
- Test: `tests/test_reader_trailing_run.py` (Create)

**Interfaces:**
- Consumes: existing `HwpRun`, `HwpParagraph`, `_int`.
- Produces: `parse_paragraph` appends `HwpRun(char_shape_id=break_cs, contents=[])` per the rule.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reader_trailing_run.py
from lxml import etree
from hwp2hwpx.hwpmodel.reader import parse_paragraph


def _para(inner):
    xml = ('<Paragraph parashape-id="0" style-id="0"><LineSeg>%s</LineSeg>'
           '</Paragraph>' % inner)
    return parse_paragraph(etree.fromstring(xml))


def test_trailing_empty_run_appended_when_mark_shape_differs():
    p = _para('<Text charshape-id="40">가나다</Text>'
              '<ControlChar name="PARAGRAPH_BREAK" charshape-id="34" code="13" kind="CHAR"/>')
    assert len(p.runs) == 2
    assert p.runs[0].char_shape_id == 40 and p.runs[0].contents == ['가나다']
    assert p.runs[1].char_shape_id == 34 and p.runs[1].contents == []


def test_no_trailing_run_when_mark_shape_same():
    p = _para('<Text charshape-id="40">abc</Text>'
              '<ControlChar name="PARAGRAPH_BREAK" charshape-id="40" code="13" kind="CHAR"/>')
    assert len(p.runs) == 1
    assert p.runs[0].contents == ['abc']


def test_no_trailing_run_when_break_has_no_charshape():
    p = _para('<Text charshape-id="40">abc</Text>'
              '<ControlChar name="PARAGRAPH_BREAK" code="13" kind="CHAR"/>')
    assert len(p.runs) == 1


def test_no_trailing_run_for_table_terminated_paragraph():
    # a paragraph whose only run is a table run has no contents-bearing run;
    # last_cs is None, so no trailing empty run even if a break shape exists.
    inner = ('<TableControl charshape-id="7"><TableBody rows="1" cols="1" '
             'borderfill-id="1"><TableRow><TableCell col="0" row="0" '
             'colspan="1" rowspan="1" width="100" height="100" borderfill-id="1">'
             '</TableCell></TableRow></TableBody></TableControl>'
             '<ControlChar name="PARAGRAPH_BREAK" charshape-id="34" code="13" kind="CHAR"/>')
    p = _para(inner)
    assert all(r.contents == [] for r in p.runs)
    # exactly the table run, no appended empty text run
    assert len(p.runs) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_reader_trailing_run.py -v`
Expected: `test_trailing_empty_run_appended_when_mark_shape_differs` FAILS (only 1 run); the others may already pass. The key assertion is the append.

- [ ] **Step 3: Implement the rule in `parse_paragraph`**

In `hwp2hwpx/hwpmodel/reader.py`, add a `break_cs` accumulator and apply the rule after the final `flush()`.

Add the initializer next to the others (after `markpen_unsafe = False`):

```python
    break_cs = None
```

In the `ControlChar` branch, capture the paragraph-break char shape before the `continue`. Replace:

```python
            kind = _CONTROL_KIND.get(child.get("name"))
            if kind is None:
                continue  # PARAGRAPH_BREAK and any other control chars
```

with:

```python
            if child.get("name") == "PARAGRAPH_BREAK":
                v = child.get("charshape-id")
                break_cs = _int(v) if v is not None else None
            kind = _CONTROL_KIND.get(child.get("name"))
            if kind is None:
                continue  # PARAGRAPH_BREAK and any other control chars
```

After the final `flush()` (the one just before `return HwpParagraph(...)`), append the trailing empty run:

```python
    flush()
    last_cs = None
    for run in runs:
        if run.contents:
            last_cs = run.char_shape_id
    if break_cs is not None and last_cs is not None and break_cs != last_cs:
        runs.append(HwpRun(char_shape_id=break_cs, contents=[]))
    return HwpParagraph(
```

(Leave the rest of the `return HwpParagraph(...)` call unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reader_trailing_run.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full suite to see the expected sample-3 baseline break**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass EXCEPT `tests/test_convert_markpen.py::test_sample3_section_unchanged`, which now fails because sample 3's `section0.xml` legitimately changed (trailing empty runs added). That is expected and is fixed in Task 2. If ANY other test fails, stop and report it — it is not expected.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_trailing_run.py
git commit -m "feat: reader appends trailing empty run for paragraph-mark char shape"
```

---

### Task 2: End-to-end fidelity + re-baseline the sample-3 guard

**Files:**
- Modify: `tests/test_convert_markpen.py` (re-baseline `test_sample3_section_unchanged`)
- Test: `tests/test_convert_trailing_run.py` (Create)

**Interfaces:**
- Consumes: the full `convert()` pipeline (Task 1); `score_part`/`unzip_parts`.

- [ ] **Step 1: Re-baseline the markpen sample-3 no-change guard**

This milestone changes sample 3's `section0.xml` (adds ~4 trailing empty runs), so the markpen-era byte-identity baseline is now stale. In `tests/test_convert_markpen.py`, update `test_sample3_section_unchanged` to the new baseline (captured live from the implemented pipeline: len 496596, sha256 prefix `646b4403cb367cda`) and update its comment to say the baseline was refreshed for the trailing-empty-run milestone:

```python
def test_sample3_section_unchanged(tmp_path):
    # Sample 3 has no markpen. Baseline refreshed for the trailing-empty-run
    # milestone (adds ~4 paragraph-mark empty runs): sha256 646b4403cb367cda,
    # len 496596. This still guards that markpen itself makes no further change.
    out = tmp_path / "s3.hwpx"
    convert(S3, str(out))
    body = unzip_parts(str(out))["Contents/section0.xml"]
    import hashlib
    assert len(body) == 496596
    assert hashlib.sha256(body).hexdigest().startswith("646b4403cb367cda")
```

- [ ] **Step 2: Run the re-baselined test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_convert_markpen.py::test_sample3_section_unchanged -v`
Expected: PASS. If it fails, the actual bytes differ from the plan's baseline — print the real `len` and `hashlib.sha256(body).hexdigest()` and use those exact values (do NOT weaken the assertion to a substring of a guessed value).

- [ ] **Step 3: Write the end-to-end fidelity tests**

```python
# tests/test_convert_trailing_run.py
import glob
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]
S4_REF = glob.glob("samples/4.*.hwpx")[0]
S3_REF = glob.glob("samples/3.*.hwpx")[0]


def _section(hwp, tmp_path):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return unzip_parts(str(out))["Contents/section0.xml"]


def test_sample4_no_missing_runs(tmp_path):
    ours = _section(S4, tmp_path)
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    assert score_part(ours, theirs)["missing"].get("run", 0) == 0


def test_sample4_known_paragraph_gains_trailing_empty_run(tmp_path):
    # a known single-word paragraph in sample 4 gains a trailing bare
    # <hp:run charPrIDRef="34"/> right after its own closing </hp:t>
    xml = _section(S4, tmp_path).decode("utf-8")
    assert '</hp:t></hp:run><hp:run charPrIDRef="34"/>' in xml


def test_sample4_section_match_rises(tmp_path):
    ours = _section(S4, tmp_path)
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    assert score_part(ours, theirs)["match"] > 0.996


def test_sample3_no_missing_runs_and_match_rises(tmp_path):
    ours = _section(S3, tmp_path)
    theirs = unzip_parts(S3_REF)["Contents/section0.xml"]
    s = score_part(ours, theirs)
    assert s["missing"].get("run", 0) == 0
    assert s["match"] > 0.9937
```

- [ ] **Step 4: Run the end-to-end tests**

Run: `.venv/bin/python -m pytest tests/test_convert_trailing_run.py -v`
Expected: PASS (4 tests). If `test_sample4_known_paragraph_gains_trailing_empty_run` fails, the serialization differs — print the actual substring around that known paragraph's closing `</hp:t>` and reconcile (the run must be bare, no `<hp:t>`).

- [ ] **Step 5: Run the full suite (all green now)**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass, including the re-baselined markpen guard and the markpen `markpenBegin`/`markpenEnd` tests (unchanged).

- [ ] **Step 6: Commit**

```bash
git add tests/test_convert_trailing_run.py tests/test_convert_markpen.py
git commit -m "test: end-to-end trailing empty run + re-baseline sample-3 guard"
```

---

## Self-Review (author)

- **Spec coverage:** reader rule + unit tests (Task 1); end-to-end fidelity + sample-3 re-baseline (Task 2). Every spec section maps to a task.
- **Type consistency:** `break_cs`/`last_cs` are ints or `None`; `HwpRun(char_shape_id=…, contents=[])` matches the existing constructor used elsewhere in the reader.
- **Placeholders:** none; the rule and its measured effect were prototyped end-to-end (s4 0.9924→0.9963, s3 0.9932→0.9937) and the sample-3 baseline (496596 / 646b4403cb367cda) was captured live.
- **Regression handling:** the one expected break (markpen sample-3 byte-identity) is explicitly re-baselined in Task 2, not silently weakened; the markpen marker tests stay in the gate.
