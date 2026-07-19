# Parse-Once Performance — Design (v2, skeptic-hardened)

**Goal:** Eliminate per-conversion subprocess overhead. Open the HWP file **once**
via pyhwp's in-process Python API and serve XML, models, streams, and summary
from a single **memoizing** `HwpSource`, instead of spawning 6–10 `hwp5proc`
processes (plus a redundant in-process re-open) that each re-parse the whole file.

**Status:** design derived and adversarially verified. Three vulnerabilities were
identified and empirically tested (below); the design is revised to address each.

---

## Problem

Every `convert()` spawns 6–10 `hwp5proc` subprocesses, each starting a fresh
interpreter, importing pyhwp, and re-parsing the entire OLE file. Measured:
sample 3 = 1.17 s / 6 spawns, sample 4 = 1.68 s / 10 spawns. `rangetags.py` also
opens its **own** in-process `Hwp5File` — a 7th redundant parse.

Subprocess sites (verified full sweep): `reader.py` (`models` per section +
DocInfo, `ls`); `bindata.py` (`ls`, `cat` per image, `cat PrvImage`);
`summary.py` (`summaryinfo`); `rangetags.py` (own `Hwp5File`).

## Approach (decided: pure API, no subprocess fallback)

One **memoizing `HwpSource`** opened once per `convert`, holding one
`hwp5.xmlmodel.Hwp5File`, consumed by reader/bindata/summary/rangetags. All
`hwp5proc` subprocess calls removed; the `hwp5proc` binary is no longer a runtime
requirement.

## Adversarial verification (the three riskiest assumptions, tested)

### V1 — "the in-process XML difference is harmless" — TESTED, HELD
The in-process `xmlevents().dump()` XML is 24 KB larger than `hwp5proc xml`. Root
cause identified: the delta is confined to (a) the `PropertySetStream` element
(summary info — which the reader does **not** consume from XML; it reads summary
separately) and (b) **attribute ordering** (same attributes, same values,
different order — irrelevant to the `.get()`-based reader). Proven on all four
samples by an order-independent tree walk: outside `PropertySetStream`, the two
XMLs are **element-for-element identical** (same tags, same attribute-value sets,
same text; 5848/7001/4909/7880 elements, zero mismatches). Because the two
differences are systematic code-path behaviors (not data-dependent), this
generalizes. **Gate:** assert this tree-equivalence, not merely byte-identical
output.

### V2 — "cat via API == cat via CLI" — TESTED, HELD (with a helper caveat)
`hwp5proc cat` *is* `hwp5file[name].open().read()` internally, so they cannot
diverge on compression by construction. Verified on **every** stream in all four
docs (BinData spanning bmp/jpg/png): all byte-identical. **Caveat found:** a naive
`path.split('/')` storage walk raises `KeyError` on the control-char stream name
`\x05HwpSummaryInformation`. That stream is never `cat`-ed (summary comes from the
API object), and the paths we do use — `BinData/*`, `PrvImage` — all resolve
correctly. **Design constraint:** the stream accessor handles only the concrete
paths we need and returns `None` for a missing/inaccessible stream (callers
already skip missing streams); it does not attempt to be a general storage walker.

### V3 — "parse once → ~3×" — TESTED, CORRECTED
False as stated: pyhwp accessors are lazy and **do not cache** — `xml()` costs
0.231 s on first call and 0.227 s again on the *same object*. Opening once ≠
parsing once. Corrected conclusions, now load-bearing in the design:
- **Memoization is mandatory.** `HwpSource` MUST cache each accessor's output
  (xml bytes; the model list per stream; stream bytes) so each underlying pyhwp
  parse happens exactly once. Without it, xml/models get re-parsed and the win
  erodes or inverts.
- **Realistic win is ~2–2.5×, not 3×.** Measured in-process data-access ≈ 0.34 s
  (open 0.003 + xml 0.231 + docinfo.models 0.023 + section.models 0.080 + a few
  cheap cats) versus a 1.68 s subprocess baseline whose shared remainder
  (lxml parse + mapper + writer) is ~0.35 s → expected ≈ 0.7 s. The claim in this
  spec is the **measured** figure recorded in the final report, not an
  extrapolation.

## Architecture

- **New `hwp2hwpx/hwpmodel/source.py` — `HwpSource(hwp_path)`, memoizing:**
  - Opens one `hwp5.xmlmodel.Hwp5File` lazily.
  - `xml() -> bytes` — `xmlevents().dump()`, **cached** after first call.
  - `docinfo_models() -> list` / `section_models(name) -> list` — **cached** per
    stream (each pyhwp `models()` walk runs once). Model dicts carry `content`
    and `payload` (raw `bytes` — the offset-68 charPr read consumes `payload`
    directly; no hex decode).
  - `section_names() -> list` — BodyText/Section* in order.
  - `stream_bytes(path) -> Optional[bytes]` — resolves only the concrete paths we
    use (`BinData/<name>`, `PrvImage`); returns `None` if absent. Not a general
    walker (see V2). Cached per path.
  - `summary()` — the `HwpSummaryInfo`-equivalent object/fields.
  - The underlying `Hwp5File` is also exposed for `rangetags.py`.

- **`reader.py`** — `hwp5_xml`, `_hwp5proc_models`, `_section_streams`,
  `hwp5_char_shapes`, `hwp5_char_shape_border_fills` consume `HwpSource`. Offset-68
  read uses `model["payload"]` directly (already `bytes`). Remove `_hwp5proc` and
  the hex-flatten helper if unused.

- **`bindata.py`** — `_list_bindata_streams`, per-image extraction, and
  `extract_preview_image` use `HwpSource.section_names()`/`stream_bytes`. PNG-sig
  sniff unchanged.

- **`summary.py`** — read fields from `HwpSource.summary()`: direct attributes for
  author/comments/keywords/lastSavedBy/created&lastSaved times; `title`/`subject`
  via the property set by OLE property id (PIDSI_TITLE=2, PIDSI_SUBJECT=3), or by
  reusing pyhwp's own text dump if it reproduces the current `Key: value` lines.
  Existing timestamp formatting and field mapping preserved.

- **`rangetags.py`** — take the shared `HwpSource` (use its `Hwp5File`) instead of
  opening its own.

- **`convert.py`** — construct one `HwpSource(hwp_path)`; pass to
  reader/bindata/summary/rangetags.

## Testing & gates

- **XML tree-equivalence (V1 gate):** for all four samples, `HwpSource.xml()`
  parses to a tree that is element-for-element identical to `hwp5proc xml`
  (tags + attribute-value sets + text, order-independent) outside
  `PropertySetStream`.
- **Byte-identical output (primary gate):** the `.hwpx` after the refactor is
  byte-identical to pre-refactor output on all four samples — every zip part
  equal. Output must not change.
- **Stream equivalence (V2 gate):** `stream_bytes` equals `hwp5proc cat` for
  `PrvImage` and every `BinData/*` stream across all samples; `None` for a missing
  stream.
- **Summary equivalence:** `summary()`-derived fields equal today's
  subprocess-parsed `HwpSummaryInfo` on all samples.
- **Parse-once (V3 gate):** a test proves each underlying pyhwp parse runs once —
  e.g. wrap/patch `Hwp5File.xmlevents` and the per-stream `models` and assert one
  call each across a full `convert()`; and assert `convert()` spawns **zero**
  subprocesses.
- **Performance (informational):** record measured before/after wall-clock per
  sample in the final report (expected ~2–2.5× on sample 4). Not a hard threshold.
- **Full suite green** via `.venv/bin/python -m pytest`.

## Non-goals

- Any change to conversion output, mapper/writer logic, or fidelity behavior
  (the byte-identical gate forbids it).
- A general-purpose OLE storage walker (V2: only the concrete paths we use).
- Concurrency/parallelism; CLI batch mode; packaging (separate sub-projects).

## Value

Replaces 6–10 subprocess spawns + 1 redundant re-parse with a single memoized
in-process parse — a **measured ~2–2.5×** speedup on the larger sample, zero
change to output (gated element-for-element and byte-for-byte), and drops the
`hwp5proc` binary as a runtime dependency.
