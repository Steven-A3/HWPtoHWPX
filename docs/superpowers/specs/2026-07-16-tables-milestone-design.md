# HWP → HWPX Converter — Tables Milestone Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** `2026-07-16-hwp-to-hwpx-converter-design.md` (milestone 1: text + char/para properties, merged to `main`)

## Goal

Convert HWP tables into faithful HWPX tables — recovering document **content** that the milestone-1 converter silently drops. Target documents (Korean government solicitation/task-order documents — samples 3 and 4) are table-heavy; ~33 tables and ~350–450 cells per document currently produce no output at all.

Success = the fidelity harness's `tc`/`subList`/`cellAddr`/`cellSpan`/`cellSz` misses (×353–448) and the table-cell `p` misses (a large share of the ×529–566 `p` gap) drop to ~zero, and the output still opens in Hancom Office with visible, populated, correctly-bordered tables.

## Background — verified ground truth

**HWP side (pyhwp `hwp5proc xml`):** A table is a `TableControl` (chid `tbl `) sitting inline in a `Paragraph/LineSeg`:
```
TableControl(flow, halign, height, ...)
  TableBody(borderfill-id, cellspacing, cols, rows, padding-*, repeat-header)
    TableRow*
      TableCell(borderfill-id, col, row, colspan, rowspan, width, height,
                padding-*, valign, ...)
        Paragraph*   # ordinary paragraphs (LineSeg/Text), recursive
```
Cells and bodies reference `borderfill-id`; `DocInfo/IdMappings` holds **52 `BorderFill`** defs (id == positional index), each with 5 `Border` children (left/right/top/bottom/diagonal: `stroke-type`, `width` like `"0.4mm"`, `color`) plus an optional `FillColorPattern` (`background-color`, `pattern-color`, `pattern-type`). The samples have **15 merged cells** (colspan/rowspan > 1) and **no nested tables** (0 cells contain a nested `TableControl`).

**HWPX target (Hancom):**
```
hp:tbl(id, rowCnt, colCnt, cellSpacing, borderFillIDRef, zOrder, numberingType,
       textWrap, textFlow, pageBreak, repeatHeader, ...)
  hp:sz(width, widthRelTo, height, heightRelTo, protect)
  hp:pos(treatAsChar, ..., vertAlign, horzAlign)
  hp:outMargin(left,right,top,bottom) ; hp:inMargin(...)
  hp:tr*
    hp:tc(name, header, hasMargin, protect, editable, dirty, borderFillIDRef)
      hp:subList(id, textDirection, lineWrap, vertAlign, ...)
        hp:p*        # cell paragraphs (same as body paragraphs)
      hp:cellAddr(colAddr, rowAddr)
      hp:cellSpan(colSpan, rowSpan)
      hp:cellSz(width, height)
      hp:cellMargin(left,right,top,bottom)
```
The `hp:tbl` lives **inside a `hp:run`** (`hp:p > hp:run > hp:tbl`). Border/fill defs live in `header.xml` under `<hh:borderFills>` in `refList`:
```
hh:borderFill(id, threeD, shadow, centerLine, breakCellSeparateLine)
  hh:slash / hh:backSlash (type)
  hh:leftBorder/rightBorder/topBorder/bottomBorder/diagonal (type=SOLID|NONE|..., width="0.4 mm", color="#000000")
  hh:fillBrush > hc:winBrush(faceColor, hatchColor, alpha)   # only when filled
```
Mapping notes: HWP `stroke-type="solid"` → HWPX `type="SOLID"` (uppercase); width `"0.4mm"` → `"0.4 mm"` (space before unit); color passes through. `refList` child order is fontfaces → **borderFills** → charProperties → paraProperties → styles.

The milestone-1 fix already emits a `<hh:styles>` table and placeholder runs; this milestone adds `<hh:borderFills>` so table `borderFillIDRef`s resolve (otherwise they dangle exactly like styleIDRef did).

## Decisions

- **Architecture:** extend the existing 4 layers; no new layer. New element types flow Reader → HWP model → Mapper → OWPML model → Writer.
- **borderFill fidelity:** real per-side borders + cell background fills (not placeholders).
- **Merged cells:** included (colSpan/rowSpan from cell `colspan`/`rowspan`).
- **Nesting:** the paragraph parser is made recursive so cell paragraphs — and any nested tables — are handled by the same code path, even though the samples contain none.
- **Deferred:** precise `linesegarray` layout metadata inside cells (Hancom recomputes it, same as body paragraphs); per-language font refinement; charPr `borderFillIDRef`.

## Architecture

### Models

**HWP side (`hwpmodel/model.py`) — new:**
- `HwpBorder(kind: str, stroke_type: str, width: str, color: str)` — kind ∈ left/right/top/bottom/diagonal.
- `HwpBorderFill(index: int, borders: list[HwpBorder], fill_color: str | None)`.
- `HwpTableCell(col: int, row: int, col_span: int, row_span: int, width: int, height: int, border_fill_id: int, valign: str, paragraphs: list[HwpParagraph])`.
- `HwpTableRow(cells: list[HwpTableCell])`.
- `HwpTable(rows: int, cols: int, cell_spacing: int, border_fill_id: int, width: int, height: int, table_rows: list[HwpTableRow])`.
- `HwpRun` gains `table: HwpTable | None = None` (a run holds text OR a table).
- `HwpDocInfo` gains `border_fills: list[HwpBorderFill]`.

**OWPML side (`owpml/model.py`) — new:**
- `Border(kind, type, width, color)`; `BorderFill(id, borders, fill_color)`.
- `Tc(col_addr, row_addr, col_span, row_span, width, height, border_fill_id, valign, paras)`.
- `TableRow(cells)`; `Table(id, row_cnt, col_cnt, cell_spacing, border_fill_id, width, height, rows)`.
- `Run` gains `table: Table | None = None`.
- `Header` gains `border_fills: list[BorderFill]`.

### Reader (`hwpmodel/reader.py`)
- Parse `IdMappings/BorderFill` → `HwpDocInfo.border_fills` (positional index == id), each with its 5 `Border` children and optional `FillColorPattern` fill color.
- Refactor the paragraph walk into a reusable `parse_paragraph(para_el) -> HwpParagraph` that iterates `LineSeg` children in document order: `Text` → text `HwpRun`; `TableControl` → a table `HwpRun` (`table=` parsed `HwpTable`). Cell paragraphs call `parse_paragraph` recursively.
- `read_document` uses `parse_paragraph` for top-level `ColumnSet/Paragraph` (replacing the current `_paragraph_runs`), so body and cell paragraphs share one code path.

### Mapper
- `mapper/border_fill.py`: `map_border_fills(list[HwpBorderFill]) -> list[BorderFill]` — per-side line type uppercased, width normalized to `"N mm"`, color pass-through; fill color when present.
- `mapper/table.py`: `map_table(HwpTable) -> Table` — rowCnt/colCnt/cellSpacing/borderFillIDRef; each cell → `Tc` with cellAddr(col,row), cellSpan(colspan,rowspan), cellSz(width,height), cellMargin, border_fill_id, valign; cell paragraphs via the existing paragraph→`Para` mapping (extracted into a reusable `map_paragraph`).
- `mapper/body.py`: extended so a table `HwpRun` maps to `Run(char_pr_id, texts=[], table=map_table(...))`; `map_document` builds `Header.border_fills = map_border_fills(docinfo.border_fills)`.

### Writer
- `header_writer.py`: emit `<hh:borderFills itemCnt=…>` with each `<hh:borderFill>` (slash/backSlash, 4 side borders + diagonal, optional fillBrush), placed in `refList` after fontfaces and before charProperties.
- `section_writer.py`: when a `Run.table` is set, emit `<hp:tbl>` (sz/pos/outMargin/inMargin) → `<hp:tr>` → `<hp:tc>` (subList of cell paras + cellAddr/cellSpan/cellSz/cellMargin). Reuse the existing paragraph-writing code for cell `hp:p`s.

### Data flow & boundaries
Reader and Writer remain the only byte-touching layers. The two internal models stay the stable interface; adding table/borderFill types is additive. `parse_paragraph` (reader) and `map_paragraph` (mapper) are the shared, recursive units that keep body and cell content on one code path.

## Error handling
- A `TableControl` with unexpected/missing structure (no `TableBody`, ragged rows) is logged and skipped for that table, not fatal — a partial conversion beats a crash (consistent with milestone 1).
- Unknown border `stroke-type` maps to `NONE`; missing width/color fall back to `"0.1 mm"`/`"#000000"`.
- Cells referencing a `borderfill-id` beyond the parsed list fall back to id 0.

## Testing strategy (TDD)
- **Reader unit tests** (fixture-backed): `border_fills` count == 52; a known table parses to the right rows×cols with expected cell text; a merged cell reports colspan/rowspan > 1.
- **Mapper unit tests:** border stroke/width/color normalization; a `HwpTable` maps to a `Table` with correct cellAddr/cellSpan; fill color mapping.
- **Writer unit tests:** `header_xml` emits `<hh:borderFills>` with N entries in the right refList position; `section_xml` emits a well-formed `<hp:tbl>` with tr/tc/subList/cellAddr/cellSpan for a hand-built `Table`.
- **End-to-end / fidelity:** convert the real samples; assert `tc`/`cellAddr`/`cellSpan`/`subList` counts are now non-zero and close to Hancom's; assert no dangling `borderFillIDRef` (every ref resolves to an emitted `<hh:borderFill>`); harness section-match score rises materially from the ~20–28% baseline.
- **Regression:** all milestone-1 tests stay green; output still opens in Hancom (manual smoke).

## Non-goals (this milestone)
- Precise in-cell `linesegarray` layout metadata (deferred, as in body).
- Per-language font refinement; charPr `borderFillIDRef`.
- Images/bin-data, numbering/bullets, headers/footers, shapes — separate follow-ups.

## Key risks
- **refList ordering / element completeness** — Hancom may be strict about `<hh:borderFills>` placement or required attributes; mitigated by matching the real sample header exactly and the harness/no-dangling-ref checks.
- **Cell paragraph reuse** — extracting `map_paragraph`/`parse_paragraph` must not regress body paragraphs; mitigated by keeping the body path on the same refactored function with existing tests green.
- **Ragged/merged geometry** — colSpan/rowSpan combined with per-cell width/height can produce inconsistent `cellSz`; mitigated by taking values directly from HWP cell attrs and validating against Hancom output via the harness.
