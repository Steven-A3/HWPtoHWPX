# Drawings, Images & Package Metadata — Design Spec

**Date:** 2026-07-18
**Milestone:** M21
**Status:** Approved design, pending plan

## Goal

Close the fidelity and correctness gaps exposed by the third sample (the
"2013" sample; full filename redacted from this doc post-hoc, see privacy
sweep): recover a silently-dropped embedded
JPEG, render text-boxes, and emit the missing package-metadata parts. The
package-metadata work is general (affects all three samples); the drawing work
is exercised by the 2013 sample.

## Motivation & Ground Truth

The 2013 sample was added as a wider-corpus check and falsified the prior
"fidelity ceiling" claim. Measured gaps (ours vs Hancom export):

| Part | Match | Principal gaps |
|---|---|---|
| `Contents/section0.xml` | 0.9639 | `run`×42, `t`×35, `p`×14, `lineseg`×14, `scaMatrix`/`rotMatrix`×10, `tab`×9, `offset`/`orgSz`/`curSz`/`flip`×7 |
| `Contents/header.xml` | 0.9942 | `substFont`×28 (non-goal), `paraHead`×10 (numberings — separate), `supscript`×6 (separate), `color`×4, `fillBrush`×2, `gradation`×2, borderFill bits |
| `Contents/content.hpf` | 0.5714 | `meta`×8, `item`×1 |
| `META-INF/container.xml` | 0.7500 | `rootfile`×1 |
| `META-INF/container.rdf` | — | **entire part missing** |
| `BinData/*` | — | **JPEG dropped; other two mis-indexed** |

This spec addresses the drawing gaps in section0, the image gaps, and the
package-metadata parts (`content.hpf` meta, `container.xml` rootfile,
`container.rdf`). It does **not** address the header-side `numberings`,
`supscript`, or fill/color gaps — those are separate milestones.

### Root cause of the dropped JPEG

Source shape tree of the container:

```
GShapeObjectControl (chid=gso)
  ShapeComponent chid0=$con          ← container/group: UNSUPPORTED → _parse_drawing returns None
    ShapeComponent chid=$pic         ← the JPEG (bindata-id=2), lost with the whole subtree
    ShapeComponent chid=$rec  ×2     ← rectangles holding the ToC text
```

`_parse_drawing` in `hwp2hwpx/hwpmodel/reader.py` accepts only `$lin`/`$pic`;
`$con` returns `None`, discarding every descendant. The JPEG is not lost by the
bindata collector — it is never collected because its container is unsupported.

Document-wide drawing kinds: `$pic`×2 (top-level), `$rec`×3 (top-level) + ×2
(nested), `$con`×1. Hancom's section0 emits `container`×1, `rect`×5, `pic`×3,
`drawText`×2.

### Root cause of image mis-indexing

Hancom renumbers embedded images `image1..N` by **document order of first
reference**, preserving the file extension — NOT by HWP bindata-id:

| Doc order | HWP stream | bindata-id | Hancom name |
|---|---|---|---|
| 1st | `BIN0002.jpg` | 2 | `image1.jpg` |
| 2nd | `BIN0003.bmp` | 3 | `image2.bmp` |
| 3rd | `BIN0001.png` | 1 | `image3.png` |

Our `extract_bin_items` names files `image{bindata_id}.{ext}` and the writer
emits `binaryItemIDRef="image{bindata_id}"`. Sample 4 matches Hancom today
**only by coincidence** (its ids run 1,2,3 in document order). The 2013 sample
breaks that coincidence.

## Architecture

Four-layer pipeline unchanged (Reader → Mapper → Writer → Fidelity). Changes
are additive within each layer plus a new package-parts source.

### Component A — Recursive drawing shapes

Generalize the drawing model from a flat pic/line to a recursive shape tree.

**Reader (`hwp2hwpx/hwpmodel/reader.py`):**
- `_parse_drawing` recurses into child `ShapeComponent`s. `$con` becomes a
  container whose `children` are parsed recursively; `$rec` becomes a rectangle
  with geometry + line + shadow + nested paragraph content; `$pic`/`$lin`
  unchanged but now nestable.
- `$rec` text: the `ShapeComponent`'s child `Paragraph` elements are parsed with
  the existing `parse_paragraph` (reuse — do not duplicate paragraph logic).
- Unknown `chid0` values still return `None` (skip), preserving current
  fail-safe behavior for shape kinds we do not model.

**Model (`hwp2hwpx/hwpmodel/model.py`):**
- `HwpDrawing` gains `children: list = field(default_factory=list)` and a
  `rect`/`draw_text` payload (`HwpRect`, `HwpDrawText` holding
  `paragraphs: list`). `kind` extends to `"container"` and `"rect"`.

**OWPML model (`hwp2hwpx/owpml/model.py`):**
- New dataclasses: `Container` (children + shared shape-object attrs), `Rect`
  (geometry + line_shape + shadow + draw_text), `DrawText` (last_width, name,
  editable, sub_list), `SubList` (the fixed subList attrs + `paras: list`).

**Mapper (`hwp2hwpx/mapper/`):**
- Recursive mapping of container/rect; paragraphs inside a `SubList` reuse the
  existing paragraph mapper (`map_paragraph`).

**Writer (`hwp2hwpx/owpml/section_writer.py`):**
- `_write_container`, `_write_rect`, `_write_draw_text` following the existing
  `_write_pic`/`_write_line` structure. `groupLevel` increments with nesting
  depth (container=0, its children=1). Paragraphs inside `subList` reuse
  `_write_paragraph`.

**Target structures (exact attribute sets the writer must emit):**

```
<hp:container id zOrder numberingType="PICTURE" textWrap textFlow lock="0"
    dropcapstyle="None" href="" groupLevel="0" instid>
  <hp:offset/><hp:orgSz/><hp:curSz/><hp:flip/><hp:rotationInfo/>
  <hp:renderingInfo> transMatrix, scaMatrix, rotMatrix </hp:renderingInfo>
  ...child shapes at groupLevel=1...

<hp:rect id zOrder numberingType="NONE" textWrap textFlow lock="0"
    dropcapstyle="None" href="" groupLevel="1" instid ratio="0">
  <hp:offset/><hp:orgSz/><hp:curSz/><hp:flip/><hp:rotationInfo/>
  <hp:renderingInfo> transMatrix, scaMatrix, rotMatrix, scaMatrix, rotMatrix </hp:renderingInfo>
  <hp:lineShape color width style endCap headStyle tailStyle headfill tailfill
      headSz tailSz outlineStyle alpha/>
  <hp:shadow type="NONE" color offsetX offsetY alpha/>
  <hp:drawText lastWidth name="" editable="0">
    <hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK"
        vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0"
        textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">
      <hp:p ...recursive paragraph content...>
```

Note the rect's `renderingInfo` carries a **second** scaMatrix+rotMatrix pair
(the shape's own transform on top of the group transform). The reader must
capture both; the writer must emit both.

### Component B — Bindata sequential renumbering

Establish a single **document-order index** at extraction time and thread it
through every reference.

- `extract_bin_items` assigns `image{k}` (`k = 1..N`) in first-reference order,
  filename `image{k}.{ext}`, `id="image{k}"`.
- The drawing's `bin_item_id` (section `binaryItemIDRef`) uses the same index,
  looked up by source bindata-id → sequential-index map.
- `content.hpf` items and manifest entries follow.
- **Regression guard:** sample 4 must still produce identical output (its map is
  the identity `1→1, 2→2, 3→3`).
- **Media type:** match Hancom's `image/jpg` spelling for `.jpg` (Hancom uses the
  non-standard token; fidelity over correctness here).

### Component C — Package/metadata parts

**`META-INF/container.rdf`** (new part, all samples): generated from section
count. For each section: a `hasPart` + `SectionFile` typed Description; one
`hasPart` + `HeaderFile` for the header; one `Document` type. Exact template
from the sample:

```xml
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""><ns0:hasPart .../header.xml"/></rdf:Description>
  <rdf:Description rdf:about="Contents/header.xml"><rdf:type ...#HeaderFile"/></rdf:Description>
  <rdf:Description rdf:about=""><ns0:hasPart .../section0.xml"/></rdf:Description>
  <rdf:Description rdf:about="Contents/section0.xml"><rdf:type ...#SectionFile"/></rdf:Description>
  <rdf:Description rdf:about=""><rdf:type ...#Document"/></rdf:Description>
</rdf:RDF>
```

**`META-INF/container.xml`** (all samples): add the third `<ocf:rootfile>`
entry for `META-INF/container.rdf` (`media-type="application/rdf+xml"`), after
the existing content.hpf and PrvText entries.

**`Contents/content.hpf`** (all samples): expand the `<opf:package>` namespace
list to Hancom's full set, and emit `<opf:meta>` blocks in `<opf:metadata>`
from `HwpSummaryInfo` (`hwp5proc summaryinfo` / body-XML `HwpSummaryInfo`
element): `creator`, `subject`, `description`, `lastsaveby`, `CreatedDate`,
`ModifiedDate`, `date`, `keyword`. Title/language sourced from summary.

## Non-Goals (confirmed with user)

Hancom generates these at its own export time; they cannot be reproduced from
the source HWP. Treated as documented non-goals (substFont-class):

1. **`Preview/PrvImage.png`** — rendered page thumbnail. Not in source, cannot
   be byte-reproduced. We do not emit it.
2. **`ModifiedDate` / `lastsaveby` values** — Hancom rewrites these at export
   time (the sample shows a 2026 modified-date and a different user than the
   source `lastsaveby`). We emit the *elements* (element-count scoring credits
   them) with best-effort source values; the values will not byte-match.
3. **`media-type` spelling** — Hancom writes the non-standard `image/jpg`; we
   match Hancom's spelling for fidelity rather than the standard `image/jpeg`.

## Testing Strategy

Fidelity scoring is element-count-based (attribute values do not affect score),
so each component carries **exact-serialization** unit tests guarding the
attribute values, following the pattern established in prior milestones
(bullets, inline-ctrls). Specifically:

- Reader tests: recursive `$con`/`$rec` parse; nested paragraph capture; unknown
  chid still skipped; bindata document-order index.
- Mapper tests: container/rect mapping; subList paragraph passthrough; bindata
  index → `binaryItemIDRef`.
- Writer tests: exact-serialization of container, rect, drawText/subList against
  Hancom byte-substrings; container.rdf; container.xml third rootfile;
  content.hpf meta blocks.
- End-to-end: 2013 section0 miss for `container`/`rect`/`pic`/`drawText` == 0;
  JPEG present as `image1.jpg`; all three BinData names match Hancom; section0
  and header match rise; **samples 3 and 4 unchanged** (regression guards,
  including the existing s3 section0 byte-identity guard — re-baseline if the
  package-parts change alters s3 output).

**Risk:** the recursive shape reader/writer is the primary risk; nesting depth
and `groupLevel` assignment are tested explicitly. Bindata renumbering is
cross-cutting; sample 4's identity-map invariance is the guard.

## Expected Outcome

- 2013: JPEG recovered (`image1.jpg`), section0 0.9639 → ~0.99+, header
  0.9942 → ~0.998 (remaining: substFont, numberings, supscript — out of scope).
- All samples: `container.rdf` emitted, `container.xml` and `content.hpf`
  metadata gaps closed.
- Samples 3 & 4: no regression (byte-identity guards hold or are re-baselined
  with the package-parts delta documented).
