"""Map HWP section-definition records to an OWPML SecPr."""
from ..owpml.model import (
    SecPr, Grid, StartNum, Visibility, LineNumberShape, PagePr, Margin,
    NotePr, AutoNumFormat, NoteLine, NoteSpacing, Numbering, Placement,
    PageBorderFill, PageBorderOffset, ColPr, PageNum,
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
_PAGE_STARTS = {0: "BOTH", 1: "EVEN", 2: "ODD"}  # HWP pagenum-on-split-section


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
            offset=PageBorderOffset(left=b.margin_left, right=b.margin_right,
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
        start_num=StartNum(
            page_starts_on=_PAGE_STARTS.get(sd.pagenum_on_split_section, "BOTH"),
            page=sd.starting_pagenum, pic=sd.starting_picturenum,
            tbl=sd.starting_tablenum, equation=sd.starting_equationnum),
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
