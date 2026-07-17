# HWP → HWPX Converter — pageHiding Control Design

**Date:** 2026-07-17
**Status:** Approved (design confirmed by user)
**Builds on:** milestones 1..16 (through inline-object empty `<hp:t>`), all merged to `main`.

## Goal

Emit the `<hp:ctrl><hp:pageHiding .../></hp:ctrl>` inline control Hancom writes for
each HWP `PageHide` record. We currently drop `PageHide` entirely, missing both
the `ctrl` wrapper and the `pageHiding` element: sample 3 and sample 4 each have 2.

**Success** = each HWP `PageHide` becomes a `<hp:ctrl><hp:pageHiding/></hp:ctrl>`
in the correct run; the `pageHiding`/`ctrl` `section0.xml` miss counts drop by the
pageHiding contribution on both samples; output still opens in Hancom Office.

## Verified ground truth

`hwp5proc xml` exposes `<PageHide>` inside a paragraph's `<LineSeg>` (verified: 2
per sample, matching Hancom's 2 `pageHiding`). It carries a direct attribute map:

| HWP `PageHide` | OWPML `pageHiding` |
|---|---|
| `header` | `hideHeader` |
| `footer` | `hideFooter` |
| `basepage` | `hideMasterPage` |
| `pageborder` | `hideBorder` |
| `pagefill` | `hideFill` |
| `pagenumber` | `hidePageNum` |

Measured values match exactly (e.g. `header=0 … pagenumber=1` → `hideHeader="0" …
hidePageNum="1"`).

**Placement (verified):** `PageHide` controls appear as **leading** items in a
paragraph's `LineSeg` (before the text/line-break), and Hancom emits them as
leading `<hp:ctrl>` children of the run that holds the following text — run child
order `ctrl, [ctrl,] t` (two pageHiding in one run when two `PageHide` precede the
same text). In both samples these paragraphs are **inside table cells**;
`parse_paragraph` already handles cell paragraphs (via `_parse_table`), so one
reader code path covers them.

## Architecture (extends all 4 layers)

**Model (`hwpmodel/model.py`):**
- `HwpPageHide(hide_header=0, hide_footer=0, hide_master_page=0, hide_border=0,
  hide_fill=0, hide_page_num=0)` — ints (0/1).
- `HwpRun` gains `ctrls: list = field(default_factory=list)` — leading run-level
  controls (currently only `HwpPageHide`).

**OWPML model (`owpml/model.py`):**
- `PageHiding(hide_header=0, hide_footer=0, hide_master_page=0, hide_border=0,
  hide_fill=0, hide_page_num=0)`.
- `Run` gains `ctrls: list = field(default_factory=list)`.

**Reader (`hwpmodel/reader.py`, `parse_paragraph`):** recognize `<PageHide>` in
`LineSeg/*`; parse to `HwpPageHide`; collect pending leading ctrls and attach them
to the first content-bearing run built afterward (they precede the text). Missing
attrs default to 0; never crash. `PageHide` does not itself start/break a run.

**Mapper (`mapper/body.py`):** map `HwpRun.ctrls` → `Run.ctrls` (`HwpPageHide` →
`PageHiding`, field passthrough) in `map_paragraph` for text runs.

**Writer (`owpml/section_writer.py`, `_write_run`):** emit each `run.ctrls` item as
`<hp:ctrl><hp:pageHiding hideHeader=… …/></hp:ctrl>` **before** the `<hp:t>` (and
before any table/drawing), matching Hancom's `ctrl … t` child order.

## Error handling

- `PageHide` with no following content run (degenerate) → attach to the first run,
  or drop if the paragraph has no runs; never crash.
- Missing `PageHide` attributes → default 0.
- A run with no ctrls → unchanged output (the vast majority).

## Testing strategy (TDD)

- **Model:** `HwpPageHide`/`PageHiding` hold the six flags; `HwpRun.ctrls` and
  `Run.ctrls` default to independent empty lists.
- **Reader:** a synthetic `<Paragraph>` with two leading `<PageHide … pagenumber="1"/>`
  before text → the first content run's `ctrls` holds two `HwpPageHide` with
  `hide_page_num == 1`; a paragraph with no `PageHide` → empty `ctrls`. Sample 3
  yields exactly 2 attached `PageHide` (including nested cell paragraphs).
- **Mapper:** `HwpRun(ctrls=[HwpPageHide(hide_page_num=1)])` → `Run.ctrls ==
  [PageHiding(hide_page_num=1)]`.
- **Writer:** a `Run` with `ctrls=[PageHiding(hide_page_num=1)]` and text →
  serializes `<hp:ctrl><hp:pageHiding … hidePageNum="1"/></hp:ctrl>` **before**
  `<hp:t>`; child order is `ctrl, t`.
- **End-to-end / fidelity:** sample 3 and sample 4 — `pageHiding` miss count is 0;
  the `ctrl` miss count drops by 2; `section0.xml` match rises; full regression
  green.
- **Regression:** the markpen-era sample-3 byte-identity guard
  (`tests/test_convert_markpen.py::test_sample3_section_unchanged`) must be
  re-baselined — this milestone changes sample 3's `section0.xml` (adds 2
  `<hp:ctrl><hp:pageHiding/></hp:ctrl>`). Capture the new `len`/`sha256` live.
  Markpen, trailing-empty-run, and inline-`<hp:t>` tests stay green.

## Non-goals

- The other `ctrl`-wrapped controls (`newNum`, `bookmark`, `titleMark`, and any
  `pageNum`/`colPr` placement gaps) — separate milestones. This milestone closes
  only the `pageHiding` contribution to the `ctrl` gap (2 of the 4 on sample 3, 2
  of the 2 on sample 4).
- Correcting where our existing `secPr`/`colPr`/`pageNum` controls sit — untouched.

## Key risks

- **Attach to the wrong run** — mitigated by attaching pending ctrls to the first
  content-bearing run (they always precede text in the samples) and a reader test
  asserting the attachment; count-based fidelity plus a writer order test catch
  regressions.
- **Child-order (`ctrl` before `t`)** — mitigated by emitting ctrls first in
  `_write_run` and a writer test asserting `ctrl, t` order.
- **Sample-3 regression guard churn** — handled by re-baselining the markpen
  no-change test (documented), not by weakening it.
