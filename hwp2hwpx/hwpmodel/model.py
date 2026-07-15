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


@dataclass
class HwpParaShape:
    index: int
    align: str = "LEFT"


@dataclass
class HwpDocInfo:
    fonts: list = field(default_factory=list)
    char_shapes: list = field(default_factory=list)
    para_shapes: list = field(default_factory=list)


@dataclass
class HwpRun:
    char_shape_id: int
    text: str


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
