"""HWP-side data model — the Reader's output / Mapper's input contract."""
from dataclasses import dataclass, field


@dataclass
class HwpPanose:
    family_type: int = 0
    weight: int = 0
    proportion: int = 0
    contrast: int = 0
    stroke_variation: int = 0
    arm_style: int = 0
    letterform: int = 0
    midline: int = 0
    x_height: int = 0


@dataclass
class HwpFont:
    index: int
    name: str
    panose: "HwpPanose" = None


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


@dataclass
class HwpParaShape:
    index: int
    align: str = "LEFT"
    indent: int = 0
    margin_left: int = 0
    margin_right: int = 0
    margin_top: int = 0
    margin_bottom: int = 0
    line_spacing: int = 100
    line_spacing_type: str = "ratio"
    border_fill_id: int = 1
    level: int = 0
    tab_def_id: int = 0


@dataclass
class HwpStyle:
    index: int
    kind: str = "paragraph"
    local_name: str = ""
    eng_name: str = ""
    para_shape_id: int = 0
    char_shape_id: int = 0
    next_style_id: int = 0
    lang_id: int = 1042


@dataclass
class HwpTab:
    pos: int = 0
    kind: str = "left"
    fill_type: int = 0


@dataclass
class HwpTabDef:
    index: int
    auto_tab_left: int = 0
    auto_tab_right: int = 0
    tabs: list = field(default_factory=list)


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


@dataclass
class HwpDocInfo:
    fonts: list = field(default_factory=list)
    char_shapes: list = field(default_factory=list)
    para_shapes: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    tab_defs: list = field(default_factory=list)


@dataclass
class HwpControl:
    kind: str = "fwSpace"


@dataclass
class HwpRun:
    char_shape_id: int
    contents: list = field(default_factory=list)
    table: "HwpTable" = None

    @property
    def text(self):
        return "".join(c for c in self.contents if isinstance(c, str))


@dataclass
class HwpLineSeg:
    text_pos: int = 0
    vert_pos: int = 0
    vert_size: int = 0
    text_height: int = 0
    baseline: int = 0
    spacing: int = 0
    horz_pos: int = 0
    horz_size: int = 0
    flags: int = 0


@dataclass
class HwpParagraph:
    para_shape_id: int
    style_id: int = 0
    runs: list = field(default_factory=list)
    line_segs: list = field(default_factory=list)


@dataclass
class HwpSection:
    paragraphs: list = field(default_factory=list)
    sec_def: "HwpSectionDef" = None


@dataclass
class HwpDocument:
    docinfo: HwpDocInfo
    sections: list = field(default_factory=list)


@dataclass
class HwpBorder:
    kind: str
    stroke_type: str = "none"
    width: str = "0.1mm"
    color: str = "#000000"


@dataclass
class HwpBorderFill:
    index: int
    borders: list = field(default_factory=list)
    fill_color: str = None


@dataclass
class HwpTableCell:
    col: int = 0
    row: int = 0
    col_span: int = 1
    row_span: int = 1
    width: int = 0
    height: int = 0
    border_fill_id: int = 0
    valign: str = "middle"
    paragraphs: list = field(default_factory=list)


@dataclass
class HwpTableRow:
    cells: list = field(default_factory=list)


@dataclass
class HwpTable:
    rows: int = 0
    cols: int = 0
    cell_spacing: int = 0
    border_fill_id: int = 0
    width: int = 0
    height: int = 0
    table_rows: list = field(default_factory=list)
