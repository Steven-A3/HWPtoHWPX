# Preview Image Emission — Design

**Goal:** Give the output `.hwpx` a usable preview thumbnail by copying the
source `.hwp`'s `PrvImage` OLE stream into `Preview/PrvImage.png` — **only when
that stream is already PNG**. Non-PNG sources (GIF/BMP) are skipped and
documented.

**Status:** design approved; ground truth verified against the three sample
documents.

---

## Problem

Every Hancom `.hwpx` export ships a `Preview/PrvImage.png` part. Our converter
emits none, on all three samples. The gap was invisible to the fidelity harness
because that harness scores XML element counts only — binary parts are never
counted.

## Why byte-fidelity is off the table (verified)

Hancom **re-renders** the preview at export time; it does not copy the source
stream:

| Sample | Source `.hwp` `/PrvImage` | Hancom `.hwpx` `Preview/PrvImage.png` |
|--------|---------------------------|----------------------------------------|
| 3      | 16,596-byte **PNG**       | 44,729-byte PNG (different bytes)       |
| 4      | 16,632-byte **PNG**       | 49,142-byte PNG (different bytes)       |
| 2013   | 1,986-byte **GIF**        | 45,532-byte PNG (different format)      |

Reproducing Hancom's bytes would require a full page-rendering engine. It is not
a goal. Additionally, `PrvImage.png` is a **loose ZIP entry** — referenced in
*neither* `content.hpf` *nor* `container.xml` — so its presence or absence moves
the fidelity score by exactly zero.

## Objective (decided)

**Usability, not byte-match.** Emit a valid `Preview/PrvImage.png` so downstream
HWPX consumers (Hancom Office, file explorers) get a working thumbnail. Accept
that the bytes will not equal Hancom's.

## Scope decision: PNG-only, skip + document

The source preview stream is not always PNG (2013 is a GIF). Writing an honest
`.png` for a non-PNG source would require transcoding, for which there is **no
Python stdlib path** (GIF LZW decode + PNG encode needs an imaging library such
as Pillow — a new C-extension dependency). The project is a pure-Python
converter, and this feature is unscored/usability-only, so adding an imaging
dependency is disproportionate.

**Rule:** copy the source stream verbatim when it is already PNG; otherwise skip
emission. The output is therefore always honest (bytes match the `.png`
extension) and always dependency-free.

- Samples 3 & 4 (PNG source): get a real thumbnail.
- 2013 (GIF source): stays preview-less — documented residual.

## Architecture

Data flows source `.hwp` → extractor → OWPML doc field → package writer.

- **`hwp2hwpx/hwpmodel/bindata.py`** — new
  `extract_preview_image(hwp_path) -> Optional[bytes]`:
  - Runs `hwp5proc cat <hwp_path> PrvImage` (the same subprocess pattern
    `extract_bin_items` uses to read BinData streams).
  - Returns the bytes **iff** they begin with the PNG signature
    `b"\x89PNG\r\n\x1a\n"`; otherwise returns `None`. `None` covers GIF/BMP,
    an empty stream, and a missing stream / non-zero exit.

- **`hwp2hwpx/owpml/model.py`** — the OWPML document model gains an optional
  `prv_image: Optional[bytes] = None` field (mirrors how `bin_items` rides along
  on the doc). The default `None` keeps every existing caller and test
  unaffected.

- **`hwp2hwpx/convert.py`** — one line:
  `owpml_doc.prv_image = extract_preview_image(hwp_path)`.

- **`hwp2hwpx/owpml/writer.py`** — `write_hwpx` adds
  `parts["Preview/PrvImage.png"] = doc.prv_image` **only when `doc.prv_image` is
  not None**.

**No manifest changes.** Hancom lists `PrvImage.png` in neither `content.hpf`
nor `container.xml`; emitting it as a bare ZIP entry matches their structure
exactly. `PrvText.txt` is unchanged.

## Testing

- **Unit (sniffer):** returns the input bytes for a PNG-signature stub; returns
  `None` for a GIF stub, a BMP stub, and empty input.
- **Integration (PNG source):** convert sample 3 → `Preview/PrvImage.png` is
  present, byte-equal to the source `PrvImage` stream, and carries the PNG
  signature.
- **Integration (non-PNG source):** convert 2013 → `Preview/PrvImage.png` is
  **absent** (GIF source, correctly skipped).
- **Regression:** the full existing suite stays green; no other package part
  changes.

## Non-goals

- Byte-matching Hancom's re-rendered preview image (needs a rendering engine).
- Transcoding GIF/BMP sources to PNG (needs an imaging dependency; 2013 stays
  preview-less — documented residual).
- `Preview/PrvText.txt` byte-fidelity (separate concern; already emitted from
  our text model).

## Value (stated plainly)

Zero change to the element-count fidelity score (binary part). The value is
real-world usability: two of three samples gain a working preview thumbnail in
their output `.hwpx`, with no new dependency and no risk to the scored parts.
