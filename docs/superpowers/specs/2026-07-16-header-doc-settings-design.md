# HWP → HWPX Converter — Header Document-Settings Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestones 1..12 (through drawing pictures), all merged to `main`.

## Goal

Emit the six header-tail elements missing on both samples, closing most of the
remaining `header.xml` gap:
`beginNum`, `compatibleDocument`>`layoutCompatibility`, `docOption`>`linkinfo`,
`trackchageConfig`.

**Success** = all six tags leave the `header.xml` miss list on both samples;
`beginNum` and `compatibleDocument targetProgram` carry the values derived from the
HWP; `header.xml` match rises on both; output still opens in Hancom Office.

## Verified ground truth (both samples identical)

Placement inside `<hh:head>`:
```
<hh:head version="1.5" secCnt="1">
  <hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>  <!-- FIRST child, before refList -->
  <hh:refList>...</hh:refList>
  <hh:compatibleDocument targetProgram="HWP201X"><hh:layoutCompatibility/></hh:compatibleDocument>
  <hh:docOption><hh:linkinfo path="" pageInherit="1" footnoteInherit="0"/></hh:docOption>
  <hh:trackchageConfig flags="56"/>
</hh:head>
```

Source → target:

| Target | HWP source | Kind |
|---|---|---|
| `beginNum page` | `DocumentProperties page-startnum` | real |
| `beginNum footnote` | `DocumentProperties footnote-startnum` | real |
| `beginNum endnote` | `DocumentProperties endnote-startnum` | real |
| `beginNum pic` | `DocumentProperties picture-startnum` | real |
| `beginNum tbl` | `DocumentProperties table-startnum` | real |
| `beginNum equation` | `DocumentProperties math-startnum` | real |
| `compatibleDocument targetProgram` | `CompatibleDocument target` (0 → `HWP201X`) | real |
| `layoutCompatibility` (empty) | `LayoutCompatibility` (attrs dropped by Hancom) | emit empty |
| `docOption`>`linkinfo` `path=""`/`pageInherit="1"`/`footnoteInherit="0"` | — (no HWP source) | **constant** |
| `trackchageConfig flags="56"` | — (no HWP source) | **constant** |

Verified: `DocumentProperties` and `CompatibleDocument` exist in HWP DocInfo on both
samples; all six `beginNum` values are `1`; `target="0"`; `linkinfo`/`trackchageConfig`
are byte-identical across the two samples (hence emitted as constants).

## Architecture (extends the 4 layers)

**Model (`hwpmodel/model.py`):**
- `HwpDocProperties(page_start=1, footnote_start=1, endnote_start=1, pic_start=1,
  tbl_start=1, equation_start=1)`.
- `HwpCompatDocument(target=0)`.
- `HwpDocInfo` gains `doc_properties: "HwpDocProperties" = None`,
  `compat: "HwpCompatDocument" = None`.

**OWPML model (`owpml/model.py`):**
- `BeginNum(page=1, footnote=1, endnote=1, pic=1, tbl=1, equation=1)`.
- `CompatDocument(target_program="HWP201X")`.
- `Header` gains `begin_num: "BeginNum" = None`, `compat: "CompatDocument" = None`.

**Reader (`hwpmodel/reader.py`):** in `read_docinfo`, parse
`root.find(".//DocumentProperties")` → `HwpDocProperties` and
`root.find(".//CompatibleDocument")` → `HwpCompatDocument`; attach to `HwpDocInfo`.
Missing records → `None` (defensive).

**Mapper (`mapper/body.py`, or a small `mapper/docsettings.py`):** map
`HwpDocProperties` → `BeginNum` (field passthrough) and `HwpCompatDocument` →
`CompatDocument` (`target` 0 → `HWP201X` via a small map, default `HWP201X`); set
`Header.begin_num` and `Header.compat`.

**Writer (`owpml/header_writer.py`):** in `header_xml`:
- Emit `<hh:beginNum .../>` as the **first** child of `head` (before `refList` is
  created) from `header.begin_num` (or defaults when `None`).
- After the `refList` subtree is built (before `return`), emit, as children of
  `head`: `<hh:compatibleDocument targetProgram="…"><hh:layoutCompatibility/></…>`
  from `header.compat`; `<hh:docOption><hh:linkinfo path="" pageInherit="1"
  footnoteInherit="0"/></hh:docOption>` (constants); `<hh:trackchageConfig
  flags="56"/>` (constant).

## Error handling

- Missing `DocumentProperties`/`CompatibleDocument` → model `None` → writer emits
  `beginNum`/`compatibleDocument` with defaults (`beginNum` all `1`, `targetProgram
  ="HWP201X"`). Never crash. (Both samples have the records; defaults keep a
  record-less document valid.)
- Unknown `CompatibleDocument target` → `targetProgram="HWP201X"` (default).

## Testing strategy (TDD)

- **Reader:** the fixture parses `HwpDocInfo.doc_properties` with `page_start==1`
  (and the other five), and `HwpDocInfo.compat.target==0`.
- **Mapper:** `HwpDocProperties(page_start=2,...)` → `BeginNum(page=2,...)`;
  `HwpCompatDocument(target=0)` → `CompatDocument(target_program="HWP201X")`;
  unknown target → `HWP201X`.
- **Writer:** `header_xml` emits `beginNum` as the first child of `head` (before
  `refList`) with the six attributes; emits `compatibleDocument`>`layoutCompatibility`,
  `docOption`>`linkinfo`, `trackchageConfig` after `refList`; a `None` `begin_num`/
  `compat` still emits valid defaults.
- **End-to-end / fidelity (both samples):** convert samples 3 and 4; assert the six
  tags (`beginNum`, `compatibleDocument`, `layoutCompatibility`, `docOption`,
  `linkinfo`, `trackchageConfig`) leave the `header.xml` miss list; `beginNum` values
  match the HWP `DocumentProperties`; `header.xml` match rises; full regression green.

## Non-goals

- `substFont` (Hancom runtime substitution — non-goal), `subscript`, bullets/numbering
  definitions, and the section-side `ctrl`/`pageHiding`/`bookmark` items — separate
  milestones.
- Reproducing Hancom's exact `trackchageConfig`/`linkinfo` semantics from HWP — not
  derivable; emitted as the observed constants (score-neutral, both samples identical).

## Key risks

- **`beginNum` placement (first child of `head`, before `refList`)** — a structural
  change to the head open sequence; mitigated by creating the `beginNum` element
  before the `refList` `SubElement` and a writer test asserting it is `head`'s first
  child.
- **Tail elements after `refList`** — mitigated by appending them as `head` children
  after the refList subtree is complete and a writer test asserting presence + order.
- **Constants (`linkinfo`, `trackchageConfig`)** — documented as non-derivable; both
  samples identical, so score-neutral. If a future document differs, only these two
  attributes would diverge (values are display/config, count-neutral).
