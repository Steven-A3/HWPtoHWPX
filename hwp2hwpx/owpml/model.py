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
