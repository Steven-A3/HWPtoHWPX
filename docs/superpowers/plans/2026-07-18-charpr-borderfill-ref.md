# Real charPr borderFillIDRef Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit each character shape's true border/fill reference (read from the `HWPTAG_CHAR_SHAPE` record) instead of the hardcoded `1`, so `charPr/@borderFillIDRef` matches Hancom.

**Architecture:** A new reader helper reads the border/fill id from payload offset 68 of each `CharShape` record (`hwp5proc models DocInfo`), threaded into `read_docinfo`/`read_document` under a length-equality guard, stored on `HwpCharShape`, and consumed by the mapper. The existing `normalize_borderfill_null` pass supplies the +1 for null-insert documents.

**Tech Stack:** Python 3.9, pyhwp (`hwp5proc`), lxml, pytest. Pure-Python; no new dependencies.

## Global Constraints

- **Python 3.9 floor:** no `X | None` unions; `field(default_factory=...)` for mutable dataclass defaults.
- **Run tests via `.venv/bin/python -m pytest`** — plain `python` lacks `hwp5proc`.
- **No new dependencies.**
- **Samples are private and git-ignored.** Locate samples by number/prefix glob (`glob.glob("samples/3.*.hwp")[0]`, `glob.glob("samples/4.*.hwp")[0]`, `glob.glob("samples/★131008*.hwp")[0]`); never hard-code full Korean filenames. Refer to samples by number/tag (3, 4, ★131008).
- **The border/fill id is a UINT16 little-endian at payload offset 68** of the `HWPTAG_CHAR_SHAPE` record (immediately after the four COLORREF color fields at bytes 52–67). Fall back to `1` for any payload shorter than 70 bytes.
- **Correlation guard:** assign the border-fill list to char shapes only when `len(list) == len(char_shapes)`; on mismatch, leave the model default (never misalign).
- **Section0 refs are untouched** — this change affects header `charPr` only.

---

### Task 1: Reader — payload border-fill reader + model field + plumbing

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (add field to `HwpCharShape`)
- Modify: `hwp2hwpx/hwpmodel/reader.py` (new helpers + `read_docinfo`/`read_document` params + assignment)
- Test: `tests/test_charpr_borderfill.py` (create)

**Interfaces:**
- Consumes: `_hwp5proc_models(hwp_path, stream)` (existing, in `reader.py`); `HwpCharShape` (in `model.py`); `read_docinfo(xml_bytes)` and `read_document(xml_bytes, char_shapes=None)` (existing signatures in `reader.py`).
- Produces:
  - `_payload_bytes(rec) -> bytes` — flatten a models record's `payload` (list of space-separated hex strings) to bytes.
  - `_cs_border_fill(payload) -> int` — `UINT16` LE at offset 68, or `1` if `len(payload) < 70`.
  - `hwp5_char_shape_border_fills(hwp_path) -> list` — per-`CharShape` border/fill id in index order.
  - `HwpCharShape.border_fill_id: int = 1`.
  - `read_docinfo(xml_bytes, char_border_fills=None)` and `read_document(xml_bytes, char_shapes=None, char_border_fills=None)` — new optional params.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_charpr_borderfill.py`:

```python
import glob

from lxml import etree

from hwp2hwpx.hwpmodel.reader import (
    _payload_bytes, _cs_border_fill, hwp5_char_shape_border_fills,
    read_docinfo, hwp5_xml,
)
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def test_payload_bytes_decodes_hex_chunks():
    rec = {"payload": ["01 02 03", "ff 00"]}
    assert _payload_bytes(rec) == bytes([1, 2, 3, 255, 0])


def test_cs_border_fill_reads_offset_68():
    payload = bytes(68) + bytes([5, 0]) + bytes(4)   # len 74, u16le at 68 == 5
    assert _cs_border_fill(payload) == 5


def test_cs_border_fill_short_payload_falls_back_to_one():
    assert _cs_border_fill(bytes(40)) == 1


def _hancom_charpr_refs(pre):
    ref = glob.glob(pre + "*.hwpx")[0]
    root = etree.fromstring(unzip_parts(ref)["Contents/header.xml"])
    return [int(cp.get("borderFillIDRef"))
            for cp in root.iter("{%s}charPr" % "http://www.hancom.co.kr/hwpml/2011/head")]


def test_border_fills_match_hancom_on_no_insert_doc():
    # sample 3 gets no null-insert, so the raw offset-68 ids equal Hancom's
    # charPr borderFillIDRef directly.
    hwp = glob.glob("samples/3.*.hwp")[0]
    got = hwp5_char_shape_border_fills(hwp)
    assert got == _hancom_charpr_refs("samples/3.")


def test_read_docinfo_assigns_when_lengths_match():
    hwp = glob.glob("samples/3.*.hwp")[0]
    xml = hwp5_xml(hwp)
    bfs = hwp5_char_shape_border_fills(hwp)
    di = read_docinfo(xml, char_border_fills=bfs)
    assert [cs.border_fill_id for cs in di.char_shapes] == bfs


def test_read_docinfo_ignores_on_length_mismatch():
    hwp = glob.glob("samples/3.*.hwp")[0]
    xml = hwp5_xml(hwp)
    di = read_docinfo(xml, char_border_fills=[7, 7, 7])  # wrong length
    assert all(cs.border_fill_id == 1 for cs in di.char_shapes)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_charpr_borderfill.py -q`
Expected: FAIL — `ImportError` on `_payload_bytes` / `_cs_border_fill` / `hwp5_char_shape_border_fills`, and `read_docinfo` has no `char_border_fills` kwarg.

- [ ] **Step 3: Add the model field**

In `hwp2hwpx/hwpmodel/model.py`, add to the `HwpCharShape` dataclass (immediately after the `shade_color` field, ~line 41):

```python
    border_fill_id: int = 1
```

- [ ] **Step 4: Add the reader helpers**

In `hwp2hwpx/hwpmodel/reader.py`, add near `_hwp5proc_models` (after `hwp5_char_shapes`):

```python
# The character shape's border/fill id is a UINT16 (little-endian) at payload
# offset 68 of HWPTAG_CHAR_SHAPE — right after the four COLORREF fields
# (text/underline/shade/shadow colors, bytes 52-67). pyhwp parses the record but
# does not surface this field, so we read it from the raw payload.
_CHAR_SHAPE_BORDER_FILL_OFFSET = 68


def _payload_bytes(rec):
    return bytes(int(b, 16)
                 for chunk in rec.get("payload", []) for b in chunk.split())


def _cs_border_fill(payload):
    off = _CHAR_SHAPE_BORDER_FILL_OFFSET
    if len(payload) < off + 2:
        return 1
    return int.from_bytes(payload[off:off + 2], "little")


def hwp5_char_shape_border_fills(hwp_path):
    """Per-CharShape border/fill id (1-based, HWPX-compatible), in CharShape
    index order, read from the raw HWPTAG_CHAR_SHAPE payloads."""
    recs = _hwp5proc_models(hwp_path, "DocInfo")
    return [_cs_border_fill(_payload_bytes(r))
            for r in recs if r.get("type") == "CharShape"]
```

- [ ] **Step 5: Thread the list into `read_docinfo` and `read_document`**

In `hwp2hwpx/hwpmodel/reader.py`, change the `read_docinfo` signature to accept the optional list, and assign it after the `char_shapes` list is built (just before `return HwpDocInfo(...)`, ~line 386):

```python
def read_docinfo(xml_bytes, char_border_fills=None):
    ...
    # (existing body that builds `char_shapes`, `para_shapes`, etc.)
    if char_border_fills and len(char_border_fills) == len(char_shapes):
        for cs, bf in zip(char_shapes, char_border_fills):
            cs.border_fill_id = bf
    return HwpDocInfo(fonts=fonts, char_shapes=char_shapes, ...)
```

And forward it from `read_document`:

```python
def read_document(xml_bytes, char_shapes=None, char_border_fills=None):
    docinfo = read_docinfo(xml_bytes, char_border_fills)
    ...
```

(Leave the rest of `read_document` unchanged.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_charpr_borderfill.py -q`
Expected: PASS (6 passed).

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/hwpmodel/reader.py tests/test_charpr_borderfill.py
git commit -m "feat: read char-shape border/fill id from HWPTAG_CHAR_SHAPE payload"
```

---

### Task 2: Mapper + convert wiring + fidelity gate

**Files:**
- Modify: `hwp2hwpx/mapper/char_pr.py` (use `cs.border_fill_id`)
- Modify: `hwp2hwpx/convert.py` (pass the list to `read_document`)
- Modify: `tests/test_mapper_charpr_full.py` (strengthen the pass-through test)
- Test: `tests/test_charpr_borderfill_fidelity.py` (create)

**Interfaces:**
- Consumes: `hwp5_char_shape_border_fills` and `read_document(..., char_border_fills=...)` from Task 1; `map_char_shapes` in `hwp2hwpx/mapper/char_pr.py`; `convert(hwp_path, out_path)` in `hwp2hwpx/convert.py`.
- Produces: `charPr/@borderFillIDRef` in `header.xml` derived from each char shape's real border/fill id.

- [ ] **Step 1: Write the failing fidelity test**

Create `tests/test_charpr_borderfill_fidelity.py`:

```python
import glob
import os
import tempfile

from lxml import etree

import pytest

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _charpr_refs(header_xml):
    root = etree.fromstring(header_xml)
    return [cp.get("borderFillIDRef") for cp in root.iter("{%s}charPr" % _HH)]


@pytest.mark.parametrize("pre", ["samples/3.", "samples/4.", "samples/★131008"])
def test_charpr_border_fill_refs_match_hancom(pre):
    hwp = glob.glob(pre + "*.hwp")[0]
    ref = glob.glob(pre + "*.hwpx")[0]
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.hwpx")
        convert(hwp, out)
        ours = unzip_parts(out)
    theirs = unzip_parts(ref)
    assert _charpr_refs(ours["Contents/header.xml"]) == \
        _charpr_refs(theirs["Contents/header.xml"])
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_charpr_borderfill_fidelity.py -q`
Expected: FAIL — ours are all `"1"`, Hancom's vary (mapper still hardcodes `1`; convert doesn't pass the list yet).

- [ ] **Step 3: Use the real id in the mapper**

In `hwp2hwpx/mapper/char_pr.py`, change the hardcoded line (~line 39):

```python
            border_fill_id=1,
```

to:

```python
            border_fill_id=cs.border_fill_id,
```

- [ ] **Step 4: Wire the list into `convert`**

In `hwp2hwpx/convert.py`, update the reader import to include the new helper:

```python
from .hwpmodel.reader import (
    hwp5_xml, hwp5_char_shapes, hwp5_char_shape_border_fills, read_document,
)
```

and pass it into `read_document` (the call currently reads `read_document(xml, hwp5_char_shapes(hwp_path))`):

```python
    hwp_doc = read_document(
        xml, hwp5_char_shapes(hwp_path),
        char_border_fills=hwp5_char_shape_border_fills(hwp_path),
    )
```

- [ ] **Step 5: Strengthen the existing mapper test**

In `tests/test_mapper_charpr_full.py`, `test_border_fill_id_is_one` (~line 30) currently asserts the mapper output is `1` from a default source. Replace it with a pass-through test that proves the mapper uses the source's value (keep whatever `_src()` helper the file already defines; set the field on the source instance):

```python
def test_border_fill_id_passes_through_from_source():
    src = _src()
    src.border_fill_id = 7
    assert map_char_shapes([src])[0].border_fill_id == 7
```

If `_src()` returns a shared/module-level object, construct a fresh `HwpCharShape` in the test instead so the mutation does not leak. Verify by reading the current `_src()` definition in that file before editing.

- [ ] **Step 6: Run the new + changed tests**

Run: `.venv/bin/python -m pytest tests/test_charpr_borderfill_fidelity.py tests/test_mapper_charpr_full.py -q`
Expected: PASS (fidelity: 3 passed; mapper file: all passed).

- [ ] **Step 7: Run the full suite; update any test that assumed the hardcoded 1**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS. If a pre-existing test asserted `charPr/@borderFillIDRef == "1"` or a mapped `border_fill_id == 1` that now reflects a real (non-1) value, update it to the correct value — these are legitimate corrections. Writer-only tests that construct their own `CharPr(border_fill_id=...)` are unaffected. If a test genuinely conflicts with the spec, stop and report it rather than forcing it green.

- [ ] **Step 8: Commit**

```bash
git add hwp2hwpx/mapper/char_pr.py hwp2hwpx/convert.py tests/test_mapper_charpr_full.py tests/test_charpr_borderfill_fidelity.py
git commit -m "feat: emit real charPr borderFillIDRef from char-shape border/fill id"
```

---

## Self-Review

- **Spec coverage:** payload reader + offset-68 + short-payload fallback (Task 1 `_payload_bytes`/`_cs_border_fill`/`hwp5_char_shape_border_fills`) ✔; model field ✔; length-guarded assignment in `read_docinfo` + forwarding from `read_document` ✔; mapper uses real id (Task 2) ✔; convert wiring ✔; null-insert +1 reused unchanged (no code) ✔; fidelity gate on 3/4/★131008 vs Hancom ✔; score-floor implied by full suite + attribute-only change ✔.
- **Placeholder scan:** none — every step has exact code/commands/expected output. (Step 5's `_src()` handling instructs the implementer to read the current definition before editing, which is a concrete directive, not a placeholder.)
- **Type consistency:** `hwp5_char_shape_border_fills`/`_payload_bytes`/`_cs_border_fill` defined in Task 1 and consumed in Task 2; `read_docinfo`/`read_document` new `char_border_fills` param defined in Task 1 and passed in Task 2; `HwpCharShape.border_fill_id` defined Task 1, read in Task 2's mapper.
- **Non-goals honored:** section0 refs untouched; no change to `substFont`, `paraPr`, `diagonal`, or fillBrush handling.
