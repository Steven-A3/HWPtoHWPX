"""OWPML (HWPX) side data model — the Writer's input contract."""
from dataclasses import dataclass, field


@dataclass
class Font:
    id: int
    face: str
    type: str = "TTF"
    is_embedded: bool = False


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
