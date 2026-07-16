"""HWP-side data model — the Reader's output / Mapper's input contract."""
from dataclasses import dataclass, field


@dataclass
class HwpFont:
    index: int
    name: str


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


@dataclass
class HwpDocInfo:
    fonts: list = field(default_factory=list)
    char_shapes: list = field(default_factory=list)
    para_shapes: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)


@dataclass
class HwpRun:
    char_shape_id: int
    text: str = ""
    table: "HwpTable" = None


@dataclass
class HwpParagraph:
    para_shape_id: int
    style_id: int = 0
    runs: list = field(default_factory=list)


@dataclass
class HwpSection:
    paragraphs: list = field(default_factory=list)


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
