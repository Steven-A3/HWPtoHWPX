# HWP → HWPX Converter — Section Inline Content Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestones 1 + tables + paraPr + charPr + styles + tabs, all merged to `main`.

## Goal

Emit inline control characters (`<hp:fwSpace/>`, `<hp:lineBreak/>`) as mixed content inside `<hp:t>`, and — the larger win — **merge consecutive same-`charshape` text and control characters into a single run**, matching Hancom's run structure. Today the reader emits one run per `Text` element and silently drops every `ControlChar`, producing 1603 runs / 1429 `hp:t` versus Hancom's 869 / 690, and losing the full-width spaces and forced line breaks from the text.

Success = `fwSpace` (30) and `lineBreak` (11) appear in section0 as mixed content; run and `hp:t` counts converge toward Hancom's (869 / 690); no visible text is dropped; `fwSpace`/`lineBreak` leave the section miss list; section0.xml match rises materially; output still opens in Hancom Office.

## Background — verified ground truth (sample 3)

HWP paragraphs contain, inline within `LineSeg`, a sequence of `Text` and `ControlChar` elements, each with a `charshape-id`:
```
<Text charshape-id="94" lang="ko">(body text)</Text>
<ControlChar charshape-id="94" code="31" kind="CHAR" name="FIXWIDTH_SPACE"/>
<Text charshape-id="94" lang="other">(annotation mark) </Text>
<Text charshape-id="94" lang="ko">(more body text),</Text>
<ControlChar charshape-id="94" code="31" kind="CHAR" name="FIXWIDTH_SPACE"/>
…
```
The only inline `ControlChar` kinds are **`FIXWIDTH_SPACE`**, **`LINE_BREAK`**, and **`PARAGRAPH_BREAK`** (the paragraph terminator).

Hancom merges a maximal run of `Text` + `FIXWIDTH_SPACE`/`LINE_BREAK` sharing one `charshape-id` into a **single `<hp:run charPrIDRef=N>` with one `<hp:t>`** whose content is mixed — text nodes interleaved with empty control elements:
```
<hp:run charPrIDRef="94"><hp:t>(body text)<hp:fwSpace/>(annotation mark) (more body text),<hp:fwSpace/>(more body text)</hp:t></hp:run>
```
`<hp:lineBreak/>` appears the same way (`<hp:t><hp:lineBreak/>(body text)</hp:t>`).

**Verified mapping:**
- `FIXWIDTH_SPACE` → `<hp:fwSpace/>` (empty element inside `hp:t`).
- `LINE_BREAK` → `<hp:lineBreak/>` (empty element inside `hp:t`).
- `PARAGRAPH_BREAK` → skipped (implicit paragraph end in HWPX).
- Runs are split **only** by `charshape-id` change (differing `lang` on `Text` does not split — an `other`-lang annotation mark and the `ko`-lang body text right after it stay in one run), by a `TableControl`, or by `PARAGRAPH_BREAK`.

## Decisions

- A run's content becomes an **ordered list of inline items** — text strings and control markers — emitted as a single mixed-content `<hp:t>`.
- Group by `charshape-id`: consecutive `Text`/`FIXWIDTH_SPACE`/`LINE_BREAK` with the same `charshape-id` form one run; a change of `charshape-id`, a table, or a paragraph break starts a new run.
- Keep a read-only `text` convenience on `HwpRun` (join of its text pieces) so existing text-reading call sites and the mapper's plain-text path keep working during the migration.
- Preserve the empty-paragraph placeholder behavior (a run with no content emits no `<hp:t>`, exactly as today).
- Scope: `FIXWIDTH_SPACE` + `LINE_BREAK` only. Other control kinds and `<hp:ctrl>` section controls (pageHiding, etc.) are deferred.

## Architecture (extends existing layers, touches the core text path)

**Model (`hwpmodel/model.py`, `owpml/model.py`):**
- `HwpControl(kind:str)` where `kind`∈{`fwSpace`,`lineBreak`}.
- `HwpRun`: replace `text:str` with `contents:list` (items are `str` or `HwpControl`); add a read-only `text` property returning `"".join(c for c in contents if isinstance(c, str))`. Keep `char_shape_id`, `table`.
- `Control(kind:str)` (OWPML) where `kind`∈{`fwSpace`,`lineBreak`}.
- `Run.texts` keeps its name but now holds an ordered mix of `Text` and `Control` items.

**Reader (`hwpmodel/reader.py`):** rewrite `parse_paragraph`'s `LineSeg/*` walk to accumulate a current run keyed by `charshape-id`: append text (`Text.text`) and control markers (`HwpControl("fwSpace"|"lineBreak")`) to `contents`; flush the run when `charshape-id` changes, on a `TableControl` (emit the table run), or at `PARAGRAPH_BREAK`. Skip `PARAGRAPH_BREAK` and unknown control kinds.

**Mapper (`mapper/body.py`):** `map_paragraph` maps each `HwpRun.contents` item to a `Run.texts` item — `str`→`Text(content)`, `HwpControl`→`Control(kind)` — preserving order. A table run maps as today. An empty run keeps the placeholder `Run(char_pr_id=0, texts=[])`.

**Writer (`owpml/section_writer.py`, `owpml/package_parts.py`):** `_write_run` emits **one `<hp:t>` per non-empty run** with lxml mixed content: text via `.text`/`.tail`, `Control`→`<hp:fwSpace/>`/`<hp:lineBreak/>` sub-elements. `package_parts` preview text iterates `run.texts` skipping `Control` items.

**Fidelity harness:** existing; confirm run/`hp:t` counts converge to Hancom's and `fwSpace`/`lineBreak` leave the miss list.

## Error handling
- Unknown `ControlChar` names (anything but `FIXWIDTH_SPACE`/`LINE_BREAK`/`PARAGRAPH_BREAK`) are skipped — never crash.
- An empty `Text` contributes nothing; a run that ends up empty emits no `<hp:t>` (placeholder behavior preserved).
- A control before any text becomes the first child of `<hp:t>` (its text sits in the child's `.tail`).

## Testing strategy (TDD)
- **Model:** `HwpRun(contents=["가", HwpControl("fwSpace"), "나"]).text == "가나"`; `Control("lineBreak").kind == "lineBreak"`.
- **Reader:** a paragraph with `Text`(cs=94) + `FIXWIDTH_SPACE`(cs=94) + `Text`(cs=94) parses to ONE `HwpRun` with `contents == ["…", HwpControl("fwSpace"), "…"]`; a `charshape-id` change splits runs; `PARAGRAPH_BREAK` is dropped; `LINE_BREAK` becomes a `lineBreak` control.
- **Mapper:** `HwpRun.contents` maps to `Run.texts` with `Text`/`Control` in order; a table run still maps with `table` set.
- **Writer:** `_write_run` emits one `<hp:t>` with mixed content (`.text`, a `<hp:fwSpace/>` child, its `.tail`); a control-first run puts text in the child `.tail`; a table run emits no `<hp:t>`; an empty run emits no `<hp:t>`.
- **End-to-end / fidelity:** convert real samples; assert section0 `fwSpace`==30, `lineBreak`==11, run count and `hp:t` count drop toward Hancom's (≈869 / ≈690), the full body text (including the previously-dropped spaces) is present, `fwSpace`/`lineBreak` gone from the miss list, section0.xml match up materially; regression suite green; smoke opens in Hancom.

## Non-goals (this milestone)
- `<hp:ctrl>` section controls (pageHiding, pageNumberPosition, etc.); other `ControlChar` kinds.
- `linesegarray`/`lineseg` layout metadata (invisible, deferred).
- `pageBorderFill`, `autoNumFormat`, numbering/bullets.

## Key risks
- **Core text-path regression** — this reworks run construction and text emission, which currently have high fidelity. Mitigated by keeping the full existing text/table suite green, the `text` convenience property, and a staged migration (writer mixed-content and reader grouping land in separate, independently-green tasks).
- **Run grouping correctness** — merging must key strictly on `charshape-id` (not `lang`) and span the whole paragraph (across `LineSeg` boundaries). Mitigated by the reader unit tests and the end-to-end run/`t` count convergence check.
- **Mixed-content `.text`/`.tail` handling** — easy to misplace a text fragment. Mitigated by writer unit tests for text-before-control, control-before-text, and control-between-texts.
