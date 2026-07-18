# Preview Image Emission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `Preview/PrvImage.png` into the output `.hwpx` by copying the source `.hwp`'s `PrvImage` OLE stream, but only when that stream is already PNG.

**Architecture:** A thin extractor reads the source `PrvImage` stream via `hwp5proc cat` and returns its bytes iff they carry the PNG signature (else `None`). The bytes ride to the writer on a new optional `OwpmlDocument.prv_image` field; the writer emits the part only when it is present. No manifest changes — Hancom references `PrvImage.png` in neither `content.hpf` nor `container.xml`.

**Tech Stack:** Python 3.9, pyhwp (`hwp5proc`) for stream extraction, stdlib `subprocess`/`zipfile`, pytest.

## Global Constraints

- **Python 3.9 floor:** NO `X | None` unions — use `typing.Optional`. Use `field(default_factory=...)` for mutable dataclass defaults.
- **Run tests via `.venv/bin/python -m pytest`** — plain `python` lacks `hwp5proc`.
- **No new dependencies.** PNG-only by design specifically to avoid an imaging library. Do not add Pillow or any transcoding dependency.
- **Samples are private and git-ignored.** Never hard-code a sample's full Korean filename in committed code/comments; locate samples by number prefix via glob (e.g. `glob.glob("samples/3.*.hwp")[0]`). Refer to samples by number (3, 4, 2013).
- **Do not touch the manifest parts.** `content.hpf`, `container.xml`, `container.rdf`, `PrvText.txt` stay exactly as they are.
- **The PNG signature is exactly** `b"\x89PNG\r\n\x1a\n"` (8 bytes).

---

### Task 1: PNG-sniff predicate + preview extractor

**Files:**
- Modify: `hwp2hwpx/hwpmodel/bindata.py`
- Test: `tests/test_preview_image.py` (create)

**Interfaces:**
- Consumes: `_hwp5proc()` from `hwp2hwpx/hwpmodel/reader.py` (already imported in `bindata.py`); stdlib `subprocess` (already imported).
- Produces:
  - `_preview_png_or_none(data: bytes) -> Optional[bytes]` — returns `data` iff it starts with the PNG signature, else `None`.
  - `extract_preview_image(hwp_path: str) -> Optional[bytes]` — runs `hwp5proc cat <hwp_path> PrvImage`; returns the stream bytes iff PNG, else `None` (also `None` on non-zero exit).

- [ ] **Step 1: Write the failing unit tests for the sniff predicate**

Create `tests/test_preview_image.py`:

```python
import glob
import zipfile

from hwp2hwpx.hwpmodel.bindata import (
    _preview_png_or_none,
    extract_preview_image,
)

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def test_sniff_accepts_png():
    data = PNG_SIG + b"payload"
    assert _preview_png_or_none(data) == data


def test_sniff_rejects_gif():
    assert _preview_png_or_none(b"GIF89a....") is None


def test_sniff_rejects_bmp():
    assert _preview_png_or_none(b"BM\x00\x00....") is None


def test_sniff_rejects_empty():
    assert _preview_png_or_none(b"") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_preview_image.py -q`
Expected: FAIL with `ImportError` / `cannot import name '_preview_png_or_none'`.

- [ ] **Step 3: Implement the predicate and extractor**

In `hwp2hwpx/hwpmodel/bindata.py`, add near the top (after the existing imports) the signature constant, and append the two functions at the end of the file:

```python
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _preview_png_or_none(data):
    """Return `data` iff it is a PNG (by signature), else None."""
    return data if data.startswith(_PNG_SIGNATURE) else None


def extract_preview_image(hwp_path):
    """Return the source HWP's PrvImage stream bytes iff they are a PNG, else
    None.

    Hancom re-renders the preview at export, so this is a best-effort *usable*
    thumbnail, not a byte-match of Hancom's output. Non-PNG sources (GIF/BMP)
    are skipped because an honest transcode to .png would need an imaging
    dependency the project deliberately avoids.
    """
    proc = subprocess.run([_hwp5proc(), "cat", hwp_path, "PrvImage"],
                          capture_output=True)
    if proc.returncode != 0:
        return None
    return _preview_png_or_none(proc.stdout)
```

Note: `Optional` need not be imported here — the functions are untyped, matching the surrounding module style. The signature constant lives with the other module-level constants.

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_preview_image.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Add and run the real-sample integration tests**

Append to `tests/test_preview_image.py`:

```python
def test_extract_returns_png_for_png_source():
    hwp = glob.glob("samples/3.*.hwp")[0]
    data = extract_preview_image(hwp)
    assert data is not None
    assert data.startswith(PNG_SIG)


def test_extract_skips_non_png_source():
    # The 2013 sample's PrvImage stream is a GIF, not a PNG.
    hwp = glob.glob("samples/2013*.hwp")[0]
    assert extract_preview_image(hwp) is None
```

Run: `.venv/bin/python -m pytest tests/test_preview_image.py -q`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/bindata.py tests/test_preview_image.py
git commit -m "feat: PNG-sniffing preview-image extractor"
```

---

### Task 2: Model field + convert wiring + writer emission

**Files:**
- Modify: `hwp2hwpx/owpml/model.py:428-433` (the `OwpmlDocument` dataclass)
- Modify: `hwp2hwpx/convert.py`
- Modify: `hwp2hwpx/owpml/writer.py`
- Test: `tests/test_preview_image.py` (append), `tests/test_writer_endtoend.py` (append)

**Interfaces:**
- Consumes: `extract_preview_image` from Task 1; `OwpmlDocument` from `hwp2hwpx/owpml/model.py`; `write_hwpx(doc, out_path)` from `hwp2hwpx/owpml/writer.py`; `convert(hwp_path, out_path)` from `hwp2hwpx/convert.py`.
- Produces: `OwpmlDocument.prv_image: Optional[bytes] = None`; `write_hwpx` emits `Preview/PrvImage.png` iff `doc.prv_image is not None`.

- [ ] **Step 1: Write the failing writer unit tests**

Append to `tests/test_writer_endtoend.py` (it already imports `zipfile`, `write_hwpx`, and the model names; `_doc()` builds a minimal `OwpmlDocument`):

```python
def test_prv_image_emitted_when_present(tmp_path):
    out = tmp_path / "out.hwpx"
    doc = _doc()
    doc.prv_image = b"\x89PNG\r\n\x1a\npayload"
    write_hwpx(doc, str(out))
    with zipfile.ZipFile(out) as z:
        assert "Preview/PrvImage.png" in z.namelist()
        assert z.read("Preview/PrvImage.png") == b"\x89PNG\r\n\x1a\npayload"


def test_prv_image_absent_when_none(tmp_path):
    out = tmp_path / "out.hwpx"
    doc = _doc()  # prv_image defaults to None
    write_hwpx(doc, str(out))
    with zipfile.ZipFile(out) as z:
        assert "Preview/PrvImage.png" not in z.namelist()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_writer_endtoend.py -q`
Expected: FAIL — `test_prv_image_emitted_when_present` fails setting/emitting `prv_image` (field does not exist yet / part not written).

- [ ] **Step 3: Add the model field**

In `hwp2hwpx/owpml/model.py`, add the import at the top (after line 2, `from dataclasses import dataclass, field`):

```python
from typing import Optional
```

Then extend the `OwpmlDocument` dataclass (currently lines 428-433):

```python
@dataclass
class OwpmlDocument:
    header: Header
    sections: list
    metadata: Metadata
    bin_items: list = field(default_factory=list)
    prv_image: Optional[bytes] = None
```

- [ ] **Step 4: Emit the part in the writer**

In `hwp2hwpx/owpml/writer.py`, in `write_hwpx`, after the `parts = {...}` dict literal is built (immediately after the closing `}` of the dict, before the `for i, section ...` loop), insert:

```python
    if doc.prv_image is not None:
        parts["Preview/PrvImage.png"] = doc.prv_image
```

- [ ] **Step 5: Run the writer unit tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_writer_endtoend.py -q`
Expected: PASS (all, including the two new tests).

- [ ] **Step 6: Wire the extractor into `convert`**

In `hwp2hwpx/convert.py`, change the import line

```python
from .hwpmodel.bindata import extract_bin_items
```

to

```python
from .hwpmodel.bindata import extract_bin_items, extract_preview_image
```

and, immediately after `owpml_doc.bin_items = items`, add:

```python
    owpml_doc.prv_image = extract_preview_image(hwp_path)
```

- [ ] **Step 7: Write and run the convert-level integration tests**

Append to `tests/test_preview_image.py` (it already imports `glob`, `zipfile`, and defines `PNG_SIG`; add the import of `convert` at the top of the file):

```python
from hwp2hwpx.convert import convert


def test_convert_emits_preview_for_png_source(tmp_path):
    hwp = glob.glob("samples/3.*.hwp")[0]
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    with zipfile.ZipFile(out) as z:
        assert "Preview/PrvImage.png" in z.namelist()
        emitted = z.read("Preview/PrvImage.png")
    assert emitted == extract_preview_image(hwp)
    assert emitted.startswith(PNG_SIG)


def test_convert_skips_preview_for_non_png_source(tmp_path):
    hwp = glob.glob("samples/2013*.hwp")[0]
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    with zipfile.ZipFile(out) as z:
        assert "Preview/PrvImage.png" not in z.namelist()
```

Run: `.venv/bin/python -m pytest tests/test_preview_image.py -q`
Expected: PASS (8 passed).

- [ ] **Step 8: Run the full suite to confirm no regression**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — all previously-passing tests still pass, no other package part changed.

- [ ] **Step 9: Commit**

```bash
git add hwp2hwpx/owpml/model.py hwp2hwpx/owpml/writer.py hwp2hwpx/convert.py tests/test_preview_image.py tests/test_writer_endtoend.py
git commit -m "feat: emit Preview/PrvImage.png for PNG-source documents"
```

---

## Self-Review

- **Spec coverage:** Extractor + PNG sniff (Task 1) ✔; model field + convert wiring + conditional writer emission (Task 2) ✔; PNG-only skip behavior tested on both a PNG source (3) and a GIF source (2013) ✔; no manifest changes ✔; no new dependency ✔.
- **Placeholder scan:** none — every step carries the exact code/command/expected output.
- **Type consistency:** `extract_preview_image` / `_preview_png_or_none` defined in Task 1 and consumed by name in Task 2; `OwpmlDocument.prv_image` defined in Task 2 Step 3 and read in Step 4; `write_hwpx(doc, out_path)` and `convert(hwp_path, out_path)` signatures unchanged.
- **Non-goals honored:** no transcoding, no manifest edits, `PrvText.txt` untouched.
