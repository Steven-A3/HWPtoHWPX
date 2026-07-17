# HWP → HWPX Converter — Trailing Empty `<hp:t>` for Inline-Object Runs Design

**Date:** 2026-07-17
**Status:** Approved (design confirmed by user)
**Builds on:** milestones 1..15 (through trailing empty run), all merged to `main`.

## Goal

Emit the trailing empty `<hp:t></hp:t>` Hancom writes inside a run that carries an
**inline** (`treatAsChar="1"`) object — a table or a picture. Our writer emits the
object but no trailing `<hp:t>`, leaving us short every such element: sample 3
`t`×33, sample 4 `t`×25 in `section0.xml`.

**Success** = a run carrying an inline object (a table, or a drawing with
`treatAsChar=1`) gains a trailing empty `<hp:t/>` as its last child; the
`section0.xml` `t`-count gap closes on both samples; output still opens in Hancom
Office.

## Verified ground truth

Hancom emits one trailing empty `<hp:t>` per inline-object run (child order
`ctrl?, tbl|pic, t`). Measured on both samples:

| object | `treatAsChar` | trailing empty `<hp:t>`? |
|---|---|---|
| table (inline) | 1 | **yes** — sample 3: 33/33; sample 4: 16/18 |
| picture | 1 | **yes** — sample 4: 3/3 |
| table (floating) | 0 | no — sample 4: ~4/5 |
| line | 0 | no — sample 4: 0/6 |

The empty `<hp:t>` has no text — it is an anchor for the inline object's character
position. The `t`-count gap (s3 ×33, s4 ×25) equals exactly the missing inline-
object empty `<hp:t>` elements; visible text is otherwise identical (measured:
same `textlen` 14235 on sample 3, so no text is dropped).

### Our writer already fixes `treatAsChar`

`_write_table` emits `treatAsChar="1"` unconditionally (our tables are always
inline in output today); `_write_pic`/`_write_line` emit `treatAsChar=
str(pos.treat_as_char)` from the drawing's `inline` flag. So "inline as we emit
it" = every table run + every `treat_as_char==1` drawing run.

### Measured effect (end-to-end prototype of the rule)

| | before | after |
|---|---|---|
| sample 3 `section0` match | 0.9937 | **0.9988** (`t` miss 33 → 0) |
| sample 4 `section0` match | 0.9963 | **0.9994** (`t` miss 25 → 0) |

Sample 4 note: because our writer emits every table as `treatAsChar="1"`, we add
an empty `<hp:t>` to the ~4 *floating* tables that Hancom leaves bare. This is
**score-neutral** (fidelity scores `min(ours, theirs)` per tag; and the sample-4
`t` count still lands exactly on Hancom's total because Hancom carries an equal
number of empty `<hp:t>` elsewhere). Correcting floating-table `treatAsChar` is a
separate concern (see Non-goals).

## The rule

In the writer's `_write_run`, after writing a run's object:
- If the run carries a **table** → it is inline in our output → append a trailing
  empty `<hp:t/>`.
- If the run carries a **drawing** whose `pos.treat_as_char == 1` → append a
  trailing empty `<hp:t/>`.
- Otherwise (floating drawing, or a text/empty run) → no change.

The `<hp:t/>` is the run's last child, after the `<hp:tbl>`/`<hp:pic>`.

## Architecture (writer-only)

**Writer (`owpml/section_writer.py`, `_write_run`):** track whether an inline
object was written; after the table/drawing dispatch, if so, `etree.SubElement(r,
_hp("t"))` (an empty element). No model or mapper change — `Run.texts` stays
empty for object runs, so mapper-level tests are untouched; the anchor `<hp:t>`
is a serialization detail.

- `Line` and `Pic` both carry `pos: ShapePos` with `treat_as_char`; access via
  `run.drawing.pos.treat_as_char` (guard for `pos is None`).

## Error handling

- A drawing run whose `pos` is `None` → treated as not-inline (no empty `<hp:t>`);
  never raises.
- A run with neither table nor drawing → unchanged.
- A run that already emitted a `<hp:t>` from its `texts` (a text run) never
  reaches the object branch (object runs have empty `texts` per the reader), so no
  double `<hp:t>`.

## Testing strategy (TDD)

- **Writer unit tests** (build a `Run` and call `_write_run`):
  - a run with a `Table` → serializes with a trailing empty `<hp:t/>` after the
    `<hp:tbl>` (last child is `t`, with no text).
  - a run with an inline `Pic` (`pos.treat_as_char == 1`) → trailing empty
    `<hp:t/>` after `<hp:pic>`.
  - a run with a floating `Line` (`pos.treat_as_char == 0`) → **no** trailing
    `<hp:t>`.
  - a plain text run → exactly one `<hp:t>` with its text (unchanged; no extra).
- **End-to-end / fidelity:**
  - Sample 3: `section0.xml` `t` miss count is 0; match rises to ≥ 0.998.
  - Sample 4: `section0.xml` `t` miss count is 0; match rises to ≥ 0.999; the
    inline pictures and inline tables each carry a trailing empty `<hp:t>`.
- **Regression:** the markpen-era sample-3 byte-identity guard
  (`tests/test_convert_markpen.py::test_sample3_section_unchanged`) must be
  re-baselined — this milestone legitimately changes sample 3's `section0.xml`
  (adds 33 empty `<hp:t>`): new `len 496827`, `sha256` prefix `022bef521a01b5c1`.
  The trailing-empty-run e2e tests (`test_convert_trailing_run.py`) still hold
  (run counts unchanged; match thresholds only rise). Markpen marker tests stay
  green.

## Non-goals

- Correcting `treatAsChar` for floating tables (we hardcode `"1"`; a floating
  table should be `"0"`). That needs the reader to capture table position/inline
  from HWP — a separate milestone. This milestone's `t` count matches Hancom
  exactly regardless, and the over-emission is score-neutral.
- The remaining inline `ctrl` markers (`pageNum`/`newNum`/`pageHiding`/`titleMark`/
  `bookmark`) that also live in these object runs — separate milestone.
- Non-`<hp:t/>` serialization nuance (`<hp:t></hp:t>` vs `<hp:t/>`) — both are one
  `t` element; scoring parses XML so they are equivalent.

## Key risks

- **Over-emission on floating tables** — score-neutral (see above); if a future
  document's floating-table count diverges it still cannot lower the `t` match,
  and the empty anchor renders nothing. Bounded and documented.
- **Double `<hp:t>`** — impossible: object runs have empty `texts`, so the text
  branch never runs for them.
- **Sample-3 regression guard churn** — handled by re-baselining the markpen
  no-change test to the new bytes (documented), not by weakening it.
