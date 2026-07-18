# Faithful Paragraph Segmentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the reader's paragraph run/`<t>` segmentation from the raw `HWPTAG_PARA_CHAR_SHAPE` char-position array so run grouping, char-shape assignment, and `<t>` structure match Hancom's `.hwpx` export.

**Architecture:** A new reader capability extracts per-paragraph `[position, charshape-id]` arrays via `hwp5proc models`. A char-width model maps array positions onto `LineSeg` items, resolving the char-shape of every item (including objects, which `hwp5proc xml` reports as `cs=None`). `parse_paragraph` is rewritten to build runs as maximal same-char-shape spans over an interleaved item stream. `HwpRun` becomes an ordered item list (multiple objects + text segments per run). Two gates gover: a structural differ (per-paragraph run/`<t>`/object match vs reference) and a score-floor (no per-part fidelity score may decrease).

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc`). Tests: `.venv/bin/python -m pytest`.

## Global Constraints

- **Python 3.9 floor:** no `X | None` unions (use `Optional[X]`); `field(default_factory=...)` for mutable dataclass defaults.
- **Tests run only via `.venv/bin/python -m pytest`** — plain `python` lacks `hwp5proc` (~13 spurious failures).
- **Score-floor invariant (hard gate):** no per-part fidelity score may decrease on any sample. Samples 3 & 4 section0 stay ≥ 1.0000; 2013 section0 must not drop below its current 0.9982.
- **Char-width model (verified):** Text = UTF-16 units `sum(2 if ord(c)>0xFFFF else 1 for c in s)`; ControlChar = 1; objects/extended-controls (`TableControl`, `GShapeObjectControl`, `ColumnsDef`, `PageNumberPosition`, `PageHide`, `NewNumbering`, `BookmarkControl`) = 8.
- **Fidelity scoring is element-count per tag; attribute values are score-invisible** — guard exact values with serialization unit tests, never the score.
- **samples/ are private, git-ignored** — never leak sample filenames/content into committed code or comments; refer to samples by number (3, 4, 2013) and paragraph index only.
- Category A (bullet-glyph paragraphs) and para-751 drawing internals are explicit non-goals; do not special-case them.

---

### Task 1: Char-shape extraction + width-model resolver

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`
- Test: `tests/test_char_shape_resolver.py` (create)

**Interfaces:**
- Produces: `hwp5_char_shapes(hwp_path) -> List[List[Tuple[int, int]]]` — per-paragraph `[(position, charshape_id), ...]` arrays in document (depth-first pre-order) order, all paragraphs (top-level and nested).
- Produces: `_item_width(tag, text) -> int` and `_resolve_item_char_shapes(items, char_shape_array) -> List[int]` where `items` is a list of `(tag, text_or_None, xml_charshape_or_None)` in `LineSeg` order; returns the resolved char-shape per item. Raises `AssertionError`-free — instead returns a `mismatches` count via a second return value for the consistency check: `_resolve_item_char_shapes(...) -> Tuple[List[int], int]`.

- [ ] **Step 1: Write the failing test for `hwp5_char_shapes`**

```python
# tests/test_char_shape_resolver.py
import glob
from hwp2hwpx.hwpmodel.reader import hwp5_char_shapes

S2013 = glob.glob("samples/2013*.hwp")[0]

def test_char_shapes_first_para_is_secpr_shape():
    arrs = hwp5_char_shapes(S2013)
    # para 0 (secPr): single position-0 segment, charshape 155
    assert arrs[0] == [(0, 155)]

def test_char_shapes_table_para_192_positions():
    # 192nd top-level para is a table-only paragraph: table at pos 0 (cs 46),
    # paragraph-break at pos 8 (cs 141). hwp5_char_shapes returns ALL paras
    # (incl. nested) in document order, so index != top-level index; assert the
    # array shape exists among returned arrays.
    arrs = hwp5_char_shapes(S2013)
    assert [(0, 46), (8, 141)] in arrs
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_char_shape_resolver.py -x -q`
Expected: FAIL (`hwp5_char_shapes` not defined).

- [ ] **Step 3: Implement `hwp5_char_shapes`**

Add near `hwp5_xml` in `reader.py`. It invokes `hwp5proc models` per section stream (`BodyText/Section0`, `Section1`, …), parses the JSON array, and walks records: each `{"type": "Paragraph"}` starts a new paragraph; the following `{"type": "ParaCharShape"}` supplies `content["charshapes"]` (a list of `[pos, cs]` pairs). Return them in stream order (document order).

```python
import subprocess, json

def _hwp5proc_models(hwp_path, stream):
    proc = subprocess.run([_hwp5proc(), "models", hwp_path, stream],
                          capture_output=True)
    return json.loads(proc.stdout)

def _section_streams(hwp_path):
    proc = subprocess.run([_hwp5proc(), "ls", hwp_path], capture_output=True, text=True)
    return sorted(s for s in proc.stdout.split() if s.startswith("BodyText/Section"))

def hwp5_char_shapes(hwp_path):
    """Per-paragraph [(position, charshape_id), ...] arrays in document order
    (all paragraphs, top-level and nested), from HWPTAG_PARA_CHAR_SHAPE."""
    out = []
    for stream in _section_streams(hwp_path):
        recs = _hwp5proc_models(hwp_path, stream)
        pending = False
        for r in recs:
            if r.get("type") == "Paragraph":
                out.append(None)
                pending = True
            elif r.get("type") == "ParaCharShape" and pending:
                out[-1] = [tuple(pair) for pair in r["content"]["charshapes"]]
                pending = False
    return out
```

Note: `_hwp5proc()` already exists in `reader.py` (returns the hwp5proc executable path). Reuse it.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_char_shape_resolver.py -x -q`
Expected: PASS.

- [ ] **Step 5: Write the failing width-model + resolver test**

```python
from hwp2hwpx.hwpmodel.reader import _item_width, _resolve_item_char_shapes

def test_item_widths():
    assert _item_width("Text", "abc") == 3
    assert _item_width("Text", "\U000f02b3 ") == 2   # BMP PUA + space
    assert _item_width("Text", "\U00010000") == 2    # supplementary -> 2 UTF-16
    assert _item_width("ControlChar", None) == 1
    assert _item_width("TableControl", None) == 8
    assert _item_width("GShapeObjectControl", None) == 8

def test_resolver_assigns_object_char_shape_from_array():
    # table (pos 0) then paragraph-break (pos 8): table -> 46, break -> 141
    items = [("TableControl", None, None), ("ControlChar", None, "141")]
    arr = [(0, 46), (8, 141)]
    shapes, mism = _resolve_item_char_shapes(items, arr)
    assert shapes == [46, 141]
    assert mism == 0

def test_resolver_consistency_across_samples():
    # Every Text/ControlChar item's array-looked-up cs must equal its xml cs.
    # 0 mismatches on samples 3 & 4; exactly 7 on 2013 (category-A bullet paras).
    import glob
    from hwp2hwpx.hwpmodel.reader import hwp5_xml, hwp5_char_shapes, _para_items
    from lxml import etree
    expected = {"3.": 0, "4.": 0, "2013": 7}
    for pre, exp in expected.items():
        hwp = glob.glob("samples/" + pre + "*.hwp")[0]
        root = etree.fromstring(hwp5_xml(hwp))
        arrs = hwp5_char_shapes(hwp)
        # walk paragraphs in the SAME document order hwp5_char_shapes uses
        total = 0
        cursor = [0]
        def walk(para_el):
            arr = arrs[cursor[0]]; cursor[0] += 1
            items = _para_items(para_el)
            _, m = _resolve_item_char_shapes(items, arr or [(0, 0)])
            nonlocal_total[0] += m
            # descend into nested paragraphs (table cells, textboxes) in order
            for nested in para_el.findall(".//Paragraph"):
                pass  # handled by document-order cursor in reader; see Step 7
        nonlocal_total = [0]
        for sec in root.findall(".//SectionDef"):
            for col in sec.findall("ColumnSet"):
                for p in col.findall("Paragraph"):
                    walk(p)
        # NOTE: nested-paragraph correlation is finalized in Task 3; this test
        # asserts top-level correlation only here.
        assert nonlocal_total[0] == exp, (pre, nonlocal_total[0])
```

If the nested-walk correlation is not yet wired, restrict this test to top-level paragraphs and assert the top-level mismatch counts (still 0/0/7). Finalize full-document correlation in Task 3.

- [ ] **Step 6: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_char_shape_resolver.py -x -q`
Expected: FAIL (`_item_width`/`_resolve_item_char_shapes`/`_para_items` not defined).

- [ ] **Step 7: Implement the width model + resolver + item extractor**

```python
_OBJECT_TAGS = {"TableControl", "GShapeObjectControl", "ColumnsDef",
                "PageNumberPosition", "PageHide", "NewNumbering",
                "BookmarkControl"}

def _item_width(tag, text):
    if tag == "Text":
        return sum(2 if ord(c) > 0xFFFF else 1 for c in (text or ""))
    if tag == "ControlChar":
        return 1
    return 8  # objects / extended controls

def _para_items(para_el):
    """(tag, text_or_None, xml_charshape_or_None) per LineSeg child, in order."""
    items = []
    for ls in para_el.findall("LineSeg/*"):
        if ls.tag == "Text":
            items.append(("Text", ls.text or "", ls.get("charshape-id")))
        else:
            items.append((ls.tag, None, ls.get("charshape-id")))
    return items

def _cs_at(arr, pos):
    cur = arr[0][1]
    for start, cs in arr:
        if start <= pos:
            cur = cs
        else:
            break
    return cur

def _resolve_item_char_shapes(items, arr):
    """Resolve each item's char-shape from the position array. Returns
    (shapes, mismatch_count). mismatch_count = items whose known xml charshape
    disagrees with the array (expected 0 except category-A bullet paras)."""
    shapes, mism, pos = [], 0, 0
    for tag, text, xml_cs in items:
        cs = _cs_at(arr, pos)
        shapes.append(cs)
        if xml_cs is not None and str(cs) != str(xml_cs):
            mism += 1
        pos += _item_width(tag, text)
    return shapes, mism
```

- [ ] **Step 8: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_char_shape_resolver.py -x -q`
Expected: PASS (0/0/7 consistency).

- [ ] **Step 9: Run full suite (no regressions — Task 1 adds only new code)**

Run: `.venv/bin/python -m pytest -q`
Expected: all prior tests still pass.

- [ ] **Step 10: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_char_shape_resolver.py
git commit -m "feat: extract PARA_CHAR_SHAPE arrays + width-model resolver"
```

---

### Task 2: Structural differ + score-floor gates (test infrastructure)

**Files:**
- Create: `tests/fidelity_struct.py` (helper module, not a test file itself)
- Test: `tests/test_paragraph_structure.py` (create)

**Interfaces:**
- Consumes: `hwp2hwpx.convert.convert`, `hwp2hwpx.fidelity.diff.score_part`, `hwp2hwpx.fidelity.xmlnorm.unzip_parts`.
- Produces: `paragraph_divergences(our_section_xml, their_section_xml) -> List[dict]` — per top-level paragraph, the run/`<t>`(empty vs non-empty)/object-sequence structure of ours vs theirs when they differ.
- Produces: `section_scores(hwp, ref) -> dict` mapping part → per-tag `missing` totals, for the score-floor assertion.

- [ ] **Step 1: Write `tests/fidelity_struct.py`**

Provide `_para_sig(p)` returning per-run `(charPrIDRef, [child-kinds])` with `t`/`t0` for non-empty/empty text; `paragraph_divergences(...)` aligning top-level `<hp:p>` by index and returning the differing ones; `section_scores(...)` returning the current per-part `missing` dict. (Reuse the census/differ logic already validated in Phase 0.)

- [ ] **Step 2: Write the baseline gate test (asserts CURRENT state — will tighten in Task 3)**

```python
# tests/test_paragraph_structure.py
import glob, tempfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

SAMPLES = {"3.": (0.0, 0.0), "4.": (0.0, 0.0), "2013": (7, 4)}  # (run_miss, t_miss) current

def _section_missing(hwp, ref):
    out = tempfile.mktemp(suffix=".hwpx"); convert(hwp, out)
    s = score_part(unzip_parts(out)["Contents/section0.xml"],
                   unzip_parts(ref)["Contents/section0.xml"])
    return s["missing"]

def test_score_floor_baseline():
    """Score-floor gate: section0 per-tag missing must not exceed current
    baseline on any sample. Task 3 tightens 2013's numbers downward."""
    for pre, (run_max, t_max) in SAMPLES.items():
        hwp = glob.glob("samples/" + pre + "*.hwp")[0]
        ref = glob.glob("samples/" + pre + "*.hwpx")[0]
        miss = _section_missing(hwp, ref)
        assert miss.get("run", 0) <= run_max, (pre, "run", miss.get("run"))
        assert miss.get("t", 0) <= t_max, (pre, "t", miss.get("t"))
```

- [ ] **Step 3: Run to verify it passes at baseline**

Run: `.venv/bin/python -m pytest tests/test_paragraph_structure.py -q`
Expected: PASS (documents the current baseline; becomes the ratchet).

- [ ] **Step 4: Commit**

```bash
git add tests/fidelity_struct.py tests/test_paragraph_structure.py
git commit -m "test: structural differ + score-floor gate for paragraph segmentation"
```

---

### Task 3: Interleaved-item run model + faithful `parse_paragraph`

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (HwpRun items)
- Modify: `hwp2hwpx/hwpmodel/reader.py` (`parse_paragraph`, `read_document` correlation)
- Modify: `hwp2hwpx/mapper/body.py` (`map_paragraph`)
- Modify: `hwp2hwpx/owpml/section_writer.py` (`_write_run`)
- Test: `tests/test_paragraph_structure.py` (tighten), `tests/test_char_shape_resolver.py` (full-document correlation)

**Interfaces:**
- Consumes: `hwp5_char_shapes`, `_resolve_item_char_shapes`, `_para_items` (Task 1).
- The `HwpRun` contents become an ordered list interleaving text strings, `HwpControl`s, and objects (table/drawing). A run may hold multiple objects.

**This is the behavior change. Both gates apply: the structural differ must show the score-visible categories match Hancom, and the score-floor must hold (no per-part score drop; samples 3 & 4 stay 1.0000).**

- [ ] **Step 1: Write the failing exact-structure tests for representative paragraphs**

Assert the resulting top-level paragraph structure (run char-shapes + child-kind sequence) for 2013 #192, S4 #336, S4 #337, 2013 #361 exactly matches the reference `.hwpx` (use `_para_sig` from `tests/fidelity_struct.py`). Example:

```python
def test_para_192_matches_hancom():
    # table-only paragraph -> [46: tbl][141: <t/>]
    ours, theirs = _top_para_sigs("2013", 192)
    assert ours == theirs
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_paragraph_structure.py -k para_192 -q`
Expected: FAIL (current output puts the table in its own `cs=0` run with a `t0` anchor).

- [ ] **Step 3: Change `HwpRun` to interleaved items (model.py)**

`HwpRun.contents` becomes the single ordered item list holding `str` (text), `HwpControl`, and object instances (table/drawing). Remove the separate single-object `table`/`drawing` fields (or keep them deprecated but unused). Update the dataclass and any constructors. Keep `char_shape_id`, `ctrls`, `ctrls_after`.

- [ ] **Step 4: Rewrite `parse_paragraph` to build runs from resolved char-shapes**

Algorithm:
1. `items = _para_items(para_el)` plus the parsed object payloads (table/drawing) attached per item.
2. `shapes, _ = _resolve_item_char_shapes(items, arr)` where `arr` is this paragraph's char-shape array (threaded in as a parameter).
3. Walk items with their resolved `shapes`, grouping maximal same-shape spans into runs. Within a run, accumulate an ordered contents list: text strings and inline controls form `<t>` spans; objects go inline; the paragraph-break contributes an (empty) text span, producing `<t/>` when the span is empty.
4. Extended controls (`PageHide`, `BookmarkControl`, `NewNumbering`) remain modeled as `ctrls`/`ctrls_after` OR as items in the stream — preserve their current placement semantics; verify via the differ.

`parse_paragraph(para_el, char_shape_array)` — new required parameter.

- [ ] **Step 5: Thread char-shape arrays through `read_document` (correlation)**

`read_document` calls `hwp5_char_shapes(hwp_path)` once, then feeds arrays to `parse_paragraph` in document order via a shared sequential cursor, descending into table cells and textbox paragraph lists in the same depth-first pre-order the models stream uses. `read_document` needs the `hwp_path` (add it as a parameter or thread the arrays in). Table-cell parsing (`_parse_table`) and textbox parsing (`_parse_drawing`) must advance the same cursor.

- [ ] **Step 6: Update `map_paragraph` (body.py) for interleaved contents**

Map the ordered item list to OWPML `Run` contents: text→`Text`, control→`Control`, object→mapped table/drawing, preserving order. A run may now carry multiple objects.

- [ ] **Step 7: Update `_write_run` (section_writer.py)**

Emit the interleaved contents directly: text spans as `<t>` (with inline tab/lineBreak/markpen children), objects inline between spans, empty spans as `<t/>`. Remove `_run_has_inline_object` (the empty `<t/>` now comes from the model, not a heuristic).

- [ ] **Step 8: Run the structural + score-floor gates**

Run: `.venv/bin/python -m pytest tests/test_paragraph_structure.py tests/test_char_shape_resolver.py -q`
Expected: representative-paragraph tests PASS; score-floor holds (samples 3 & 4 `run`/`t` missing = 0; 2013 `run`/`t` missing strictly ≤ baseline and reduced). Tighten `SAMPLES` in `test_score_floor_baseline` to the achieved 2013 numbers.

- [ ] **Step 9: Run full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. Investigate any exact-serialization test that changed; a changed run structure that improves the differ AND holds score is correct — update byte-exact expectations only where the new output matches Hancom's reference.

- [ ] **Step 10: Commit**

```bash
git add hwp2hwpx/ tests/
git commit -m "feat: faithful paragraph run segmentation from char-shape positions"
```

---

### Task 4: Lock-in tests + residual documentation

**Files:**
- Test: `tests/test_paragraph_structure.py` (finalize)
- Modify: `hwp2hwpx/hwpmodel/reader.py` (doc comment for category-A + para-751 residuals)

- [ ] **Step 1: Add the full-document structural regression test**

Assert, for all three samples, zero top-level paragraph divergence in the score-visible categories (run grouping, object sequence), with an explicit allowlist for the category-A bullet paragraphs (2013 #145, #149, #153, #215, #259, #279) documented as score-neutral residuals.

- [ ] **Step 2: Add the exact-serialization unit tests**

Byte-exact run/`<t>` structure vs Hancom reference for #192, #336, #337, #361 (if not already covered in Task 3).

- [ ] **Step 3: Document residuals in `reader.py`**

A concise comment on `parse_paragraph`/resolver noting: (a) category-A bullet paragraphs where `hwp5proc`'s xml char-shape attribution diverges from the raw array (score-neutral, left as-is); (b) para-751 drawing internals are out of scope.

- [ ] **Step 4: Run full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_paragraph_structure.py
git commit -m "test: lock faithful segmentation; document residuals"
```

---

## Self-Review Notes

- **Spec coverage:** Task 1 = extraction+resolver+widths; Task 2 = gates; Task 3 = model change + faithful segmentation + correlation + writer; Task 4 = lock-in + residuals. All spec sections covered.
- **Correlation risk:** the document-order cursor between `hwp5_char_shapes` and `parse_paragraph` (including nested paragraphs) is the highest-risk seam. The width-consistency check (`_resolve_item_char_shapes` mismatch count) is the built-in guard — a misaligned array yields mismatches far above the known 0/0/7, failing the Task 3 test loudly.
- **Model-change blast radius:** `HwpRun` contents change touches reader, mapper, writer. Task 3 lands them atomically; the score-floor + full-suite gates catch any silent regression.
