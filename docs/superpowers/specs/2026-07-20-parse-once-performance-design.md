# Parse-Once Performance — Design

**Goal:** Eliminate per-conversion subprocess overhead. Open the HWP file **once**
via pyhwp's in-process Python API and serve XML, models, streams, and summary
from that single object, instead of spawning 6–10 `hwp5proc` processes (plus a
redundant in-process re-open) that each re-parse the whole OLE file.

**Status:** design derived and feasibility-verified against all four sample
documents — including a byte-identical-output proof for the XML path.

---

## Problem

Every `convert()` currently spawns 6–10 `hwp5proc` subprocesses, each of which
starts a fresh Python interpreter, imports pyhwp, and re-parses the entire OLE
file. Measured: sample 3 = 1.17 s / 6 spawns, sample 4 = 1.65 s / 10 spawns. In
addition, `rangetags.py` already opens its **own** in-process
`hwp5.xmlmodel.Hwp5File` — a 7th independent parse of the same bytes.

Subprocess call sites (verified full sweep):
- `hwp2hwpx/hwpmodel/reader.py`: `models <stream>` (per section + DocInfo), `ls`.
- `hwp2hwpx/hwpmodel/bindata.py`: `ls`, `cat <BinData stream>` (per image), `cat PrvImage`.
- `hwp2hwpx/hwpmodel/summary.py`: `summaryinfo`.
- `hwp2hwpx/hwpmodel/rangetags.py`: opens its own `Hwp5File` (in-process, but redundant).

## Approach (decided: pure API, no subprocess fallback)

Introduce a single **`HwpSource`** opened once per `convert`, holding one
`hwp5.xmlmodel.Hwp5File`, and refactor every reader/bindata/summary/rangetags
access to consume it. Remove all `hwp5proc` subprocess calls. Dropping the
subprocess path also removes the `hwp5proc` binary as a runtime requirement
(a packaging simplification).

### Feasibility (verified)

- **XML — byte-identical output.** `Hwp5File.xmlevents().dump(buf)` produces XML
  that is *not* byte-identical to `hwp5proc xml` (formatting differs), but
  converting from it yields **byte-identical `.hwpx` output on all four samples**
  (the reader parses structurally). Proven this session.
- **Models — `payload` available as `bytes`.** `Hwp5File.docinfo.models()` and
  `.bodytext.section(n).models()` yield model dicts with keys `type`, `content`,
  `payload` (raw `bytes`, not the hex-string list the JSON CLI emits). The
  offset-68 charPr read and the `charshapes` position arrays both work directly
  (the API is actually simpler — no hex decode).
- **Streams — byte-identical `cat`.** `hwp5file[part][...].open().read()` returns
  bytes byte-identical to `hwp5proc cat` for `PrvImage` (16,632 B) and a BinData
  image (1,005,994 B), decompression included.
- **Summary — structured object.** `hwp5file.summaryinfo` is a `HwpSummaryInfo`
  with `author/comments/keywords/lastSavedBy/created&lastSaved times`. `title`
  and `subject` are **not** direct attributes; they live in `summaryinfo.propertySet`
  by OLE property id (PIDSI_TITLE=2, PIDSI_SUBJECT=3). This is the one accessor
  needing a field-mapping (or reuse of pyhwp's text dump); gated by an
  equivalence test.

## Architecture

- **New `hwp2hwpx/hwpmodel/source.py`** — `HwpSource(hwp_path)`:
  - Opens one `hwp5.xmlmodel.Hwp5File` (lazily/once).
  - `xml() -> bytes` — `xmlevents().dump()` into a buffer.
  - `docinfo_models() -> list` — list of model dicts.
  - `section_models(name) -> list` — per `BodyText/SectionN`.
  - `section_names() -> list` — BodyText/Section* storage names, in order.
  - `stream_bytes(path) -> bytes` — navigate storage, `.open().read()`. Returns
    `None` (or raises a typed error) for a missing stream so callers can skip.
  - `summary() -> HwpSummaryInfo`-equivalent fields (see summary mapping).
  - Serves repeated accesses from the single parsed object (no re-parse, no spawn).

- **`hwp2hwpx/hwpmodel/reader.py`** — `hwp5_xml`, `_hwp5proc_models`,
  `_section_streams`, `hwp5_char_shapes`, `hwp5_char_shape_border_fills` consume
  `HwpSource` instead of `subprocess.run(_hwp5proc(), ...)`. The offset-68 read
  uses `model["payload"]` directly (already `bytes`; drop the hex-flatten helper
  or make it accept bytes). Remove `_hwp5proc` if it has no remaining users.

- **`hwp2hwpx/hwpmodel/bindata.py`** — `_list_bindata_streams`, per-image `cat`,
  and `extract_preview_image` use `HwpSource.section_names()`/`stream_bytes`. The
  PrvImage PNG-signature sniff is unchanged (operates on the returned bytes).

- **`hwp2hwpx/hwpmodel/summary.py`** — read fields from `HwpSource.summary()`
  (property-id lookup for title/subject; direct attributes for the rest), mapping
  to the existing `HwpSummaryInfo` model fields and the existing timestamp
  formatting. Output must equal today's subprocess-parsed values.

- **`hwp2hwpx/hwpmodel/rangetags.py`** — take the shared `HwpSource` (or its
  underlying `Hwp5File`) instead of opening its own.

- **`hwp2hwpx/convert.py`** — construct one `HwpSource(hwp_path)` and pass it to
  the reader/bindata/summary/rangetags entry points.

## Testing & gates

- **Byte-identical output (primary gate):** for all four samples, the `.hwpx`
  produced after the refactor is byte-identical to the pre-refactor output
  (every zip part equal). Output must not change at all.
- **Per-accessor equivalence:** `HwpSource.xml()` parses to the same document;
  `stream_bytes` equals the old `cat` bytes for PrvImage + a BinData image;
  `docinfo_models`/`section_models` yield the same `content`/`payload` the offset-68
  and char-shape-position code consumes; `summary()` fields equal the old
  subprocess-parsed `HwpSummaryInfo`.
- **No subprocess remains:** a test asserts `convert()` spawns zero processes
  (e.g. patch `subprocess.Popen`/`run` to fail, or assert the `hwp5proc` call
  sites are gone).
- **Performance (informational):** record before/after wall-clock per sample in
  the final report (expected ~3× on sample 4). Not a hard threshold — the
  byte-identical gate is the guarantee; speed is the goal.
- **Full suite green** via `.venv/bin/python -m pytest`.

## Non-goals

- Any change to conversion output, mapper/writer logic, or fidelity behavior
  (the byte-identical gate forbids it).
- Algorithmic/parsing changes beyond replacing the data-access layer.
- Concurrency/parallelism (separate concern).
- CLI batch mode and packaging (their own sub-projects, next).

## Value

Removes 6–10 subprocess spawns + 1 redundant re-parse per conversion, replacing
them with a single in-process parse — an estimated ~3× speedup on the larger
sample (1.65 s → well under), with zero change to output, and drops the
`hwp5proc` binary as a runtime dependency.
