# charPr Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit the full `<hh:charPr>` subtree (per-language `fontRef`/`ratio`/`spacing`/`relSz`/`offset`, plus `shadeColor`/`useFontSpace`/`useKerning`/`symMark`/`borderFillIDRef` and `underline`/`strikeout`/`outline`/`shadow`) so `header.xml` fidelity rises from 71.2%.

**Architecture:** Extend the existing 4 layers (Reader → HWP model → Mapper → OWPML model → Writer). No new layer. `HwpCharShape`/`CharPr` gain per-language dicts and the new scalar attributes; the reader parses them, the mapper translates HWP language keys to OWPML keys and applies the `shadeColor`/`underline`/`outline`/`shadow` transforms, and `header_writer` emits the full subtree.

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc xml`), pytest.

## Global Constraints

- **Python 3.9 floor:** NO PEP 604 `X | None` union syntax (breaks at class-definition time). Use bare `field: T = None` / `field(default_factory=dict)`.
- **Language-key correspondence (HWP → OWPML):** `ko→hangul`, `en→latin`, `cn→hanja`, `jp→japanese`, `other→other`, `symbol→symbol`, `user→user`.
- **`fontRef` values = global font index** `group_offset[lang] + FontFace@lang` (reader's existing `_font_group_offsets`), NOT Hancom's reordered integers. Consequence: only `fontRef` integers may differ from Hancom; every other charPr value matches Hancom byte-for-byte.
- **`charPr@borderFillIDRef` = `"1"`** always (pyhwp exposes no per-CharShape border-fill id; id 1 is always defined, so it never dangles).
- **charPr child order (exact):** `fontRef, ratio, spacing, relSz, offset, italic?, bold?, underline, strikeout, outline, shadow`. `italic`/`bold` are empty elements emitted only when set.
- **No dangling refs:** every emitted ref must resolve.
- Keep existing `HwpCharShape.font_id` and `CharPr.font_ref_id` fields intact (back-compat with current tests); the new `font_ref` dict supersedes them for the writer.

---

### Task 1: Model fields for full charPr

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py` (HwpCharShape)
- Modify: `hwp2hwpx/owpml/model.py` (CharPr)
- Test: `tests/test_model_charpr_fields.py`

**Interfaces:**
- Produces: `HwpCharShape` with new fields `font_ref`, `ratio`, `spacing`, `rel_sz`, `offset` (dicts, HWP-keyed `ko/en/cn/jp/other/symbol/user`), `shade_color: str`, `underline_type/underline_shape/underline_color: str`, `strikeout_shape/strikeout_color: str`, `outline_type: str`, `shadow_type/shadow_color: str`, `shadow_offset_x/shadow_offset_y: int`. `CharPr` with `font_ref`, `ratio`, `spacing`, `rel_sz`, `offset` (dicts, OWPML-keyed), `shade_color`, `border_fill_id: int`, and the same underline/strikeout/outline/shadow scalars.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_charpr_fields.py
from hwp2hwpx.hwpmodel.model import HwpCharShape
from hwp2hwpx.owpml.model import CharPr


def test_hwp_char_shape_new_fields_default():
    cs = HwpCharShape(index=0, base_size=1000)
    assert cs.font_ref == {}
    assert cs.ratio == {}
    assert cs.shade_color == "#ffffff"
    assert cs.underline_type == "NONE"
    assert cs.underline_shape == "SOLID"
    assert cs.strikeout_shape == "NONE"
    assert cs.outline_type == "NONE"
    assert cs.shadow_type == "NONE"
    assert cs.shadow_offset_x == 10
    assert cs.shadow_offset_y == 10


def test_owpml_charpr_new_fields_default():
    cp = CharPr(id=0)
    assert cp.font_ref == {}
    assert cp.ratio == {}
    assert cp.border_fill_id == 1
    assert cp.shade_color == "none"
    assert cp.underline_type == "NONE"
    assert cp.shadow_type == "NONE"
    assert cp.shadow_offset_x == 10
    # existing fields still present
    assert cp.height == 1000
    assert cp.font_ref_id == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_model_charpr_fields.py -v`
Expected: FAIL (AttributeError / TypeError on unknown fields)

- [ ] **Step 3: Add fields to HwpCharShape** in `hwp2hwpx/hwpmodel/model.py`

Replace the `HwpCharShape` dataclass with:

```python
@dataclass
class HwpCharShape:
    index: int
    base_size: int
    text_color: str = "#000000"
    font_id: int = 0
    bold: bool = False
    italic: bool = False
    font_ref: dict = field(default_factory=dict)   # HWP-keyed: ko/en/cn/jp/other/symbol/user -> global font index
    ratio: dict = field(default_factory=dict)       # HWP-keyed -> int (LetterWidthExpansion)
    spacing: dict = field(default_factory=dict)     # HWP-keyed -> int (LetterSpacing)
    rel_sz: dict = field(default_factory=dict)      # HWP-keyed -> int (RelativeSize)
    offset: dict = field(default_factory=dict)      # HWP-keyed -> int (Position)
    shade_color: str = "#ffffff"
    underline_type: str = "NONE"
    underline_shape: str = "SOLID"
    underline_color: str = "#000000"
    strikeout_shape: str = "NONE"
    strikeout_color: str = "#000000"
    outline_type: str = "NONE"
    shadow_type: str = "NONE"
    shadow_color: str = "#C0C0C0"
    shadow_offset_x: int = 10
    shadow_offset_y: int = 10
```

- [ ] **Step 4: Add fields to CharPr** in `hwp2hwpx/owpml/model.py`

Replace the `CharPr` dataclass with:

```python
@dataclass
class CharPr:
    id: int
    height: int = 1000
    text_color: str = "#000000"
    font_ref_id: int = 0
    bold: bool = False
    italic: bool = False
    font_ref: dict = field(default_factory=dict)   # OWPML-keyed: hangul/latin/hanja/japanese/other/symbol/user -> int
    ratio: dict = field(default_factory=dict)
    spacing: dict = field(default_factory=dict)
    rel_sz: dict = field(default_factory=dict)
    offset: dict = field(default_factory=dict)
    shade_color: str = "none"
    border_fill_id: int = 1
    underline_type: str = "NONE"
    underline_shape: str = "SOLID"
    underline_color: str = "#000000"
    strikeout_shape: str = "NONE"
    strikeout_color: str = "#000000"
    outline_type: str = "NONE"
    shadow_type: str = "NONE"
    shadow_color: str = "#C0C0C0"
    shadow_offset_x: int = 10
    shadow_offset_y: int = 10
```

(`field` is already imported in both modules.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_model_charpr_fields.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py tests/test_model_charpr_fields.py
git commit -m "feat: charShape/charPr model fields for full charPr"
```

---

### Task 2: Reader parses full CharShape

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`
- Test: `tests/test_reader_charpr_full.py`

**Interfaces:**
- Consumes: `HwpCharShape` fields from Task 1; existing `_font_group_offsets`, `_int`.
- Produces: `read_docinfo` fills every new `HwpCharShape` field. `font_ref[lang] = offsets[lang] + FontFace@lang`; `ratio/spacing/rel_sz/offset` are raw per-language values; `underline_type` = `BOTTOM` when `underline="underline"` else `NONE`; `outline_type` = `SOLID` when `outline` nonzero else `NONE`; `shadow_type` = `DROP` when `shadow` nonzero else `NONE`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader_charpr_full.py
from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _docinfo():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read())


def test_char_shape_font_ref_is_global_index():
    di = _docinfo()
    cs = di.char_shapes[0]
    # CharShape[0] FontFace ko=12 (hangul group offset 0) -> global 12
    assert cs.font_ref["ko"] == 12
    # en=10, latin group offset = ko-fonts(14) -> global 24
    assert cs.font_ref["en"] == 24
    # every ref resolves within the flat font list
    assert all(0 <= v < len(di.fonts) for v in cs.font_ref.values())


def test_char_shape_per_language_metrics():
    di = _docinfo()
    cs = di.char_shapes[0]
    assert cs.ratio["ko"] == 100
    assert cs.spacing["ko"] == 0
    assert cs.rel_sz["ko"] == 100
    assert cs.offset["ko"] == 0
    assert set(cs.ratio.keys()) == {"ko", "en", "cn", "jp", "other", "symbol", "user"}


def test_char_shape_effects_and_shade():
    di = _docinfo()
    cs = di.char_shapes[0]
    assert cs.shade_color == "#ffffff"
    assert cs.underline_type == "NONE"
    assert cs.shadow_type == "NONE"
    assert cs.shadow_offset_x == 10
    assert cs.shadow_offset_y == 10
    # some CharShape in the doc has underline="underline"
    assert any(c.underline_type == "BOTTOM" for c in di.char_shapes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_reader_charpr_full.py -v`
Expected: FAIL (font_ref empty / KeyError)

- [ ] **Step 3: Add parse helpers and extend the CharShape loop** in `hwp2hwpx/hwpmodel/reader.py`

Add these module-level helpers (after `_font_group_offsets`):

```python
def _lang_metric(el, default):
    """Per-language child element -> HWP-keyed dict of ints (raw values)."""
    d = {}
    for lang in _FONT_LANGS:
        d[lang] = _int(el.get(lang), default) if el is not None else default
    return d


def _font_ref(ff, offsets):
    """FontFace element -> HWP-keyed dict of global font indices."""
    d = {}
    for lang in _FONT_LANGS:
        local = _int(ff.get(lang), 0) if ff is not None else 0
        d[lang] = offsets.get(lang, 0) + local
    return d
```

Replace the `CharShape` loop in `read_docinfo` (the `for i, el in enumerate(id_mappings.findall("CharShape"))` block) with:

```python
    char_shapes = []
    for i, el in enumerate(id_mappings.findall("CharShape")):
        ff = el.find("FontFace")
        ko_local = _int(ff.get("ko")) if ff is not None else 0
        font_ref = _font_ref(ff, offsets)
        underline_raw = (el.get("underline") or "none").lower()
        char_shapes.append(HwpCharShape(
            index=i,
            base_size=_int(el.get("basesize"), 1000),
            text_color=el.get("text-color") or "#000000",
            font_id=offsets.get("ko", 0) + ko_local,
            bold=el.get("bold") == "1",
            italic=el.get("italic") == "1",
            font_ref=font_ref,
            ratio=_lang_metric(el.find("LetterWidthExpansion"), 100),
            spacing=_lang_metric(el.find("LetterSpacing"), 0),
            rel_sz=_lang_metric(el.find("RelativeSize"), 100),
            offset=_lang_metric(el.find("Position"), 0),
            shade_color=el.get("shade-color") or "#ffffff",
            underline_type="BOTTOM" if underline_raw not in ("none", "") else "NONE",
            underline_shape=(el.get("underline-style") or "solid").upper(),
            underline_color=el.get("underline-color") or "#000000",
            outline_type="SOLID" if _int(el.get("outline")) else "NONE",
            shadow_type="DROP" if _int(el.get("shadow")) else "NONE",
            shadow_color=(el.get("shadow-color") or "#c0c0c0").upper(),
            shadow_offset_x=_shadow_space(el, "x"),
            shadow_offset_y=_shadow_space(el, "y"),
        ))
```

Add the `_shadow_space` helper (after `_font_ref`):

```python
def _shadow_space(char_shape_el, axis):
    """ShadowSpace/@x|@y -> int (default 10)."""
    ss = char_shape_el.find("ShadowSpace")
    return _int(ss.get(axis), 10) if ss is not None else 10
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_reader_charpr_full.py tests/test_reader_docinfo.py -v`
Expected: PASS (new tests + existing docinfo tests, including `font_id == 12`)

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_charpr_full.py
git commit -m "feat: parse full HWP CharShape (per-language metrics, effects)"
```

---

### Task 3: Mapper builds full CharPr

**Files:**
- Modify: `hwp2hwpx/mapper/char_pr.py`
- Test: `tests/test_mapper_charpr_full.py`

**Interfaces:**
- Consumes: `HwpCharShape` (Task 2 fields), `CharPr` (Task 1 fields).
- Produces: `map_char_shapes(list[HwpCharShape]) -> list[CharPr]` with OWPML-keyed dicts (`hangul/latin/...`), `shade_color` mapped (`#ffffff`→`none`), `border_fill_id=1`, effects passed through. Existing `id/height/text_color/font_ref_id/bold/italic` unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mapper_charpr_full.py
from hwp2hwpx.mapper.char_pr import map_char_shapes
from hwp2hwpx.hwpmodel.model import HwpCharShape


def _src(**kw):
    base = dict(index=0, base_size=1000,
                font_ref={"ko": 12, "en": 24, "cn": 3, "jp": 3,
                          "other": 3, "symbol": 3, "user": 3},
                ratio={l: 100 for l in ("ko", "en", "cn", "jp", "other", "symbol", "user")},
                spacing={l: 0 for l in ("ko", "en", "cn", "jp", "other", "symbol", "user")})
    base.update(kw)
    return HwpCharShape(**base)


def test_font_ref_language_key_translation():
    out = map_char_shapes([_src()])
    fr = out[0].font_ref
    assert fr["hangul"] == 12
    assert fr["latin"] == 24
    assert fr["hanja"] == 3
    assert fr["japanese"] == 3
    assert set(fr.keys()) == {"hangul", "latin", "hanja", "japanese", "other", "symbol", "user"}


def test_shade_color_white_becomes_none():
    assert map_char_shapes([_src(shade_color="#ffffff")])[0].shade_color == "none"
    assert map_char_shapes([_src(shade_color="#FF0000")])[0].shade_color == "#FF0000"


def test_border_fill_id_is_one():
    assert map_char_shapes([_src()])[0].border_fill_id == 1


def test_effects_passthrough():
    out = map_char_shapes([_src(underline_type="BOTTOM", underline_shape="SOLID",
                                outline_type="SOLID", shadow_type="DROP",
                                shadow_color="#B2B2B2", shadow_offset_x=10)])
    cp = out[0]
    assert cp.underline_type == "BOTTOM"
    assert cp.outline_type == "SOLID"
    assert cp.shadow_type == "DROP"
    assert cp.shadow_color == "#B2B2B2"
    assert cp.ratio["hangul"] == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mapper_charpr_full.py -v`
Expected: FAIL (font_ref not translated / shade_color unchanged)

- [ ] **Step 3: Rewrite `map_char_shapes`** in `hwp2hwpx/mapper/char_pr.py`

```python
"""Map HWP character shapes to OWPML charPr."""
from ..owpml.model import CharPr

# HWP language key -> OWPML language key.
_LANG_MAP = {
    "ko": "hangul", "en": "latin", "cn": "hanja", "jp": "japanese",
    "other": "other", "symbol": "symbol", "user": "user",
}


def _translate(d, default):
    """HWP-keyed per-language dict -> OWPML-keyed dict."""
    return {owpml: d.get(hwp, default) for hwp, owpml in _LANG_MAP.items()}


def _shade_color(v):
    """HWP shade-color #ffffff (or empty) -> OWPML 'none'; else passthrough."""
    if not v or v.lower() in ("#ffffff", "none"):
        return "none"
    return v


def map_char_shapes(shapes):
    out = []
    for cs in shapes:
        out.append(CharPr(
            id=cs.index,
            height=cs.base_size,
            text_color=cs.text_color,
            font_ref_id=cs.font_id,
            bold=cs.bold,
            italic=cs.italic,
            font_ref=_translate(cs.font_ref, 0),
            ratio=_translate(cs.ratio, 100),
            spacing=_translate(cs.spacing, 0),
            rel_sz=_translate(cs.rel_sz, 100),
            offset=_translate(cs.offset, 0),
            shade_color=_shade_color(cs.shade_color),
            border_fill_id=1,
            underline_type=cs.underline_type,
            underline_shape=cs.underline_shape,
            underline_color=cs.underline_color,
            strikeout_shape=cs.strikeout_shape,
            strikeout_color=cs.strikeout_color,
            outline_type=cs.outline_type,
            shadow_type=cs.shadow_type,
            shadow_color=cs.shadow_color,
            shadow_offset_x=cs.shadow_offset_x,
            shadow_offset_y=cs.shadow_offset_y,
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mapper_charpr_full.py tests/test_mapper_charpr.py -v`
Expected: PASS (new + existing mapper tests)

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/char_pr.py tests/test_mapper_charpr_full.py
git commit -m "feat: full charPr mapping (lang-key translation, shadeColor, effects)"
```

---

### Task 4: Writer emits full charPr subtree

**Files:**
- Modify: `hwp2hwpx/owpml/header_writer.py` (charProperties loop, lines ~82-95)
- Test: `tests/test_header_charpr_full.py`

**Interfaces:**
- Consumes: `CharPr` (Task 1/3 fields), existing `_hh` helper.
- Produces: each `<hh:charPr>` carries attributes `id height textColor shadeColor useFontSpace useKerning symMark borderFillIDRef` and children in order `fontRef, ratio, spacing, relSz, offset, italic?, bold?, underline, strikeout, outline, shadow`, each per-language child carrying 7 OWPML language attrs.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_header_charpr_full.py
from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, Font, CharPr, ParaPr
from hwp2hwpx.constants import NS

_LANGS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def _charpr(**kw):
    base = dict(id=0, height=1000, text_color="#000000",
                font_ref={l: 1 for l in _LANGS},
                ratio={l: 100 for l in _LANGS},
                spacing={l: 0 for l in _LANGS},
                rel_sz={l: 100 for l in _LANGS},
                offset={l: 0 for l in _LANGS})
    base.update(kw)
    return CharPr(**base)


def _first_charpr(header):
    root = etree.fromstring(header_xml(header))
    return root, next(root.iter(_hh("charPr")))


def test_charpr_attributes():
    header = Header(char_prs=[_charpr(shade_color="none", border_fill_id=1)],
                    para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    assert ce.get("height") == "1000"
    assert ce.get("textColor") == "#000000"
    assert ce.get("shadeColor") == "none"
    assert ce.get("useFontSpace") == "0"
    assert ce.get("useKerning") == "0"
    assert ce.get("symMark") == "NONE"
    assert ce.get("borderFillIDRef") == "1"


def test_charpr_fontref_seven_languages():
    header = Header(char_prs=[_charpr(font_ref={l: i for i, l in enumerate(_LANGS)})],
                    para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    fr = ce.find(_hh("fontRef"))
    assert fr.get("hangul") == "0"
    assert fr.get("user") == "6"
    assert all(fr.get(l) is not None for l in _LANGS)


def test_charpr_child_order():
    header = Header(char_prs=[_charpr(bold=True, italic=True)], para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    tags = [etree.QName(c).localname for c in ce]
    assert tags == ["fontRef", "ratio", "spacing", "relSz", "offset",
                    "italic", "bold", "underline", "strikeout", "outline", "shadow"]


def test_charpr_effects_emitted():
    header = Header(char_prs=[_charpr(underline_type="BOTTOM", underline_shape="SOLID",
                                      underline_color="#000000", outline_type="NONE",
                                      shadow_type="DROP", shadow_color="#B2B2B2",
                                      shadow_offset_x=10, shadow_offset_y=10)],
                    para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    ul = ce.find(_hh("underline"))
    assert ul.get("type") == "BOTTOM" and ul.get("shape") == "SOLID" and ul.get("color") == "#000000"
    sh = ce.find(_hh("shadow"))
    assert sh.get("type") == "DROP" and sh.get("color") == "#B2B2B2"
    assert sh.get("offsetX") == "10" and sh.get("offsetY") == "10"


def test_charpr_no_bold_when_unset():
    header = Header(char_prs=[_charpr()], para_prs=[ParaPr(id=0)])
    _, ce = _first_charpr(header)
    tags = [etree.QName(c).localname for c in ce]
    assert "bold" not in tags and "italic" not in tags
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_header_charpr_full.py -v`
Expected: FAIL (missing attrs/children)

- [ ] **Step 3: Rewrite the charProperties loop** in `hwp2hwpx/owpml/header_writer.py`

Replace the existing `for cp in header.char_prs:` block (the one starting at `ce = etree.SubElement(cps, _hh("charPr"))` through the `italic` handling) with:

```python
    _CP_LANGS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")
    for cp in header.char_prs:
        ce = etree.SubElement(cps, _hh("charPr"))
        ce.set("id", str(cp.id))
        ce.set("height", str(cp.height))
        ce.set("textColor", cp.text_color)
        ce.set("shadeColor", cp.shade_color)
        ce.set("useFontSpace", "0")
        ce.set("useKerning", "0")
        ce.set("symMark", "NONE")
        ce.set("borderFillIDRef", str(cp.border_fill_id))

        def _langset(tag, values, default):
            el = etree.SubElement(ce, _hh(tag))
            for lang in _CP_LANGS:
                el.set(lang, str(values.get(lang, default)))

        _langset("fontRef", cp.font_ref, 0)
        _langset("ratio", cp.ratio, 100)
        _langset("spacing", cp.spacing, 0)
        _langset("relSz", cp.rel_sz, 100)
        _langset("offset", cp.offset, 0)

        if cp.italic:
            etree.SubElement(ce, _hh("italic"))
        if cp.bold:
            etree.SubElement(ce, _hh("bold"))

        ul = etree.SubElement(ce, _hh("underline"))
        ul.set("type", cp.underline_type)
        ul.set("shape", cp.underline_shape)
        ul.set("color", cp.underline_color)

        st = etree.SubElement(ce, _hh("strikeout"))
        st.set("shape", cp.strikeout_shape)
        st.set("color", cp.strikeout_color)

        ol = etree.SubElement(ce, _hh("outline"))
        ol.set("type", cp.outline_type)

        sh = etree.SubElement(ce, _hh("shadow"))
        sh.set("type", cp.shadow_type)
        sh.set("color", cp.shadow_color)
        sh.set("offsetX", str(cp.shadow_offset_x))
        sh.set("offsetY", str(cp.shadow_offset_y))
```

Note: the closure `_langset` captures `ce` per iteration — it is defined inside the loop, so each iteration binds the current `ce`. This is intentional and correct.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_header_charpr_full.py tests/test_header_writer.py -v`
Expected: PASS (new + existing header tests, including the `height == "1000"` assertion)

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/header_writer.py tests/test_header_charpr_full.py
git commit -m "feat: emit full hh:charPr subtree (per-language metrics + effects)"
```

---

### Task 5: End-to-end / fidelity verification

**Files:**
- Test: `tests/test_convert_charpr.py`

**Interfaces:**
- Consumes: the full pipeline (`convert`), the fidelity harness (`hwp2hwpx.fidelity.diff`).

- [ ] **Step 1: Write the fidelity/regression test**

```python
# tests/test_convert_charpr.py
import zipfile
import re
from hwp2hwpx.convert import convert

SAMPLE_HWP = "samples/3.*.hwp"


def _out_header(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/header.xml").decode("utf-8")


def test_charpr_full_subtree_present(tmp_path):
    hdr = _out_header(tmp_path)
    # every charPr carries the new sub-elements and attributes
    assert "<hh:ratio " in hdr
    assert "<hh:spacing " in hdr
    assert "<hh:relSz " in hdr
    assert "<hh:offset " in hdr
    assert "<hh:underline " in hdr
    assert "<hh:strikeout " in hdr
    assert "<hh:outline " in hdr
    assert "<hh:shadow " in hdr
    assert 'symMark="NONE"' in hdr


def test_charpr_borderfill_refs_resolve(tmp_path):
    hdr = _out_header(tmp_path)
    defined = set(re.findall(r'<hh:borderFill id="(\d+)"', hdr))
    refs = set(re.findall(r'<hh:charPr[^>]*borderFillIDRef="(\d+)"', hdr))
    assert refs, "charPr must carry borderFillIDRef"
    assert refs <= defined, "no charPr borderFillIDRef may dangle"


def test_fontref_within_font_range(tmp_path):
    hdr = _out_header(tmp_path)
    # count fonts in the HANGUL bucket (flat list replicated per language)
    block = re.search(r'<hh:fontface lang="HANGUL".*?</hh:fontface>', hdr, re.S).group(0)
    n = len(re.findall(r'<hh:font ', block))
    hangul_refs = [int(v) for v in re.findall(r'<hh:fontRef[^>]*hangul="(\d+)"', hdr)]
    assert hangul_refs
    assert all(0 <= v < n for v in hangul_refs), "fontRef must resolve within its bucket"
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_convert_charpr.py -v`
Expected: PASS

- [ ] **Step 3: Run the full suite (regression)**

Run: `python -m pytest -q`
Expected: all green (existing 92 + new tests)

- [ ] **Step 4: Measure fidelity gain (informational)**

Run:
```bash
python -c "
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import report
import tempfile, os
out = os.path.join(tempfile.mkdtemp(), 'out.hwpx')
convert('samples/3.*.hwp', out)
print(report(out, 'samples/3.*.hwpx'))
"
```
Expected: `header.xml` match materially above 71.2%; `ratio`/`spacing`/`relSz`/`offset`/`underline`/`strikeout`/`outline`/`shadow` no longer dominate the header miss list. Record the number in the commit message.

- [ ] **Step 5: Commit**

```bash
git add tests/test_convert_charpr.py
git commit -m "test: end-to-end charPr fidelity + no dangling charPr borderFillIDRef"
```

---

## Self-Review

**Spec coverage:** fontRef/ratio/spacing/relSz/offset (Tasks 2-4), shadeColor/useFontSpace/useKerning/symMark/borderFillIDRef (Tasks 3-4), underline/strikeout/outline/shadow (Tasks 2-4), fontRef global-index decision (Task 2 + constraint), borderFillIDRef=1 decision (Task 3 + constraint), child order (Task 4), fidelity/no-dangling (Task 5). Covered.

**Placeholder scan:** none — every code step contains full code.

**Type consistency:** `HwpCharShape` fields (HWP-keyed dicts) produced in Task 1, filled in Task 2, consumed by `map_char_shapes` in Task 3; `CharPr` fields (OWPML-keyed dicts) produced in Task 1/3, consumed by the writer in Task 4. `_translate`/`_LANG_MAP` (Task 3) is the single HWP→OWPML translation point. `_CP_LANGS` (writer) and OWPML dict keys match. `border_fill_id` default 1 (Task 1) reinforced in Task 3.
