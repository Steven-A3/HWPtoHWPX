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


@dataclass
class ParaPr:
    id: int
    align: str = "LEFT"


@dataclass
class Text:
    content: str


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


@dataclass
class Header:
    fonts_by_lang: dict = field(default_factory=dict)
    char_prs: list = field(default_factory=list)
    para_prs: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)


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
