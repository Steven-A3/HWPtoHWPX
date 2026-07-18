"""OWPML (HWPX) side data model — the Writer's input contract."""
from dataclasses import dataclass, field
from typing import Optional


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
    subscript: bool = False
    superscript: bool = False


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
class Bullet:
    id: int = 1
    char: str = "-"
    use_image: int = 0
    align: str = "LEFT"
    auto_indent: int = 0
    width_adjust: int = 0
    text_offset: int = 0
    char_pr_id: int = 4294967295


@dataclass
class NumHead:
    level: int = 1
    align: str = "LEFT"
    use_inst_width: int = 0
    auto_indent: int = 0
    width_adjust: int = 0
    text_offset: int = 0
    num_format: str = "DIGIT"
    char_pr_id: int = 0
    checkable: int = 0
    text: str = ""


@dataclass
class ParaNumbering:
    id: int = 1
    start: int = 0
    heads: list = field(default_factory=list)


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
class PageBorderOffset:
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
    offset: "PageBorderOffset" = None


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
    first_char_shape: int = None


@dataclass
class Text:
    content: str


@dataclass
class Control:
    kind: str = "fwSpace"


@dataclass
class PageHiding:
    hide_header: int = 0
    hide_footer: int = 0
    hide_master_page: int = 0
    hide_border: int = 0
    hide_fill: int = 0
    hide_page_num: int = 0


@dataclass
class Bookmark:
    name: str = ""


@dataclass
class NewNum:
    num: int = 1
    num_type: str = "PAGE"


@dataclass
class MarkpenBegin:
    color: str = "#FFFFFF"


@dataclass
class MarkpenEnd:
    pass


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
    # `texts` is a single ordered stream interleaving text spans (Text),
    # inline controls / markpen markers, and objects (Table / drawing shapes).
    # A run may hold multiple objects. An empty Text("") is an empty <hp:t/>.
    char_pr_id: int
    texts: list = field(default_factory=list)
    ctrls: list = field(default_factory=list)
    ctrls_after: list = field(default_factory=list)

    @property
    def table(self):
        return next((t for t in self.texts if isinstance(t, Table)), None)

    @property
    def drawing(self):
        return next((t for t in self.texts
                     if isinstance(t, (Pic, Rect, Line, Container))), None)


@dataclass
class Para:
    id: int
    para_pr_id: int
    style_id: int = 0
    runs: list = field(default_factory=list)
    line_segs: list = field(default_factory=list)


@dataclass
class BeginNum:
    page: int = 1
    footnote: int = 1
    endnote: int = 1
    pic: int = 1
    tbl: int = 1
    equation: int = 1


@dataclass
class CompatDocument:
    target_program: str = "HWP201X"


@dataclass
class Header:
    fonts_by_lang: dict = field(default_factory=dict)
    char_prs: list = field(default_factory=list)
    para_prs: list = field(default_factory=list)
    border_fills: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    tab_defs: list = field(default_factory=list)
    bullets: list = field(default_factory=list)
    numberings: list = field(default_factory=list)
    begin_num: "BeginNum" = None
    compat: "CompatDocument" = None


@dataclass
class Section:
    paras: list = field(default_factory=list)
    sec_pr: "SecPr" = None


@dataclass
class Metadata:
    title: str = ""
    language: str = "ko"
    creator: str = ""
    subject: str = ""
    description: str = ""
    last_saved_by: str = ""
    created_date: str = ""
    modified_date: str = ""
    date: str = ""
    keyword: str = ""


@dataclass
class OwpmlDocument:
    header: Header
    sections: list
    metadata: Metadata
    bin_items: list = field(default_factory=list)
    prv_image: Optional[bytes] = None


@dataclass
class Border:
    kind: str
    type: str = "NONE"
    width: str = "0.1 mm"
    color: str = "#000000"


@dataclass
class Gradation:
    type: str = "LINEAR"
    angle: int = 0
    center_x: int = 0
    center_y: int = 0
    step: int = 50
    step_center: int = 50
    alpha: int = 0
    colors: list = field(default_factory=list)


@dataclass
class BorderFill:
    id: int
    borders: list = field(default_factory=list)
    fill_color: str = None
    gradation: "Gradation" = None


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


@dataclass
class Offset:
    x: int = 0
    y: int = 0


@dataclass
class OrgSz:
    width: int = 0
    height: int = 0


@dataclass
class CurSz:
    width: int = 0
    height: int = 0


@dataclass
class Flip:
    horizontal: int = 0
    vertical: int = 0


@dataclass
class RotationInfo:
    angle: int = 0
    center_x: int = 0
    center_y: int = 0
    rotate_image: int = 0


@dataclass
class Matrix:
    e1: str = "1"
    e2: str = "0"
    e3: str = "0"
    e4: str = "0"
    e5: str = "1"
    e6: str = "0"


@dataclass
class RenderingInfo:
    trans: "Matrix" = None
    sca: "Matrix" = None
    rot: "Matrix" = None


@dataclass
class LineShape:
    color: str = "#000000"
    width: int = 0
    style: str = "SOLID"
    end_cap: str = "FLAT"
    head_style: str = "NORMAL"
    tail_style: str = "NORMAL"
    head_fill: int = 1
    tail_fill: int = 1
    head_sz: str = "SMALL_SMALL"
    tail_sz: str = "SMALL_SMALL"
    outline_style: str = "NORMAL"
    alpha: int = 0


@dataclass
class WinBrush:
    face_color: str = "#FFFFFF"
    hatch_color: str = "#000000"
    alpha: int = 0


@dataclass
class Shadow:
    type: str = "NONE"
    color: str = "#000000"
    offset_x: int = 0
    offset_y: int = 0
    alpha: int = 0


@dataclass
class Pt:
    x: int = 0
    y: int = 0


@dataclass
class ShapeSz:
    width: int = 0
    width_rel_to: str = "ABSOLUTE"
    height: int = 0
    height_rel_to: str = "ABSOLUTE"
    protect: int = 0


@dataclass
class ShapePos:
    treat_as_char: int = 0
    affect_lspacing: int = 0
    flow_with_text: int = 1
    allow_overlap: int = 0
    hold_anchor_and_so: int = 0
    vert_rel_to: str = "PAPER"
    horz_rel_to: str = "PAPER"
    vert_align: str = "TOP"
    horz_align: str = "LEFT"
    vert_offset: int = 0
    horz_offset: int = 0


@dataclass
class ShapeOutMargin:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class Line:
    id: int = 0
    z_order: int = 0
    text_wrap: str = "TOP_AND_BOTTOM"
    text_flow: str = "BOTH_SIDES"
    instid: int = 0
    offset: "Offset" = None
    org_sz: "OrgSz" = None
    cur_sz: "CurSz" = None
    flip: "Flip" = None
    rotation_info: "RotationInfo" = None
    rendering_info: "RenderingInfo" = None
    line_shape: "LineShape" = None
    win_brush: "WinBrush" = None
    shadow: "Shadow" = None
    start_pt: "Pt" = None
    end_pt: "Pt" = None
    sz: "ShapeSz" = None
    pos: "ShapePos" = None
    out_margin: "ShapeOutMargin" = None


@dataclass
class Img:
    bin_item_id: str = "image0"
    bright: int = 0
    contrast: int = 0
    effect: str = "REAL_PIC"
    alpha: int = 0


@dataclass
class ImgRect:
    pt0: "Pt" = None
    pt1: "Pt" = None
    pt2: "Pt" = None
    pt3: "Pt" = None


@dataclass
class ImgClip:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class InMargin:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class ImgDim:
    dim_width: int = 0
    dim_height: int = 0


@dataclass
class ShapeComment:
    text: str = ""


@dataclass
class Pic:
    id: int = 0
    z_order: int = 0
    text_wrap: str = "TOP_AND_BOTTOM"
    text_flow: str = "BOTH_SIDES"
    group_level: int = 0
    instid: int = 0
    reverse: int = 0
    offset: "Offset" = None
    org_sz: "OrgSz" = None
    cur_sz: "CurSz" = None
    flip: "Flip" = None
    rotation_info: "RotationInfo" = None
    rendering_info: "RenderingInfo" = None
    img: "Img" = None
    img_rect: "ImgRect" = None
    img_clip: "ImgClip" = None
    in_margin: "InMargin" = None
    img_dim: "ImgDim" = None
    sz: "ShapeSz" = None
    pos: "ShapePos" = None
    out_margin: "ShapeOutMargin" = None
    shape_comment: "ShapeComment" = None


@dataclass
class SubList:
    vert_align: str = "CENTER"
    paras: list = field(default_factory=list)


@dataclass
class TextMargin:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class DrawText:
    last_width: int = 0
    sub_list: "SubList" = None
    text_margin: "TextMargin" = None


@dataclass
class Rect:
    id: int = 0
    z_order: int = 0
    text_wrap: str = "TOP_AND_BOTTOM"
    text_flow: str = "BOTH_SIDES"
    group_level: int = 0
    instid: int = 0
    ratio: int = 0
    offset: "Offset" = None
    org_sz: "OrgSz" = None
    cur_sz: "CurSz" = None
    flip: "Flip" = None
    rotation_info: "RotationInfo" = None
    rendering_info: "RenderingInfo" = None
    sca2: "Matrix" = None    # None <=> source had no 2nd ScaleRotationMatrix
    rot2: "Matrix" = None
    line_shape: "LineShape" = None
    shadow: "Shadow" = None
    draw_text: "DrawText" = None   # None <=> no nested text
    points: list = field(default_factory=list)   # 4 Pt: outline p0..p3
    sz: "ShapeSz" = None          # None <=> nested (non-top-level) rect
    pos: "ShapePos" = None
    out_margin: "ShapeOutMargin" = None


@dataclass
class Container:
    id: int = 0
    z_order: int = 0
    text_wrap: str = "TOP_AND_BOTTOM"
    text_flow: str = "BOTH_SIDES"
    group_level: int = 0
    instid: int = 0
    offset: "Offset" = None
    org_sz: "OrgSz" = None
    cur_sz: "CurSz" = None
    flip: "Flip" = None
    rotation_info: "RotationInfo" = None
    rendering_info: "RenderingInfo" = None
    children: list = field(default_factory=list)
    # sz/pos/outMargin are the GShapeObjectControl placement, present only
    # for a top-level (group_level 0) container; a nested container (a later
    # task's data, not in current samples) would leave these None.
    sz: "ShapeSz" = None
    pos: "ShapePos" = None
    out_margin: "ShapeOutMargin" = None


@dataclass
class BinItem:
    id: str = ""
    filename: str = ""
    media_type: str = "application/octet-stream"
    data: bytes = b""
