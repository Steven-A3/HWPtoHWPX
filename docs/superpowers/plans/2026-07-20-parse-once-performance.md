# Parse-Once Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 6–10 `hwp5proc` subprocess spawns per conversion (plus rangetags' redundant re-open) with a single memoizing `HwpSource` that parses the HWP file once via pyhwp's in-process API — with zero change to conversion output.

**Architecture:** A new `HwpSource(hwp_path)` holds one `hwp5.xmlmodel.Hwp5File` and exposes memoized accessors (`xml`, `docinfo_models`, `section_models`, `section_names`, `stream_bytes`, `summary`, plus the underlying `Hwp5File` for rangetags). Every reader/bindata/summary/rangetags data access is refactored to consume it; `convert()` builds one source and threads it through. All `hwp5proc` subprocess calls are removed.

**Tech Stack:** Python 3.9, pyhwp (`hwp5.xmlmodel`/`hwp5.binmodel` API), lxml, pytest. No new dependencies.

## Global Constraints

- **Python 3.9 floor:** no `X | None` unions (use `typing.Optional`); `field(default_factory=...)` for mutable dataclass defaults.
- **Run tests via `.venv/bin/python -m pytest`** — plain `python` lacks pyhwp's console entry but the API is importable either way; keep using the venv.
- **No new dependencies.** Remove the `hwp5proc` *subprocess* usage; pyhwp stays a dependency (used via its API).
- **Samples are private/git-ignored.** Locate by prefix glob (`glob.glob("samples/3.*.hwp")[0]`, `4.*`, `★131008*`, `20131106*`); never hard-code full Korean filenames.
- **Output must not change.** The primary gate is byte-identical `.hwpx` output on all four samples. Any output change is a defect, not a "correction."
- **Three tested equivalence facts drive the gates:**
  - **V1 (XML):** in-process `Hwp5File.xmlevents().dump()` differs from `hwp5proc xml` only in (a) the `PropertySetStream` element (reader never consumes it from XML) and (b) attribute *ordering*. Outside `PropertySetStream` the trees are element-for-element identical (tags + attribute-value sets + text).
  - **V2 (streams):** `hwp5file[...].open().read()` equals `hwp5proc cat` for every stream (same code path). A naive `path.split('/')` walk raises `KeyError` on the control-char name `\x05HwpSummaryInformation`; only resolve the concrete paths we use (`BinData/<name>`, `PrvImage`) and return `None` for anything absent.
  - **V3 (memoization):** pyhwp accessors are lazy and do NOT cache — `xml()`/`models()` re-parse on every call. `HwpSource` MUST memoize each accessor's result so every underlying parse runs once.
- **API model dicts** have `type` as a **class** (use `model["type"].__name__ == "Paragraph"`, as `rangetags.py` already does — NOT the JSON string form `r.get("type") == "Paragraph"`), and `payload` as raw `bytes` (offset-68 read consumes it directly; no hex decode).

---

### Task 1: `HwpSource` (memoizing) + per-accessor equivalence tests

**Files:**
- Create: `hwp2hwpx/hwpmodel/source.py`
- Test: `tests/test_hwpsource.py`

**Interfaces:**
- Consumes: `hwp5.xmlmodel.Hwp5File`.
- Produces `HwpSource(hwp_path)` with:
  - `hwp5file` (property) — the underlying `Hwp5File`, opened once.
  - `xml() -> bytes` (memoized)
  - `docinfo_models() -> list` (memoized)
  - `section_names() -> list` — `BodyText/SectionN` names in order
  - `section_models(name) -> list` (memoized per name)
  - `stream_bytes(path) -> Optional[bytes]` (memoized per path; `None` if absent)
  - `summary() -> dict` — normalized fields matching `read_summary_info`'s output
  - Also `_as_source(x)` module helper: `x if isinstance(x, HwpSource) else HwpSource(x)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hwpsource.py`:

```python
import glob
import subprocess

from lxml import etree

from hwp2hwpx.hwpmodel.source import HwpSource, _as_source
from hwp2hwpx.hwpmodel.reader import _hwp5proc
from hwp2hwpx.hwpmodel.summary import read_summary_info

SAMPLES = ["samples/3.", "samples/4.", "samples/★131008", "samples/20131106"]


def _hwp(pre):
    return glob.glob(pre + "*.hwp")[0]


def _tree_key(root):
    # order-independent (tag, sorted-attrs, text) list, excluding PropertySetStream
    out = []
    def rec(el):
        if el.tag == "PropertySetStream":
            return
        out.append((el.tag, tuple(sorted(el.attrib.items())), (el.text or "").strip()))
        for c in el:
            rec(c)
    rec(root)
    return out


import pytest


@pytest.mark.parametrize("pre", SAMPLES)
def test_xml_tree_equivalent_to_cli(pre):
    hwp = _hwp(pre)
    api = HwpSource(hwp).xml()
    cli = subprocess.check_output([_hwp5proc(), "xml", hwp])
    assert _tree_key(etree.fromstring(api)) == _tree_key(etree.fromstring(cli))


@pytest.mark.parametrize("pre", SAMPLES)
def test_stream_bytes_equal_cli_cat(pre):
    hwp = _hwp(pre)
    src = HwpSource(hwp)
    ls = subprocess.run([_hwp5proc(), "ls", hwp], capture_output=True, text=True).stdout.split()
    targets = [s for s in ls if s.startswith("BinData/")] + ["PrvImage"]
    for name in targets:
        cli = subprocess.run([_hwp5proc(), "cat", hwp, name], capture_output=True).stdout
        assert src.stream_bytes(name) == cli, name


def test_stream_bytes_missing_returns_none():
    assert HwpSource(_hwp("samples/3.")).stream_bytes("BinData/BIN9999.bmp") is None


@pytest.mark.parametrize("pre", SAMPLES)
def test_summary_matches_subprocess(pre):
    hwp = _hwp(pre)
    assert HwpSource(hwp).summary() == vars(read_summary_info(hwp))


def test_section_models_type_is_class_name():
    src = HwpSource(_hwp("samples/3."))
    names = {m["type"].__name__ for m in src.section_models(src.section_names()[0])}
    assert "Paragraph" in names and "ParaCharShape" in names


def test_memoized_parse_runs_once(monkeypatch):
    src = HwpSource(_hwp("samples/3."))
    calls = {"xml": 0}
    real = src.hwp5file.xmlevents
    def counting(*a, **k):
        calls["xml"] += 1
        return real(*a, **k)
    monkeypatch.setattr(src.hwp5file, "xmlevents", counting)
    src.xml(); src.xml(); src.xml()
    assert calls["xml"] == 1


def test_as_source_passthrough():
    src = HwpSource(_hwp("samples/3."))
    assert _as_source(src) is src
    assert isinstance(_as_source(_hwp("samples/3.")), HwpSource)
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_hwpsource.py -q`
Expected: FAIL — `ModuleNotFoundError: hwp2hwpx.hwpmodel.source`.

- [ ] **Step 3: Implement `HwpSource`**

Create `hwp2hwpx/hwpmodel/source.py`:

```python
"""Single-parse, memoizing access to an HWP file via pyhwp's in-process API.

Replaces per-call `hwp5proc` subprocesses: one HwpSource opens the file once and
serves XML, models, streams, and summary from cached in-memory results.
"""
import io
from typing import Optional

from hwp5.xmlmodel import Hwp5File


# OLE SummaryInformation property ids used for title/subject (not exposed as
# HwpSummaryInfo attributes on all builds).
def _strip(v):
    return (v or "").strip()


def _fmt_ts(dt):
    # match read_summary_info: "YYYY-MM-DDThh:mm:ssZ", empty when absent
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class HwpSource:
    def __init__(self, hwp_path):
        self._path = hwp_path
        self._file = None
        self._xml = None
        self._docinfo_models = None
        self._section_models = {}
        self._streams = {}
        self._summary = None

    @property
    def hwp5file(self):
        if self._file is None:
            self._file = Hwp5File(self._path)
        return self._file

    def xml(self):
        if self._xml is None:
            buf = io.BytesIO()
            self.hwp5file.xmlevents().dump(buf)
            self._xml = buf.getvalue()
        return self._xml

    def docinfo_models(self):
        if self._docinfo_models is None:
            self._docinfo_models = list(self.hwp5file.docinfo.models())
        return self._docinfo_models

    def section_names(self):
        return list(self.hwp5file.bodytext)

    def section_models(self, name):
        if name not in self._section_models:
            self._section_models[name] = list(self.hwp5file.bodytext[name].models())
        return self._section_models[name]

    def stream_bytes(self, path):
        if path not in self._streams:
            self._streams[path] = self._read_stream(path)
        return self._streams[path]

    def _read_stream(self, path):
        node = self.hwp5file
        try:
            for part in path.split("/"):
                node = node[part]
            return node.open().read()
        except (KeyError, Exception):  # missing/unreadable stream -> caller skips
            return None

    def summary(self):
        if self._summary is None:
            si = self.hwp5file.summaryinfo
            self._summary = {
                "title": _strip(getattr(si, "title", "")),
                "creator": _strip(getattr(si, "author", "")),
                "subject": _strip(getattr(si, "subject", "")),
                "description": _strip(getattr(si, "comments", "")),
                "last_saved_by": _strip(getattr(si, "lastSavedBy", "")),
                "created_date": _fmt_ts(getattr(si, "createdTime", None)),
                "modified_date": _fmt_ts(getattr(si, "lastSavedTime", None)),
                "date": _strip(getattr(si, "dateString", "")),
                "keyword": _strip(getattr(si, "keywords", "")),
            }
        return self._summary


def _as_source(x):
    return x if isinstance(x, HwpSource) else HwpSource(x)
```

Note: `except (KeyError, Exception)` is redundant (`Exception` covers `KeyError`); write `except Exception:` — a missing/odd stream must yield `None`, never raise. If the summary field mapping or timestamp format does not match `read_summary_info` on a sample (the equivalence test will show the exact diff), adjust the mapping/format until `summary()` equals `vars(read_summary_info(hwp))` — that test is the arbiter, not this reference code.

- [ ] **Step 4: Run tests; iterate on summary until equivalence holds**

Run: `.venv/bin/python -m pytest tests/test_hwpsource.py -q`
Expected: PASS (all). If `test_summary_matches_subprocess` fails, read the assertion diff and fix the field mapping / `_fmt_ts` (e.g. timezone handling) so `summary()` matches the subprocess output exactly.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/hwpmodel/source.py tests/test_hwpsource.py
git commit -m "feat: memoizing in-process HwpSource with per-accessor equivalence tests"
```

---

### Task 2: Wire all consumers to `HwpSource`; remove subprocess; integration gates

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`, `hwp2hwpx/hwpmodel/bindata.py`, `hwp2hwpx/hwpmodel/summary.py`, `hwp2hwpx/hwpmodel/rangetags.py`, `hwp2hwpx/convert.py`
- Test: `tests/test_parse_once.py` (create)

**Interfaces:**
- Consumes: `HwpSource`, `_as_source` from Task 1.
- Produces: reader/bindata/summary/rangetags entry points accept an `HwpSource` (or a path, auto-wrapped via `_as_source`); `convert()` builds one `HwpSource` and passes it to all of them. No `subprocess`/`_hwp5proc` remains.

- [ ] **Step 1: Write the failing integration tests**

Create `tests/test_parse_once.py`:

```python
import glob
import os
import subprocess
import tempfile

import pytest

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

SAMPLES = ["samples/3.", "samples/4.", "samples/★131008", "samples/20131106"]

# Golden outputs captured from the pre-refactor converter (main). Regenerated in
# Step 2 below before the refactor so the comparison is against current behavior.


@pytest.mark.parametrize("pre", SAMPLES)
def test_convert_spawns_no_subprocess(pre, monkeypatch):
    hwp = glob.glob(pre + "*.hwp")[0]
    def boom(*a, **k):
        raise AssertionError("subprocess spawned: %r" % (a[0] if a else k))
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "check_output", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    with tempfile.TemporaryDirectory() as td:
        convert(hwp, os.path.join(td, "o.hwpx"))  # must succeed with no spawns


@pytest.mark.parametrize("pre", SAMPLES)
def test_output_matches_golden(pre):
    hwp = glob.glob(pre + "*.hwp")[0]
    golden = glob.glob(pre + "*.golden.hwpx")
    assert golden, "golden missing; regenerate per Step 2"
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "o.hwpx")
        convert(hwp, out)
        got = unzip_parts(out)
    want = unzip_parts(golden[0])
    assert set(got) == set(want)
    for part in want:
        assert got[part] == want[part], part
```

- [ ] **Step 2: Capture golden outputs from current (pre-refactor) converter**

Before changing any source, generate a golden `.hwpx` per sample from the CURRENT converter, so the refactor is gated against present behavior. Run:

```bash
.venv/bin/python - <<'PY'
import glob
from hwp2hwpx.convert import convert
for pre in ("samples/3.", "samples/4.", "samples/★131008", "samples/20131106"):
    hwp = glob.glob(pre + "*.hwp")[0]
    convert(hwp, hwp[:-4] + ".golden.hwpx")
print("goldens written")
PY
```

These `*.golden.hwpx` live under `samples/` (git-ignored with the rest of `samples/`), so they are test fixtures only, never committed. Run the golden test now to confirm it passes against the unchanged converter:

Run: `.venv/bin/python -m pytest tests/test_parse_once.py::test_output_matches_golden -q`
Expected: PASS (converter unchanged). `test_convert_spawns_no_subprocess` will still FAIL (subprocess present) until the refactor lands.

- [ ] **Step 3: Refactor `reader.py` to consume `HwpSource`**

In `hwp2hwpx/hwpmodel/reader.py`:
- Add `from .source import HwpSource, _as_source` and remove the `subprocess`/`json` imports once unused.
- Replace the subprocess bodies:

```python
def hwp5_xml(source):
    return _as_source(source).xml()


def hwp5_char_shapes(source):
    src = _as_source(source)
    out = []
    for name in src.section_names():
        pending = False
        for m in src.section_models(name):
            tname = m["type"].__name__
            if tname == "Paragraph":
                out.append(None); pending = True
            elif tname == "ParaCharShape" and pending:
                out[-1] = [tuple(pair) for pair in m["content"]["charshapes"]]
                pending = False
    return out


def hwp5_char_shape_border_fills(source):
    src = _as_source(source)
    return [_cs_border_fill(m["payload"])
            for m in src.docinfo_models() if m["type"].__name__ == "CharShape"]
```

- `_cs_border_fill(payload)` already reads `payload[68:70]`; since `payload` is now `bytes` directly, it is unchanged. Delete `_payload_bytes`, `_hwp5proc_models`, `_section_streams`, and `_hwp5proc` if they have no remaining callers (grep first).
- `read_docinfo`/`read_document` already take `xml_bytes`/`char_shapes`/`char_border_fills`; keep those signatures (they receive already-extracted data). `convert` will produce them from the shared source.

- [ ] **Step 4: Refactor `bindata.py`, `summary.py`, `rangetags.py`**

`bindata.py`:
```python
def _list_bindata_streams(source):
    src = _as_source(source)
    streams = {}
    for name in src.hwp5file["BinData"] if "BinData" in _bindata_dir(src) else []:
        base = name  # e.g. "BIN0001.bmp"
        if base.startswith("BIN"):
            try:
                streams[_stream_num(base)] = "BinData/" + base
            except ValueError:
                pass
    return streams
```
Use a small `_bindata_dir(src)` helper that returns the set of top-level storage names (`set(iter(src.hwp5file))`) so a document with no `BinData` folder yields `{}`. In `extract_bin_items(source, hwp_doc)`, replace the `cat` subprocess with `src.stream_bytes(stream)` (skip when `None`). In `extract_preview_image(source)`, replace the PrvImage `cat` with `src.stream_bytes("PrvImage")` and keep the PNG-signature sniff.

`summary.py`: replace `read_summary_info(source)`'s subprocess+text parse with `_as_source(source).summary()` returned as an `HwpSummaryInfo(**fields)`; drop the `_hwp5proc`/`subprocess` import and `_KEYS`/`_fmt_ts` text-parsing if now unused (the source already returns normalized fields).

`rangetags.py`: change the section-reader to take the shared source — `f = _as_source(source).hwp5file` instead of `Hwp5File(hwp_path)` — keeping the existing fail-safe try/except and `model["type"].__name__` logic.

- [ ] **Step 5: Thread one `HwpSource` through `convert.py`**

In `hwp2hwpx/convert.py`, build one source and pass it everywhere:

```python
def convert(hwp_path, out_path):
    from .hwpmodel.source import HwpSource
    src = HwpSource(hwp_path)
    xml = hwp5_xml(src)
    hwp_doc = read_document(xml, hwp5_char_shapes(src),
                            char_border_fills=hwp5_char_shape_border_fills(src))
    attach_range_tags(src, hwp_doc)
    hwp_doc.summary_info = read_summary_info(src)
    title = os.path.splitext(os.path.basename(hwp_path))[0]
    items, bin_index = extract_bin_items(src, hwp_doc)
    owpml_doc = map_document(hwp_doc, title=title, bin_index=bin_index)
    owpml_doc.bin_items = items
    owpml_doc.prv_image = extract_preview_image(src)
    write_hwpx(owpml_doc, out_path)
```

(`attach_range_tags`, `extract_bin_items`, `extract_preview_image`, `read_summary_info` now take a source; `title` still derives from `hwp_path`.)

- [ ] **Step 6: Update existing tests that call the refactored entry points with a path**

The refactored functions accept a path too (auto-wrapped via `_as_source`), so most existing tests keep working unchanged. Run the full suite and fix any that broke because they asserted on a removed helper (`_hwp5proc_models`, `_section_streams`, `_payload_bytes`) — rewrite them against `HwpSource` or delete if now covered by `tests/test_hwpsource.py`. Do not weaken any assertion; if a test encodes real behavior, port it.

- [ ] **Step 7: Run the integration gates + full suite**

Run: `.venv/bin/python -m pytest tests/test_parse_once.py tests/test_hwpsource.py -q`
Expected: PASS — including `test_convert_spawns_no_subprocess` (no spawns) and `test_output_matches_golden` (byte-identical).

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (full suite). If a test referenced a deleted subprocess helper, port or remove it per Step 6.

- [ ] **Step 8: Record the measured speedup + clean up goldens**

Measure and note before/after wall-clock in the task report:
```bash
.venv/bin/python - <<'PY'
import glob, time, tempfile, os
from hwp2hwpx.convert import convert
for pre in ("samples/3.", "samples/4."):
    hwp = glob.glob(pre + "*.hwp")[0]
    with tempfile.TemporaryDirectory() as td:
        t = time.perf_counter(); convert(hwp, os.path.join(td, "o.hwpx"))
        print(pre, "%.3fs" % (time.perf_counter() - t))
PY
rm -f samples/*.golden.hwpx
```
(The golden test regenerates goldens on demand per Step 2; they are not committed.)

- [ ] **Step 9: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py hwp2hwpx/hwpmodel/bindata.py hwp2hwpx/hwpmodel/summary.py hwp2hwpx/hwpmodel/rangetags.py hwp2hwpx/convert.py tests/test_parse_once.py
git commit -m "perf: parse HWP once via in-process HwpSource; remove hwp5proc subprocesses"
```

---

## Self-Review

- **Spec coverage:** memoizing `HwpSource` with all accessors (Task 1) ✔; V1 XML tree-equivalence gate ✔; V2 stream equivalence + missing→None + no general walker ✔; V3 memoization test (parse-once) ✔; wire all consumers + remove subprocess (Task 2) ✔; zero-subprocess gate ✔; byte-identical golden gate ✔; measured-speedup report ✔; summary field mapping with equivalence arbiter ✔.
- **Placeholder scan:** none — every step has exact code/commands/expected output. The `except (KeyError, Exception)` in the reference code is explicitly corrected to `except Exception:` in the note.
- **Type consistency:** `HwpSource`/`_as_source` defined in Task 1, consumed in Task 2; accessors return the shapes the reader/bindata/summary/rangetags code consumes (`model["type"].__name__`, `payload` bytes, `stream_bytes -> Optional[bytes]`, `summary() -> dict` matching `vars(read_summary_info(...))`).
- **Non-goals honored:** no output change (golden + zero-subprocess gates), no mapper/writer edits, no concurrency, no CLI/packaging.
