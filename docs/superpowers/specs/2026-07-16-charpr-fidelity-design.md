# HWP → HWPX Converter — charPr Fidelity Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestone 1 (text/char/para) + tables + paraPr fidelity, all merged to `main`.

## Goal

Emit the **full `<hh:charPr>`** subtree so `header.xml` fidelity rises from the current 71.2%. Today we emit only `id`, `height`, `textColor`, a single-valued `fontRef`, and `bold`/`italic`; the 103 charPr entries are the dominant remaining header miss. This milestone adds per-language `fontRef`/`ratio`/`spacing`/`relSz`/`offset`, the `shadeColor`/`useFontSpace`/`useKerning`/`symMark`/`borderFillIDRef` attributes, and `underline`/`strikeout`/`outline`/`shadow`.

Success = `header.xml` match rises materially; `ratio`/`spacing`/`relSz`/`offset`/`underline`/`strikeout`/`outline`/`shadow` leave the miss list; no dangling refs; output still opens in Hancom Office.

## Background — verified ground truth (sample 3)

**HWP `CharShape` attributes:** `basesize`, `bold`, `italic`, `outline`, `shadow`, `text-color`, `shade-color`, `shadow-color`, `underline`, `underline-color`, `underline-style`, `charshapeflags`.

**HWP `CharShape` children** (each with 7 per-language attrs `ko`/`en`/`cn`/`jp`/`other`/`symbol`/`user`, except `ShadowSpace`):
```
<FontFace ko en cn jp other symbol user/>              # → fontRef
<LetterWidthExpansion ko en …/>                        # → ratio
<LetterSpacing ko en …/>                               # → spacing
<RelativeSize ko en …/>                                # → relSz
<Position ko en …/>                                    # → offset
<ShadowSpace x y/>                                     # → shadow offsetX/offsetY
```

**Hancom `charPr` target:**
```
<hh:charPr id height textColor shadeColor useFontSpace useKerning symMark borderFillIDRef>
  <hh:fontRef hangul latin hanja japanese other symbol user/>
  <hh:ratio   hangul latin hanja japanese other symbol user/>
  <hh:spacing hangul latin hanja japanese other symbol user/>
  <hh:relSz   hangul latin hanja japanese other symbol user/>
  <hh:offset  hangul latin hanja japanese other symbol user/>
  <hh:italic/>                 # only when set
  <hh:bold/>                   # only when set (after offset, before underline — verified)
  <hh:underline type shape color/>
  <hh:strikeout shape color/>
  <hh:outline type/>
  <hh:shadow type color offsetX offsetY/>
</hh:charPr>
```
Language-attr correspondence: `hangul←ko`, `latin←en`, `hanja←cn`, `japanese←jp`, `other←other`, `symbol←symbol`, `user←user`.

## Decisions

**1. `fontRef` values = global font index per language, not Hancom's integers.**
Hancom emits per-language 0-indexed values into *reordered* per-language font blocks (it moves fonts, e.g. 돋움 to the end of the HANGUL block, so HWP `ko=12` → Hancom `hangul=11`). Our `mapper/fonts.py` replicates the **full flat FaceName list** into every language bucket, so the identity-correct reference is the **global** index `group_offset[lang] + FontFace@lang` (the reader already computes `_font_group_offsets`). This resolves to the right font within our buckets. Replicating Hancom's cosmetic font-reorder is out of scope. Consequence: `ratio`/`spacing`/`relSz`/`offset`/`underline`/`strikeout`/`outline`/`shadow` match Hancom byte-for-byte; `fontRef` integers may differ by Hancom's reorder but are correct by font identity and never dangle.

**2. `charPr@borderFillIDRef` = fixed `"1"`.**
Hancom varies it per charPr (character shading), but **pyhwp does not expose any per-`CharShape` border-fill id** (verified: absent from the attribute set). A fixed reference to the always-present borderFill id `1` resolves cleanly with no dangling. Real per-character shading fills are a later milestone.

**3. Attribute/child transforms:**
- `shadeColor`: `shade-color="#ffffff"` (or empty/`"none"`) → `"none"`; otherwise passthrough.
- `useFontSpace="0"`, `useKerning="0"`, `symMark="NONE"` (constant; `charshapeflags` all zero in samples).
- `height` ← `basesize`; `textColor` ← `text-color` (passthrough).
- `ratio`/`spacing`/`relSz`/`offset`: per-language passthrough from `LetterWidthExpansion`/`LetterSpacing`/`RelativeSize`/`Position` (defaults 100/0/100/0).
- `italic`/`bold`: empty child elements, emitted only when the HWP attr is `"1"`, in order `italic` then `bold`, positioned after `offset` and before `underline`.
- `underline`: `underline="none"` → `type="NONE"`; `underline="underline"` → `type="BOTTOM"`; `shape` = `underline-style` uppercased (`solid`→`SOLID`); `color` = `underline-color`.
- `strikeout`: `shape="NONE"`, `color="#000000"` (flag not exposed by pyhwp; samples have none).
- `outline`: `outline="0"` → `type="NONE"`; nonzero → `type="SOLID"`.
- `shadow`: `shadow="0"` → `type="NONE"`; nonzero → `type="DROP"`; `color` = `shadow-color` uppercased (Hancom emits upper-case hex, e.g. `#C0C0C0`); `offsetX`/`offsetY` = `ShadowSpace/@x`,`@y` (default 10/10).

## Architecture (extends existing layers)

**Model (`hwpmodel/model.py`, `owpml/model.py`):**
- `HwpCharShape` gains: `font_ref` (dict lang→global int), `ratio`, `spacing`, `rel_sz`, `offset` (dicts lang→int), `shade_color`, `underline_type`, `underline_shape`, `underline_color`, `strikeout_shape`, `strikeout_color`, `outline_type`, `shadow_type`, `shadow_color`, `shadow_offset_x`, `shadow_offset_y`. Keep existing `base_size`, `text_color`, `bold`, `italic`; `font_id` may remain for back-compat but is superseded by `font_ref`.
- `CharPr` gains the OWPML-side equivalents: `font_ref` (dict of the 7 OWPML lang keys → int), `ratio`, `spacing`, `rel_sz`, `offset` (dicts), `shade_color`, `border_fill_id`, `underline_type`, `underline_shape`, `underline_color`, `strikeout_shape`, `strikeout_color`, `outline_type`, `shadow_type`, `shadow_color`, `shadow_offset_x`, `shadow_offset_y`. Keep `id`, `height`, `text_color`, `bold`, `italic`.

The 7 language keys: OWPML side uses `hangul/latin/hanja/japanese/other/symbol/user`; HWP side uses `ko/en/cn/jp/other/symbol/user`. The mapper translates keys.

**Reader (`hwpmodel/reader.py`):** parse all 7-language children and new attrs into `HwpCharShape`. `font_ref[lang] = offsets[lang] + FontFace@lang` for each of the 7 HWP languages (reuse `_font_group_offsets`). Missing children/attrs fall back to the documented defaults.

**Mapper (`mapper/char_pr.py`):** `map_char_shapes` builds the full `CharPr`, translating HWP language keys to OWPML keys and applying the `shadeColor`/`underline`/`outline`/`shadow` transforms. `border_fill_id` set to 1.

**Writer (`owpml/header_writer.py`):** emit the full `<hh:charPr>` subtree — the 8 element attributes and children in the exact order (`fontRef, ratio, spacing, relSz, offset, italic?, bold?, underline, strikeout, outline, shadow`).

**Fidelity harness:** existing; confirm header.xml gain and that the new sub-elements leave the miss list.

## Error handling
- Missing/malformed `CharShape` attrs or children fall back to Hancom-safe defaults (never crash): ratio/relSz 100, spacing/offset 0, underline NONE, outline NONE, shadow NONE, shadow offsets 10/10.
- A `FontFace@lang` beyond its group falls back to `group_offset[lang]` (the group's first font) so `fontRef` never dangles.
- `borderFillIDRef` is always `1` (always defined).

## Testing strategy (TDD)
- **Reader:** a known `CharShape` parses to the expected per-language `font_ref` (global index = offset+local), `ratio`/`spacing`/`rel_sz`/`offset` dicts, and `underline`/`shadow`/`shade_color` fields (fixture-backed).
- **Mapper:** HWP→OWPML language-key translation; `shade-color="#ffffff"`→`"none"`; `underline="underline"`→`type="BOTTOM"`; `outline="1"`→`SOLID`; `shadow="1"`→`DROP`; `border_fill_id==1`.
- **Writer:** `header_xml` emits `charPr` with the 8 attributes and children in exact order; `fontRef`/`ratio`/`spacing`/`relSz`/`offset` carry 7 language attrs; `italic`/`bold` only when set.
- **End-to-end / fidelity:** convert real samples; assert `ratio`/`spacing`/`relSz`/`offset`/`underline`/`strikeout`/`outline`/`shadow` gone from top-missing; every `charPr@borderFillIDRef` resolves; header.xml match up materially; regression suite green; smoke opens in Hancom.

## Non-goals (this milestone)
- Real per-charPr `borderFillIDRef` and character-shading borderFills (pyhwp does not expose them).
- Replicating Hancom's per-language font reorder (cosmetic).
- `emboss`/`engrave`/`supscript`/`subscript` and other `charshapeflags` bits (all zero in samples).
- linesegarray layout metadata; images; real numbering/bullets/styles.

## Key risks
- **fontRef global-index correctness** — mitigated by the reader's existing `_font_group_offsets` and a fixture test asserting `offset+local` for a known non-hangul language (e.g. latin).
- **charPr child order** — Hancom may be strict; mitigated by matching the verified sample order and the harness miss-list check.
- **Color-case / shadeColor mapping** — mitigated by per-value fidelity comparison against the sample (`shade-color #ffffff`→`none`, `shadow-color` uppercased).
