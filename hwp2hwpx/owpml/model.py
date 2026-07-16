"""OWPML (HWPX) side data model — the Writer's input contract."""
from dataclasses import dataclass, field


@dataclass
class TypeInfo:
    family_type: str = "FCAT_GOTHIC"
    weight: int = 0
    proportion: int = 0
    contrast: int = 0
    stroke_variation: int = 0
    arm_style: int = 0
    letterform: int = 0
    midline: int = 0
    x_height: int = 0


@dataclass
class Font:
    id: int
    face: str
    type: str = "TTF"
    is_embedded: bool = False
    type_info: "TypeInfo" = None


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


@dataclass
class ParaPr:
    id: int
    align: str = "LEFT"
    heading_type: str = "NONE"
    heading_level: int = 0
    intent: int = 0
    margin_left: int = 0
    margin_right: int = 0
    margin_prev: int = 0
    margin_next: int = 0
    line_spacing: int = 100
    line_spacing_type: str = "PERCENT"
    border_fill_id: int = 1
    tab_pr_id: int = 0


@dataclass
class Style:
    id: int
    type: str = "PARA"
    name: str = ""
    eng_name: str = ""
    para_pr_id: int = 0
    char_pr_id: int = 0
    next_style_id: int = 0
    lang_id: int = 1042
    lock_form: str = "0"


@dataclass
class TabItem:
    pos: int = 0
    type: str = "LEFT"
    leader: str = "NONE"


@dataclass
class TabDef:
    id: int
    auto_tab_left: int = 0
    auto_tab_right: int = 0
    tabs: list = field(default_factory=list)


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


@dataclass
class Text:
    content: str


@dataclass
class Control:
    kind: str = "fwSpace"


@dataclass
class LineSeg:
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
class Run:
    char_pr_id: int
    texts: list = field(default_factory=list)
    table: "Table" = None


@dataclass
class Para:
    id: int
    para_pr_id: int
    style_id: int = 0
    runs: list = field(default_factory=list)
    line_segs: list = field(default_factory=list)


@dataclass
class Header:
    fonts_by_lang: dict = field(default_factory=dict)
    char_prs: list = field(default_factory=list)
    para_prs: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    tab_defs: list = field(default_factory=list)


@dataclass
class Section:
    paras: list = field(default_factory=list)
    sec_pr: "SecPr" = None


@dataclass
class Metadata:
    title: str = ""
    language: str = "ko"


@dataclass
class OwpmlDocument:
    header: Header
    sections: list
    metadata: Metadata


@dataclass
class Border:
    kind: str
    type: str = "NONE"
    width: str = "0.1 mm"
    color: str = "#000000"


@dataclass
class BorderFill:
    id: int
    borders: list = field(default_factory=list)
    fill_color: str = None


@dataclass
class Tc:
    col_addr: int = 0
    row_addr: int = 0
    col_span: int = 1
    row_span: int = 1
    width: int = 0
    height: int = 0
    border_fill_id: int = 0
    valign: str = "CENTER"
    paras: list = field(default_factory=list)


@dataclass
class TableRow:
    cells: list = field(default_factory=list)


@dataclass
class Table:
    id: int = 0
    row_cnt: int = 0
    col_cnt: int = 0
    cell_spacing: int = 0
    border_fill_id: int = 0
    width: int = 0
    height: int = 0
    rows: list = field(default_factory=list)
