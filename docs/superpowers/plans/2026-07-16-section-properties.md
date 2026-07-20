# Section Properties (`<hp:secPr>`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit the `<hp:secPr>` cluster (page setup, columns, footnote/endnote config, page numbering, page border) at the start of `section0.xml`, derived from real HWP section records, structurally identical to Hancom's output on both samples.

**Architecture:** Extends the existing 4-layer pipeline (Reader → Mapper → Writer → fidelity). New HWP-side dataclasses (`HwpSectionDef` + sub-records) and OWPML-side dataclasses (`SecPr` + children); a reader parser scoped per-`SectionDef`; a new `mapper/section.py`; a writer that injects a leading `secPr`-bearing run into paragraph 0 of each section.

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc xml`), pytest.

## Global Constraints

- **Python 3.9 floor:** NO PEP 604 `X | None`. Use forward-ref-string defaults (`x: "T" = None`) and `field(default_factory=...)`.
- **Run tests with `.venv/bin/python -m pytest`** — plain `python`/`python3` lacks `hwp5proc` and yields ~13 spurious failures.
- **Primary correctness gate = exact `secPr` subtree equality vs Hancom** on both samples (tag, attribute dict, text, ordered children — recursively). The count-based harness is a secondary sanity check only.
- **Values HWP carries are mapped from HWP; Hancom-injected constants** (`tabStopVal="4000"`, `tabStopUnit="HWPUNIT"`, `id=""`, `memoShapeIDRef="0"`, `textVerticalWidthHead="0"`, `masterPageCnt="0"`, `lineNumberShape` all 0, `autoNumFormat type="DIGIT"`/`supscript="0"`, `numbering type="CONTINUOUS"`, `placement beneathText="0"`, `visibility fill="SHOW_ALL"`/`showLineNumber="0"`, `colPr sameGap="0"`) are emitted verbatim and commented as constants.
- **Control scan is scoped per-section** (a `SectionDef`'s own first paragraph), never a global `.//` document scan.
- **Missing record → model field `None`/empty → emit nothing** (no crash, no fabricated element).
- Samples live at `samples/3.*.hwp[x]` and `samples/4.*.hwp[x]` (git-ignored, present locally). Reader unit tests use the in-repo fixture `tests/fixtures/sample3.hwp5.xml`.

### Verified enum mappings (source of truth for the mapper)

| HWP | OWPML |
|---|---|
| `text-direction` 0 | `textDirection="HORIZONTAL"` |
| `orientation` portrait / landscape | `landscape="WIDELY"` / `"NARROWLY"` |
| `bookbinding` left | `gutterType="LEFT_ONLY"` |
| `direction` l2r | `colPr layout="LEFT"` |
| `kind` normal | `colPr type="NEWSPAPER"` |
| `stroke-type` solid / none | `noteLine type="SOLID"` / `"NONE"` |
| `position` bottom_center | `pageNum pos="BOTTOM_CENTER"` |
| `shape` 0 | `pageNum formatType="DIGIT"` |
| `relative-to`/`fill` paper | `textBorder`/`fillArea="PAPER"` |
| `pagenum-on-split-section` 0 | `startNum pageStartsOn="BOTH"` |
| `width` `"0.12mm"` | `noteLine width="0.12 mm"` (space before `mm`) |
| pageBorderFill index 0/1/2 | `type="BOTH"/"EVEN"/"ODD"` |
| footnote / endnote | `placement place="EACH_COLUMN"` / `"END_OF_DOCUMENT"` |

---

### Task 1: HWP-side section dataclasses

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py`
- Test: `tests/test_model_section.py`

**Interfaces:**
- Produces: `HwpPageDef`, `HwpNoteShape`, `HwpPageBorder`, `HwpColumnsDef`, `HwpPageNum`, `HwpSectionDef`; `HwpSection.sec_def` field. These are the Reader's output / Mapper's input for Task 3 & 4.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_section.py
from hwp2hwpx.hwpmodel.model import (
    HwpPageDef, HwpNoteShape, HwpPageBorder, HwpColumnsDef, HwpPageNum,
    HwpSectionDef, HwpSection,
)


def test_section_records_default_construct():
    assert HwpPageDef().width == 0
    assert HwpNoteShape().stroke_type == "none"
    assert HwpPageBorder().borderfill_id == 1
    assert HwpColumnsDef().count == 1
    assert HwpPageNum().position == "bottom_center"
    sd = HwpSectionDef()
    assert sd.page is None and sd.footnote is None and sd.page_borders == []
    assert sd.columns is None and sd.page_num is None


def test_hwpsection_carries_sec_def():
    s = HwpSection(paragraphs=[], sec_def=HwpSectionDef(column_spacing=1134))
    assert s.sec_def.column_spacing == 1134
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_section.py -v`
Expected: FAIL with `ImportError` (names not defined).

- [ ] **Step 3: Add the dataclasses**

Add to `hwp2hwpx/hwpmodel/model.py` (after `HwpTabDef`, before `HwpDocInfo`; keep `field` import which already exists):

```python
@dataclass
class HwpPageDef:
    width: int = 0
    height: int = 0
    orientation: str = "portrait"
    bookbinding: str = "left"
    bookbinding_offset: int = 0
    left_offset: int = 0
    right_offset: int = 0
    top_offset: int = 0
    bottom_offset: int = 0
    header_offset: int = 0
    footer_offset: int = 0


@dataclass
class HwpNoteShape:
    notes_spacing: int = 0
    prefix: str = ""
    suffix: str = ""
    usersymbol: str = ""
    stroke_type: str = "none"          # HWP `stroke-type` -> noteLine type
    line_width: str = "0.12mm"         # HWP `width` -> noteLine width
    splitter_length: int = 0
    splitter_color: str = "#000000"
    splitter_margin_top: int = 0
    splitter_margin_bottom: int = 0
    starting_number: int = 1


@dataclass
class HwpPageBorder:
    borderfill_id: int = 1
    relative_to: str = "paper"
    fill: str = "paper"
    include_header: int = 0
    include_footer: int = 0
    margin_left: int = 0
    margin_right: int = 0
    margin_top: int = 0
    margin_bottom: int = 0


@dataclass
class HwpColumnsDef:
    count: int = 1
    kind: str = "normal"
    direction: str = "l2r"
    same_widths: int = 1


@dataclass
class HwpPageNum:
    position: str = "bottom_center"
    shape: int = 0
    dash: str = "-"


@dataclass
class HwpSectionDef:
    column_spacing: int = 0
    default_tab_stops: int = 0
    text_direction: int = 0
    grid_horizontal: int = 0
    grid_vertical: int = 0
    squared_manuscript_paper: int = 0
    numbering_shape_id: int = 0
    starting_pagenum: int = 0
    starting_picturenum: int = 0
    starting_tablenum: int = 0
    starting_equationnum: int = 0
    pagenum_on_split_section: int = 0
    hide_header: int = 0
    hide_footer: int = 0
    hide_border: int = 0
    hide_pagenumber: int = 0
    hide_blank_line: int = 0
    show_background_on_first_page_only: int = 0
    page: "HwpPageDef" = None
    footnote: "HwpNoteShape" = None
    endnote: "HwpNoteShape" = None
    page_borders: list = field(default_factory=list)
    columns: "HwpColumnsDef" = None
    page_num: "HwpPageNum" = None
```

Modify `HwpSection`:

```python
@dataclass
class HwpSection:
    paragraphs: list = field(default_factory=list)
    sec_def: "HwpSectionDef" = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_section.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py tests/test_model_section.py
git commit -m "feat: HWP-side section definition dataclasses"
```

---

### Task 2: OWPML-side section dataclasses

**Files:**
- Modify: `hwp2hwpx/owpml/model.py`
- Test: `tests/test_owpml_model_secpr.py`

**Interfaces:**
- Produces: `SecPr`, `Grid`, `StartNum`, `Visibility`, `LineNumberShape`, `PagePr`, `Margin`, `NotePr`, `AutoNumFormat`, `NoteLine`, `NoteSpacing`, `Numbering`, `Placement`, `PageBorderFill`, `Offset`, `ColPr`, `PageNum`; `Section.sec_pr` field. Consumed by the Mapper (Task 4) and Writer (Task 5). Field names below are the exact contract those tasks rely on.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_owpml_model_secpr.py
from hwp2hwpx.owpml.model import (
    SecPr, Grid, StartNum, Visibility, LineNumberShape, PagePr, Margin,
    NotePr, AutoNumFormat, NoteLine, NoteSpacing, Numbering, Placement,
    PageBorderFill, Offset, ColPr, PageNum, Section,
)


def test_secpr_defaults_are_hancom_constants():
    sp = SecPr()
    assert sp.id == ""
    assert sp.tab_stop_val == 4000
    assert sp.tab_stop_unit == "HWPUNIT"
    assert sp.memo_shape_id == 0
    assert sp.text_vertical_width_head == 0
    assert sp.master_page_cnt == 0
    assert sp.page_border_fills == []
    assert AutoNumFormat().type == "DIGIT"
    assert Numbering().type == "CONTINUOUS"
    assert LineNumberShape().restart_type == 0


def test_section_carries_sec_pr():
    s = Section(paras=[], sec_pr=SecPr(space_columns=1134))
    assert s.sec_pr.space_columns == 1134
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_owpml_model_secpr.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add the dataclasses**

Add to `hwp2hwpx/owpml/model.py` (after `TabDef`, before `Text`; `field` already imported):

```python
@dataclass
class Grid:
    line_grid: int = 0
    char_grid: int = 0
    wonggoji_format: int = 0


@dataclass
class StartNum:
    page_starts_on: str = "BOTH"
    page: int = 0
    pic: int = 0
    tbl: int = 0
    equation: int = 0


@dataclass
class Visibility:
    hide_first_header: int = 0
    hide_first_footer: int = 0
    hide_first_master_page: int = 0
    border: str = "SHOW_ALL"
    fill: str = "SHOW_ALL"
    hide_first_page_num: int = 0
    hide_first_empty_line: int = 0
    show_line_number: int = 0


@dataclass
class LineNumberShape:
    restart_type: int = 0
    count_by: int = 0
    distance: int = 0
    start_number: int = 0


@dataclass
class Margin:
    header: int = 0
    footer: int = 0
    gutter: int = 0
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class PagePr:
    landscape: str = "WIDELY"
    width: int = 0
    height: int = 0
    gutter_type: str = "LEFT_ONLY"
    margin: "Margin" = None


@dataclass
class AutoNumFormat:
    type: str = "DIGIT"
    user_char: str = ""
    prefix_char: str = ""
    suffix_char: str = ""
    supscript: int = 0


@dataclass
class NoteLine:
    length: int = 0
    type: str = "SOLID"
    width: str = "0.12 mm"
    color: str = "#000000"


@dataclass
class NoteSpacing:
    between_notes: int = 0
    below_line: int = 0
    above_line: int = 0


@dataclass
class Numbering:
    type: str = "CONTINUOUS"
    new_num: int = 1


@dataclass
class Placement:
    place: str = "EACH_COLUMN"
    beneath_text: int = 0


@dataclass
class NotePr:
    auto_num_format: "AutoNumFormat" = None
    note_line: "NoteLine" = None
    note_spacing: "NoteSpacing" = None
    numbering: "Numbering" = None
    placement: "Placement" = None


@dataclass
class Offset:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class PageBorderFill:
    type: str = "BOTH"
    border_fill_id: int = 1
    text_border: str = "PAPER"
    header_inside: int = 0
    footer_inside: int = 0
    fill_area: str = "PAPER"
    offset: "Offset" = None


@dataclass
class ColPr:
    type: str = "NEWSPAPER"
    layout: str = "LEFT"
    col_count: int = 1
    same_sz: int = 1
    id: str = ""
    same_gap: int = 0


@dataclass
class PageNum:
    pos: str = "BOTTOM_CENTER"
    format_type: str = "DIGIT"
    side_char: str = "-"


@dataclass
class SecPr:
    text_direction: str = "HORIZONTAL"
    space_columns: int = 0
    tab_stop: int = 0
    outline_shape_id: int = 0
    id: str = ""
    tab_stop_val: int = 4000
    tab_stop_unit: str = "HWPUNIT"
    memo_shape_id: int = 0
    text_vertical_width_head: int = 0
    master_page_cnt: int = 0
    grid: "Grid" = None
    start_num: "StartNum" = None
    visibility: "Visibility" = None
    line_number_shape: "LineNumberShape" = None
    page_pr: "PagePr" = None
    foot_note_pr: "NotePr" = None
    end_note_pr: "NotePr" = None
    page_border_fills: list = field(default_factory=list)
    col_pr: "ColPr" = None
    page_num: "PageNum" = None
```

Modify `Section`:

```python
@dataclass
class Section:
    paras: list = field(default_factory=list)
    sec_pr: "SecPr" = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_owpml_model_secpr.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/model.py tests/test_owpml_model_secpr.py
git commit -m "feat: OWPML-side SecPr dataclasses"
```

---

### Task 3: Reader parses `SectionDef`

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`
- Test: `tests/test_reader_section.py`

**Interfaces:**
- Consumes: `HwpSectionDef` + sub-records (Task 1); existing `_int` helper.
- Produces: `_parse_section_def(sec_el) -> HwpSectionDef`; `read_document` attaches it as `HwpSection.sec_def`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader_section.py
from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _sec_def():
    with open(FIXTURE, "rb") as f:
        return read_document(f.read()).sections[0].sec_def


def test_section_def_attached_and_scalar_fields():
    sd = _sec_def()
    assert sd is not None
    assert sd.column_spacing == 1134
    assert sd.default_tab_stops == 8000
    assert sd.text_direction == 0
    assert sd.hide_blank_line == 0


def test_page_def_parsed():
    p = _sec_def().page
    assert p.width == 59528 and p.height == 84188
    assert p.left_offset == 7088 and p.right_offset == 7088
    assert p.top_offset == 5668 and p.bottom_offset == 4252
    assert p.header_offset == 4252 and p.footer_offset == 4252
    assert p.orientation == "portrait" and p.bookbinding == "left"


def test_footnote_and_endnote_parsed():
    sd = _sec_def()
    assert sd.footnote.stroke_type == "solid"
    assert sd.footnote.splitter_length == -1
    assert sd.footnote.line_width == "0.12mm"
    assert sd.footnote.notes_spacing == 284
    assert sd.endnote.stroke_type == "none"
    assert sd.endnote.splitter_length == 0


def test_page_borders_parsed():
    b = _sec_def().page_borders
    assert len(b) == 3
    assert b[0].borderfill_id == 1
    assert b[0].margin_left == 1417 and b[0].margin_bottom == 1417
    assert b[0].relative_to == "paper" and b[0].fill == "paper"


def test_columns_and_page_num_scoped_to_first_paragraph():
    sd = _sec_def()
    assert sd.columns.count == 1 and sd.columns.kind == "normal"
    assert sd.columns.direction == "l2r"
    assert sd.page_num.position == "bottom_center"
    assert sd.page_num.dash == "-" and sd.page_num.shape == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reader_section.py -v`
Expected: FAIL (`AttributeError: 'HwpSection' object has no attribute 'sec_def'` is impossible since Task 1 added it → actually FAIL because `sec_def` is `None`: `AttributeError: 'NoneType' object has no attribute 'page'` / assertion on `None`).

- [ ] **Step 3: Add the parser and wire it in**

Add to `hwp2hwpx/hwpmodel/reader.py` (import the new model names at the top alongside the existing `HwpSection` import; add `HwpPageDef, HwpNoteShape, HwpPageBorder, HwpColumnsDef, HwpPageNum, HwpSectionDef`). Place the functions just above `read_document`:

```python
def _parse_page_def(sec_el):
    pd = sec_el.find("PageDef")
    if pd is None:
        return None
    return HwpPageDef(
        width=_int(pd.get("width")),
        height=_int(pd.get("height")),
        orientation=pd.get("orientation") or "portrait",
        bookbinding=pd.get("bookbinding") or "left",
        bookbinding_offset=_int(pd.get("bookbinding-offset")),
        left_offset=_int(pd.get("left-offset")),
        right_offset=_int(pd.get("right-offset")),
        top_offset=_int(pd.get("top-offset")),
        bottom_offset=_int(pd.get("bottom-offset")),
        header_offset=_int(pd.get("header-offset")),
        footer_offset=_int(pd.get("footer-offset")),
    )


def _parse_note_shape(el):
    return HwpNoteShape(
        notes_spacing=_int(el.get("notes-spacing")),
        prefix=el.get("prefix") or "",
        suffix=el.get("suffix") or "",
        usersymbol=el.get("usersymbol") or "",
        stroke_type=el.get("stroke-type") or "none",
        line_width=el.get("width") or "0.12mm",
        splitter_length=_int(el.get("splitter-length")),
        splitter_color=el.get("splitter-color") or "#000000",
        splitter_margin_top=_int(el.get("splitter-margin-top")),
        splitter_margin_bottom=_int(el.get("splitter-margin-bottom")),
        starting_number=_int(el.get("starting-number"), 1),
    )


def _parse_page_borders(sec_el):
    out = []
    for el in sec_el.findall("PageBorderFill"):
        out.append(HwpPageBorder(
            borderfill_id=_int(el.get("borderfill-id"), 1),
            relative_to=el.get("relative-to") or "paper",
            fill=el.get("fill") or "paper",
            include_header=_int(el.get("include-header")),
            include_footer=_int(el.get("include-footer")),
            margin_left=_int(el.get("margin-left")),
            margin_right=_int(el.get("margin-right")),
            margin_top=_int(el.get("margin-top")),
            margin_bottom=_int(el.get("margin-bottom")),
        ))
    return out


def _parse_section_def(sec_el):
    first_para = sec_el.find("ColumnSet/Paragraph")  # per-section scope
    columns = None
    page_num = None
    if first_para is not None:
        cd = first_para.find(".//ColumnsDef")
        if cd is not None:
            columns = HwpColumnsDef(
                count=_int(cd.get("count"), 1),
                kind=cd.get("kind") or "normal",
                direction=cd.get("direction") or "l2r",
                same_widths=_int(cd.get("same-widths"), 1),
            )
        pn = first_para.find(".//PageNumberPosition")
        if pn is not None:
            page_num = HwpPageNum(
                position=pn.get("position") or "bottom_center",
                shape=_int(pn.get("shape")),
                dash=pn.get("dash") or "-",
            )
    foots = sec_el.findall("FootnoteShape")
    return HwpSectionDef(
        column_spacing=_int(sec_el.get("columnspacing")),
        default_tab_stops=_int(sec_el.get("defaultTabStops")),
        text_direction=_int(sec_el.get("text-direction")),
        grid_horizontal=_int(sec_el.get("grid-horizontal")),
        grid_vertical=_int(sec_el.get("grid-vertical")),
        squared_manuscript_paper=_int(sec_el.get("squared-manuscript-paper")),
        numbering_shape_id=_int(sec_el.get("numbering-shape-id")),
        starting_pagenum=_int(sec_el.get("starting-pagenum")),
        starting_picturenum=_int(sec_el.get("starting-picturenum")),
        starting_tablenum=_int(sec_el.get("starting-tablenum")),
        starting_equationnum=_int(sec_el.get("starting-equationnum")),
        pagenum_on_split_section=_int(sec_el.get("pagenum-on-split-section")),
        hide_header=_int(sec_el.get("hide-header")),
        hide_footer=_int(sec_el.get("hide-footer")),
        hide_border=_int(sec_el.get("hide-border")),
        hide_pagenumber=_int(sec_el.get("hide-pagenumber")),
        hide_blank_line=_int(sec_el.get("hide-blank-line")),
        show_background_on_first_page_only=_int(
            sec_el.get("show-background-on-first-page-only")),
        page=_parse_page_def(sec_el),
        footnote=_parse_note_shape(foots[0]) if len(foots) >= 1 else None,
        endnote=_parse_note_shape(foots[1]) if len(foots) >= 2 else None,
        page_borders=_parse_page_borders(sec_el),
        columns=columns,
        page_num=page_num,
    )
```

Modify the section-building loop in `read_document` (the `for sec_el in root.findall(".//SectionDef")` block) so the `HwpSection` carries its `sec_def`:

```python
        sections.append(HwpSection(paragraphs=paras,
                                   sec_def=_parse_section_def(sec_el)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_reader_section.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the reader regression subset**

Run: `.venv/bin/python -m pytest tests/test_reader_body.py tests/test_reader_docinfo.py -v`
Expected: PASS (no regressions from the `HwpSection` change).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_section.py
git commit -m "feat: reader parses SectionDef into HwpSectionDef"
```

---

### Task 4: Mapper — `map_section_def`

**Files:**
- Create: `hwp2hwpx/mapper/section.py`
- Modify: `hwp2hwpx/mapper/body.py`
- Test: `tests/test_mapper_section.py`

**Interfaces:**
- Consumes: `HwpSectionDef` (Task 1), OWPML `SecPr` + children (Task 2).
- Produces: `map_section_def(sd) -> SecPr` (or `None`); `map_document` sets `Section.sec_pr` per section.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mapper_section.py
from hwp2hwpx.hwpmodel.model import (
    HwpSectionDef, HwpPageDef, HwpNoteShape, HwpPageBorder, HwpColumnsDef,
    HwpPageNum, HwpSection, HwpDocInfo, HwpDocument,
)
from hwp2hwpx.mapper.section import map_section_def
from hwp2hwpx.mapper.body import map_document


def _full_sd():
    return HwpSectionDef(
        column_spacing=1134, default_tab_stops=8000, text_direction=0,
        numbering_shape_id=0, hide_blank_line=1,
        page=HwpPageDef(width=59528, height=84188, orientation="portrait",
                        bookbinding="left", left_offset=6000, right_offset=5528,
                        top_offset=4536, bottom_offset=4252,
                        header_offset=1964, footer_offset=1436),
        footnote=HwpNoteShape(stroke_type="solid", line_width="0.12mm",
                              splitter_length=-1, notes_spacing=284,
                              splitter_margin_top=852, splitter_margin_bottom=568,
                              suffix=")", starting_number=1),
        endnote=HwpNoteShape(stroke_type="none", line_width="0.12mm",
                             splitter_length=0, starting_number=1, suffix=")"),
        page_borders=[HwpPageBorder(borderfill_id=1, margin_left=1417,
                                    margin_right=1417, margin_top=1417,
                                    margin_bottom=1417) for _ in range(3)],
        columns=HwpColumnsDef(count=1, kind="normal", direction="l2r"),
        page_num=HwpPageNum(position="bottom_center", shape=0, dash="-"),
    )


def test_maps_scalar_and_enum_fields():
    sp = map_section_def(_full_sd())
    assert sp.text_direction == "HORIZONTAL"
    assert sp.space_columns == 1134 and sp.tab_stop == 8000
    assert sp.page_pr.landscape == "WIDELY"
    assert sp.page_pr.width == 59528
    assert sp.page_pr.margin.left == 6000 and sp.page_pr.margin.header == 1964
    assert sp.page_pr.gutter_type == "LEFT_ONLY"
    assert sp.visibility.hide_first_empty_line == 1
    assert sp.col_pr.type == "NEWSPAPER" and sp.col_pr.layout == "LEFT"
    assert sp.page_num.pos == "BOTTOM_CENTER" and sp.page_num.side_char == "-"


def test_maps_footnote_and_endnote_and_note_width_space():
    sp = map_section_def(_full_sd())
    assert sp.foot_note_pr.note_line.type == "SOLID"
    assert sp.foot_note_pr.note_line.width == "0.12 mm"  # space inserted
    assert sp.foot_note_pr.note_line.length == -1
    assert sp.foot_note_pr.note_spacing.between_notes == 284
    assert sp.foot_note_pr.placement.place == "EACH_COLUMN"
    assert sp.end_note_pr.note_line.type == "NONE"
    assert sp.end_note_pr.placement.place == "END_OF_DOCUMENT"


def test_three_page_border_fills_typed_by_index():
    sp = map_section_def(_full_sd())
    assert [b.type for b in sp.page_border_fills] == ["BOTH", "EVEN", "ODD"]
    assert sp.page_border_fills[0].offset.left == 1417
    assert sp.page_border_fills[0].text_border == "PAPER"


def test_absence_paths_emit_nothing():
    sd = HwpSectionDef()  # no page, no notes, no borders, no columns, no page_num
    sp = map_section_def(sd)
    assert sp.page_pr is None
    assert sp.foot_note_pr is None and sp.end_note_pr is None
    assert sp.page_border_fills == []
    assert sp.col_pr is None and sp.page_num is None


def test_columns_count_two():
    sd = HwpSectionDef(columns=HwpColumnsDef(count=2))
    assert map_section_def(sd).col_pr.col_count == 2


def test_none_maps_to_none():
    assert map_section_def(None) is None


def test_map_document_attaches_sec_pr_per_section():
    doc = HwpDocument(
        docinfo=HwpDocInfo(),
        sections=[HwpSection(paragraphs=[], sec_def=HwpSectionDef(column_spacing=11)),
                  HwpSection(paragraphs=[], sec_def=HwpSectionDef(column_spacing=22))],
    )
    out = map_document(doc)
    assert out.sections[0].sec_pr.space_columns == 11
    assert out.sections[1].sec_pr.space_columns == 22
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mapper_section.py -v`
Expected: FAIL with `ModuleNotFoundError: hwp2hwpx.mapper.section`.

- [ ] **Step 3: Create `hwp2hwpx/mapper/section.py`**

```python
"""Map HWP section-definition records to an OWPML SecPr."""
from ..owpml.model import (
    SecPr, Grid, StartNum, Visibility, LineNumberShape, PagePr, Margin,
    NotePr, AutoNumFormat, NoteLine, NoteSpacing, Numbering, Placement,
    PageBorderFill, Offset, ColPr, PageNum,
)

_ORIENTATION = {"portrait": "WIDELY", "landscape": "NARROWLY"}
_BOOKBINDING = {"left": "LEFT_ONLY", "right": "RIGHT_ONLY", "top": "TOP_ONLY"}
_COL_KIND = {"normal": "NEWSPAPER", "balanced": "BALANCED", "parallel": "PARALLEL"}
_COL_DIR = {"l2r": "LEFT", "r2l": "RIGHT"}
_STROKE = {"solid": "SOLID", "none": "NONE", "dash": "DASH", "dot": "DOT",
           "dash-dot": "DASH_DOT"}
_PGNUM_POS = {"bottom_center": "BOTTOM_CENTER", "bottom_left": "BOTTOM_LEFT",
              "bottom_right": "BOTTOM_RIGHT", "top_center": "TOP_CENTER",
              "top_left": "TOP_LEFT", "top_right": "TOP_RIGHT",
              "outside_top": "OUTSIDE_TOP", "outside_bottom": "OUTSIDE_BOTTOM",
              "inside_top": "INSIDE_TOP", "inside_bottom": "INSIDE_BOTTOM",
              "none": "NONE"}
_BORDER_TYPES = ["BOTH", "EVEN", "ODD"]  # by index; documented template assumption


def _note_line_width(w):
    # HWP stores "0.12mm"; Hancom emits "0.12 mm".
    if w.endswith("mm") and not w.endswith(" mm"):
        return w[:-2] + " mm"
    return w


def _map_note_pr(shape, place):
    return NotePr(
        auto_num_format=AutoNumFormat(  # type/supscript are Hancom constants
            user_char=shape.usersymbol, prefix_char=shape.prefix,
            suffix_char=shape.suffix),
        note_line=NoteLine(
            length=shape.splitter_length,
            type=_STROKE.get(shape.stroke_type, "SOLID"),
            width=_note_line_width(shape.line_width),
            color=shape.splitter_color),
        note_spacing=NoteSpacing(
            between_notes=shape.notes_spacing,
            below_line=shape.splitter_margin_bottom,
            above_line=shape.splitter_margin_top),
        numbering=Numbering(new_num=shape.starting_number),  # type is constant
        placement=Placement(place=place),
    )


def map_section_def(sd):
    if sd is None:
        return None

    page_pr = None
    if sd.page is not None:
        p = sd.page
        page_pr = PagePr(
            landscape=_ORIENTATION.get(p.orientation, "WIDELY"),
            width=p.width, height=p.height,
            gutter_type=_BOOKBINDING.get(p.bookbinding, "LEFT_ONLY"),
            margin=Margin(header=p.header_offset, footer=p.footer_offset,
                          gutter=p.bookbinding_offset, left=p.left_offset,
                          right=p.right_offset, top=p.top_offset,
                          bottom=p.bottom_offset))

    page_border_fills = [
        PageBorderFill(
            type=_BORDER_TYPES[i] if i < len(_BORDER_TYPES) else "BOTH",
            border_fill_id=b.borderfill_id,
            text_border="PAPER" if b.relative_to == "paper" else "PAGE",
            header_inside=b.include_header, footer_inside=b.include_footer,
            fill_area="PAPER" if b.fill == "paper" else "PAGE",
            offset=Offset(left=b.margin_left, right=b.margin_right,
                          top=b.margin_top, bottom=b.margin_bottom))
        for i, b in enumerate(sd.page_borders)
    ]

    col_pr = None
    if sd.columns is not None:
        c = sd.columns
        col_pr = ColPr(type=_COL_KIND.get(c.kind, "NEWSPAPER"),
                       layout=_COL_DIR.get(c.direction, "LEFT"),
                       col_count=c.count, same_sz=c.same_widths)

    page_num = None
    if sd.page_num is not None:
        pn = sd.page_num
        page_num = PageNum(pos=_PGNUM_POS.get(pn.position, "BOTTOM_CENTER"),
                           side_char=pn.dash)  # format_type is constant DIGIT

    return SecPr(
        text_direction="HORIZONTAL" if sd.text_direction == 0 else "VERTICAL",
        space_columns=sd.column_spacing,
        tab_stop=sd.default_tab_stops,
        outline_shape_id=sd.numbering_shape_id,
        grid=Grid(line_grid=sd.grid_vertical, char_grid=sd.grid_horizontal,
                  wonggoji_format=sd.squared_manuscript_paper),
        start_num=StartNum(page=sd.starting_pagenum, pic=sd.starting_picturenum,
                           tbl=sd.starting_tablenum,
                           equation=sd.starting_equationnum),
        visibility=Visibility(
            hide_first_header=sd.hide_header,
            hide_first_footer=sd.hide_footer,
            hide_first_master_page=sd.show_background_on_first_page_only,
            border="SHOW_ALL" if sd.hide_border == 0 else "HIDE",
            hide_first_page_num=sd.hide_pagenumber,
            hide_first_empty_line=sd.hide_blank_line),
        line_number_shape=LineNumberShape(),
        page_pr=page_pr,
        foot_note_pr=_map_note_pr(sd.footnote, "EACH_COLUMN") if sd.footnote else None,
        end_note_pr=_map_note_pr(sd.endnote, "END_OF_DOCUMENT") if sd.endnote else None,
        page_border_fills=page_border_fills,
        col_pr=col_pr,
        page_num=page_num,
    )
```

- [ ] **Step 4: Wire into `map_document`**

In `hwp2hwpx/mapper/body.py`: add `from .section import map_section_def` to the imports, and set `sec_pr` when building each `Section` in the `for hsec in hwp_doc.sections` loop:

```python
        sections.append(Section(paras=paras,
                                sec_pr=map_section_def(getattr(hsec, "sec_def", None))))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_mapper_section.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Run mapper regression subset**

Run: `.venv/bin/python -m pytest tests/test_mapper_body.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/mapper/section.py hwp2hwpx/mapper/body.py tests/test_mapper_section.py
git commit -m "feat: map HwpSectionDef to OWPML SecPr"
```

---

### Task 5: Writer emits `secPr` into paragraph 0

**Files:**
- Modify: `hwp2hwpx/owpml/section_writer.py`
- Test: `tests/test_section_writer_secpr.py`

**Interfaces:**
- Consumes: OWPML `SecPr` + children (Task 2), `Section.sec_pr`.
- Produces: `_write_sec_pr(run_el, sp)`; `_write_paragraph(..., sec_pr=None)` gains an optional leading-run injection; `section_xml` passes `section.sec_pr` to paragraph 0 only.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_section_writer_secpr.py
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import (
    Section, Para, Run, SecPr, Grid, StartNum, Visibility, LineNumberShape,
    PagePr, Margin, NotePr, AutoNumFormat, NoteLine, NoteSpacing, Numbering,
    Placement, PageBorderFill, Offset, ColPr, PageNum,
)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _q(tag):
    return "{%s}%s" % (HP, tag)


def _full_secpr():
    return SecPr(
        space_columns=1134, tab_stop=8000,
        grid=Grid(), start_num=StartNum(), visibility=Visibility(),
        line_number_shape=LineNumberShape(),
        page_pr=PagePr(width=59528, height=84188, margin=Margin(left=7088)),
        foot_note_pr=NotePr(auto_num_format=AutoNumFormat(), note_line=NoteLine(),
                            note_spacing=NoteSpacing(), numbering=Numbering(),
                            placement=Placement(place="EACH_COLUMN")),
        end_note_pr=NotePr(auto_num_format=AutoNumFormat(), note_line=NoteLine(),
                           note_spacing=NoteSpacing(), numbering=Numbering(),
                           placement=Placement(place="END_OF_DOCUMENT")),
        page_border_fills=[PageBorderFill(type=t, offset=Offset(left=1417))
                           for t in ("BOTH", "EVEN", "ODD")],
        col_pr=ColPr(), page_num=PageNum(),
    )


def _root(section):
    return etree.fromstring(section_xml(section).split(b"?>", 1)[1])


def test_secpr_is_first_child_of_first_paragraphs_first_run():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=5)])],
                  sec_pr=_full_secpr())
    root = _root(sec)
    first_p = root.find(_q("p"))
    first_run = first_p.find(_q("run"))
    assert first_run is not None
    assert etree.QName(first_run[0]).localname == "secPr"


def test_secpr_subtree_shape():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])],
                  sec_pr=_full_secpr())
    sp = _root(sec).find(".//" + _q("secPr"))
    kids = [etree.QName(c).localname for c in sp]
    assert kids == ["grid", "startNum", "visibility", "lineNumberShape",
                    "pagePr", "footNotePr", "endNotePr",
                    "pageBorderFill", "pageBorderFill", "pageBorderFill"]
    assert sp.get("spaceColumns") == "1134"
    assert sp.get("tabStopVal") == "4000"
    pp = sp.find(_q("pagePr"))
    assert pp.find(_q("margin")).get("left") == "7088"
    fn = sp.find(_q("footNotePr"))
    assert [etree.QName(c).localname for c in fn] == [
        "autoNumFormat", "noteLine", "noteSpacing", "numbering", "placement"]
    pbf = sp.findall(_q("pageBorderFill"))
    assert [b.get("type") for b in pbf] == ["BOTH", "EVEN", "ODD"]
    assert pbf[0].find(_q("offset")).get("left") == "1417"


def test_colpr_and_pagenum_are_ctrl_wrapped_in_first_paragraph():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])],
                  sec_pr=_full_secpr())
    first_p = _root(sec).find(_q("p"))
    ctrls = first_p.findall(".//" + _q("ctrl"))
    wrapped = [etree.QName(c[0]).localname for c in ctrls]
    assert "colPr" in wrapped and "pageNum" in wrapped


def test_no_secpr_when_section_has_none():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])])
    assert _root(sec).find(".//" + _q("secPr")) is None


def test_absent_colpr_pagenum_not_emitted():
    sp = _full_secpr()
    sp.col_pr = None
    sp.page_num = None
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])],
                  sec_pr=sp)
    first_p = _root(sec).find(_q("p"))
    assert first_p.find(".//" + _q("colPr")) is None
    assert first_p.find(".//" + _q("pageNum")) is None


def test_only_first_paragraph_gets_secpr():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)]),
                         Para(id=1, para_pr_id=0, runs=[Run(char_pr_id=0)])],
                  sec_pr=_full_secpr())
    ps = _root(sec).findall(_q("p"))
    assert ps[1].find(".//" + _q("secPr")) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_section_writer_secpr.py -v`
Expected: FAIL (`_write_paragraph` has no `sec_pr` param / no secPr emitted).

- [ ] **Step 3: Add the writer functions**

In `hwp2hwpx/owpml/section_writer.py`, add `_write_sec_pr` and two small ctrl helpers (place above `_write_paragraph`):

```python
def _write_sec_pr(run_el, sp):
    s = etree.SubElement(run_el, _hp("secPr"))
    for k, v in (("id", sp.id), ("textDirection", sp.text_direction),
                 ("spaceColumns", str(sp.space_columns)),
                 ("tabStop", str(sp.tab_stop)),
                 ("tabStopVal", str(sp.tab_stop_val)),
                 ("tabStopUnit", sp.tab_stop_unit),
                 ("outlineShapeIDRef", str(sp.outline_shape_id)),
                 ("memoShapeIDRef", str(sp.memo_shape_id)),
                 ("textVerticalWidthHead", str(sp.text_vertical_width_head)),
                 ("masterPageCnt", str(sp.master_page_cnt))):
        s.set(k, v)

    g = etree.SubElement(s, _hp("grid"))
    g.set("lineGrid", str(sp.grid.line_grid))
    g.set("charGrid", str(sp.grid.char_grid))
    g.set("wonggojiFormat", str(sp.grid.wonggoji_format))

    sn = etree.SubElement(s, _hp("startNum"))
    sn.set("pageStartsOn", sp.start_num.page_starts_on)
    for k, val in (("page", sp.start_num.page), ("pic", sp.start_num.pic),
                   ("tbl", sp.start_num.tbl), ("equation", sp.start_num.equation)):
        sn.set(k, str(val))

    v = sp.visibility
    vis = etree.SubElement(s, _hp("visibility"))
    vis.set("hideFirstHeader", str(v.hide_first_header))
    vis.set("hideFirstFooter", str(v.hide_first_footer))
    vis.set("hideFirstMasterPage", str(v.hide_first_master_page))
    vis.set("border", v.border)
    vis.set("fill", v.fill)
    vis.set("hideFirstPageNum", str(v.hide_first_page_num))
    vis.set("hideFirstEmptyLine", str(v.hide_first_empty_line))
    vis.set("showLineNumber", str(v.show_line_number))

    ln = sp.line_number_shape
    lns = etree.SubElement(s, _hp("lineNumberShape"))
    lns.set("restartType", str(ln.restart_type))
    lns.set("countBy", str(ln.count_by))
    lns.set("distance", str(ln.distance))
    lns.set("startNumber", str(ln.start_number))

    if sp.page_pr is not None:
        pp = etree.SubElement(s, _hp("pagePr"))
        pp.set("landscape", sp.page_pr.landscape)
        pp.set("width", str(sp.page_pr.width))
        pp.set("height", str(sp.page_pr.height))
        pp.set("gutterType", sp.page_pr.gutter_type)
        mg = sp.page_pr.margin
        m = etree.SubElement(pp, _hp("margin"))
        for k, val in (("header", mg.header), ("footer", mg.footer),
                       ("gutter", mg.gutter), ("left", mg.left),
                       ("right", mg.right), ("top", mg.top), ("bottom", mg.bottom)):
            m.set(k, str(val))

    for tag, note in (("footNotePr", sp.foot_note_pr),
                      ("endNotePr", sp.end_note_pr)):
        if note is None:
            continue
        n = etree.SubElement(s, _hp(tag))
        anf = etree.SubElement(n, _hp("autoNumFormat"))
        anf.set("type", note.auto_num_format.type)
        anf.set("userChar", note.auto_num_format.user_char)
        anf.set("prefixChar", note.auto_num_format.prefix_char)
        anf.set("suffixChar", note.auto_num_format.suffix_char)
        anf.set("supscript", str(note.auto_num_format.supscript))
        nl = etree.SubElement(n, _hp("noteLine"))
        nl.set("length", str(note.note_line.length))
        nl.set("type", note.note_line.type)
        nl.set("width", note.note_line.width)
        nl.set("color", note.note_line.color)
        ns = etree.SubElement(n, _hp("noteSpacing"))
        ns.set("betweenNotes", str(note.note_spacing.between_notes))
        ns.set("belowLine", str(note.note_spacing.below_line))
        ns.set("aboveLine", str(note.note_spacing.above_line))
        nm = etree.SubElement(n, _hp("numbering"))
        nm.set("type", note.numbering.type)
        nm.set("newNum", str(note.numbering.new_num))
        pl = etree.SubElement(n, _hp("placement"))
        pl.set("place", note.placement.place)
        pl.set("beneathText", str(note.placement.beneath_text))

    for pbf in sp.page_border_fills:
        b = etree.SubElement(s, _hp("pageBorderFill"))
        b.set("type", pbf.type)
        b.set("borderFillIDRef", str(pbf.border_fill_id))
        b.set("textBorder", pbf.text_border)
        b.set("headerInside", str(pbf.header_inside))
        b.set("footerInside", str(pbf.footer_inside))
        b.set("fillArea", pbf.fill_area)
        o = etree.SubElement(b, _hp("offset"))
        o.set("left", str(pbf.offset.left))
        o.set("right", str(pbf.offset.right))
        o.set("top", str(pbf.offset.top))
        o.set("bottom", str(pbf.offset.bottom))


def _write_ctrl_colpr(run_el, col_pr):
    ctrl = etree.SubElement(run_el, _hp("ctrl"))
    c = etree.SubElement(ctrl, _hp("colPr"))
    c.set("id", col_pr.id)
    c.set("type", col_pr.type)
    c.set("layout", col_pr.layout)
    c.set("colCount", str(col_pr.col_count))
    c.set("sameSz", str(col_pr.same_sz))
    c.set("sameGap", str(col_pr.same_gap))


def _write_ctrl_pagenum(run_el, page_num):
    ctrl = etree.SubElement(run_el, _hp("ctrl"))
    pn = etree.SubElement(ctrl, _hp("pageNum"))
    pn.set("pos", page_num.pos)
    pn.set("formatType", page_num.format_type)
    pn.set("sideChar", page_num.side_char)
```

- [ ] **Step 4: Inject the leading run and thread `sec_pr` through**

Modify `_write_paragraph` to accept `sec_pr=None` and emit the leading run after the `<hp:p>` attributes are set, before the normal `for run in para.runs` loop:

```python
def _write_paragraph(parent_el, para, state, sec_pr=None):
    p = etree.SubElement(parent_el, _hp("p"))
    p.set("id", str(state["para_id"]))
    state["para_id"] += 1
    p.set("paraPrIDRef", str(para.para_pr_id))
    p.set("styleIDRef", str(para.style_id))
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")
    if sec_pr is not None:
        cref = para.runs[0].char_pr_id if para.runs else 0
        lead = etree.SubElement(p, _hp("run"))
        lead.set("charPrIDRef", str(cref))
        _write_sec_pr(lead, sec_pr)
        if sec_pr.col_pr is not None:
            _write_ctrl_colpr(lead, sec_pr.col_pr)
        if sec_pr.page_num is not None:
            _write_ctrl_pagenum(lead, sec_pr.page_num)
    for run in para.runs:
        _write_run(p, run, state)
    if para.line_segs:
        # ... unchanged linesegarray block ...
```

Modify `section_xml` to pass `sec_pr` to paragraph 0 only (cell paragraphs, which call `_write_paragraph` from `_write_cell`, keep the default `None`):

```python
def section_xml(section):
    root = etree.Element(_hs("sec"), nsmap=_NSMAP)
    state = {"tbl_id": 0, "para_id": 0}
    for idx, para in enumerate(section.paras):
        _write_paragraph(root, para, state,
                         sec_pr=(section.sec_pr if idx == 0 else None))
    return XML_DECL + etree.tostring(root, encoding="UTF-8")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_section_writer_secpr.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Run writer regression subset**

Run: `.venv/bin/python -m pytest tests/test_section_writer.py tests/test_section_writer_inline.py tests/test_section_writer_lineseg.py tests/test_section_writer_tables.py -v`
Expected: PASS (existing paragraph/cell writing unaffected; cell paras get `sec_pr=None`).

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py tests/test_section_writer_secpr.py
git commit -m "feat: writer emits secPr + colPr/pageNum into paragraph 0"
```

---

### Task 6: End-to-end fidelity — exact subtree equality on both samples

**Files:**
- Test: `tests/test_convert_secpr.py`

**Interfaces:**
- Consumes: the whole pipeline via `hwp2hwpx.convert.convert`.

- [ ] **Step 1: Write the failing/verifying test**

```python
# tests/test_convert_secpr.py
import zipfile
import pytest
from lxml import etree
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

PAIRS = [
    ("samples/3.*.hwp", "samples/3.*.hwpx"),
    ("samples/4.*.hwp", "samples/4.*.hwpx"),
]


def _canon(el):
    """Structural signature: local tag, attribute dict, stripped text, ordered
    children — recursively. Namespace prefixes are stripped so only structure
    and values are compared."""
    tag = etree.QName(el).localname
    return (tag, dict(el.attrib), (el.text or "").strip(),
            [_canon(c) for c in el])


def _secpr_from_bytes(xml_bytes):
    root = etree.fromstring(xml_bytes)
    return root.find(".//{%s}secPr" % HP)


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_secpr_subtree_structurally_identical_to_hancom(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    with zipfile.ZipFile(str(out)) as z:
        ours = _secpr_from_bytes(z.read("Contents/section0.xml"))
    with zipfile.ZipFile(ref) as z:
        theirs = _secpr_from_bytes(z.read("Contents/section0.xml"))
    assert ours is not None and theirs is not None
    assert _canon(ours) == _canon(theirs)


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_secpr_cluster_tags_leave_miss_list(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(ref)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    for tag in ("secPr", "grid", "startNum", "visibility", "lineNumberShape",
                "pagePr", "margin", "footNotePr", "endNotePr", "colPr",
                "pageNum", "pageBorderFill"):
        assert tag not in missing, "%s still missing on %s" % (tag, hwp)


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_section0_match_improved(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(ref)["Contents/section0.xml"]
    assert score_part(ours, theirs)["match"] > 0.97
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_convert_secpr.py -v`
Expected: PASS (6 parametrized cases). If `test_secpr_subtree_structurally_identical_to_hancom` fails, the diff pinpoints the exact attribute/child mismatch — fix the mapper (Task 4) mapping for that field and re-run; the subtree test is the authoritative correctness definition.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all tests, no regressions). If `tests/test_convert_inline.py` run/`<hp:t>` count assertions are affected by the extra leading run, confirm they still hold (`runs < 1000`, `ts < 800`); they should, as only one run is added per section.

- [ ] **Step 4: Commit**

```bash
git add tests/test_convert_secpr.py
git commit -m "test: end-to-end secPr subtree equality on both samples"
```

---

## Self-Review

**Spec coverage:** Each spec element is implemented — `secPr` attrs + `grid`/`startNum`/`visibility`/`lineNumberShape` (Task 4/5), `pagePr`/`margin` (Task 4/5), `footNotePr`/`endNotePr` sub-tree (Task 4/5), 3× `pageBorderFill`/`offset` (Task 4/5), `ctrl>colPr` and `ctrl>pageNum` (Task 5). Reader source parsing (Task 3), per-section attachment + multi-section (Task 4 `test_map_document_attaches_sec_pr_per_section`). Primary gate = exact subtree equality (Task 6). Absence/breadth paths (Task 4 `test_absence_paths_emit_nothing`, `test_columns_count_two`; Task 5 `test_no_secpr_when_section_has_none`, `test_absent_colpr_pagenum_not_emitted`).

**Placeholder scan:** No TBD/TODO; all code blocks complete; all commands have expected output.

**Type consistency:** OWPML field names defined in Task 2 (`space_columns`, `tab_stop`, `page_border_fills`, `foot_note_pr`, `end_note_pr`, `line_number_shape`, `col_pr`, `page_num`, `hide_first_empty_line`, etc.) are used identically by the mapper (Task 4) and writer (Task 5). HWP field names (`line_width`, `stroke_type`, `splitter_length`, `page_borders`, `column_spacing`) defined in Task 1 are used identically by the reader (Task 3) and mapper (Task 4). `HwpNoteShape.line_width` (not `splitter_width`) holds HWP `width`; `stroke_type` holds HWP `stroke-type`.
