"""Map an HWP line drawing (GShapeObjectControl) to an OWPML Line."""
from ..owpml.model import (
    Line, Offset, OrgSz, CurSz, Flip, RotationInfo, Matrix, RenderingInfo,
    LineShape, WinBrush, Shadow, Pt, ShapeSz, ShapePos, ShapeOutMargin,
)

_TEXT_WRAP = {"front": "IN_FRONT_OF_TEXT", "back": "BEHIND_TEXT",
              "block": "TOP_AND_BOTTOM", "square": "SQUARE",
              "tight": "TIGHT", "through": "THROUGH"}
_STROKE = {"solid": "SOLID", "none": "NONE", "dash": "DASH", "dot": "DOT",
           "dash-dot": "DASH_DOT"}
_LINE_END = {"flat": "FLAT", "round": "ROUND", "square": "SQUARE"}
_ARROW_STYLE = {"none": "NORMAL", "arrow": "ARROW", "spear": "SPEAR",
                "concave_arrow": "CONCAVE_ARROW"}
_ARROW_SIZE = {"smallest": "SMALL_SMALL", "small": "SMALL_SMALL",
               "medium": "MEDIUM_MEDIUM", "large": "LARGE_LARGE"}
_SZ_RELTO = {"absolute": "ABSOLUTE", "relative": "RELATIVE"}
_POS_RELTO = {"paper": "PAPER", "page": "PAGE", "paragraph": "PARA",
              "column": "COLUMN", "char": "CHAR"}
_HALIGN = {"left": "LEFT", "center": "CENTER", "right": "RIGHT",
           "inside": "INSIDE", "outside": "OUTSIDE"}
_VALIGN = {"top": "TOP", "center": "CENTER", "bottom": "BOTTOM",
           "inside": "INSIDE", "outside": "OUTSIDE"}


def _fmt(x):
    # matrix floats: 1.0 -> "1", 15.04 -> "15.04". Count-neutral (values ignored
    # by the count-based score); formatted to resemble Hancom's output.
    return str(int(x)) if float(x) == int(x) else ("%g" % float(x))


def _matrix(vals):
    a, b, c, d, e, f = vals
    return Matrix(e1=_fmt(a), e2=_fmt(c), e3=_fmt(e),
                  e4=_fmt(b), e5=_fmt(d), e6=_fmt(f))


def map_drawing(hd):
    if hd is None or hd.kind != "line" or hd.component is None or hd.line is None:
        return None
    comp = hd.component
    ls = hd.line
    return Line(
        id=hd.instance_id,
        z_order=hd.z_order,
        text_wrap=_TEXT_WRAP.get(hd.flow, "TOP_AND_BOTTOM"),
        offset=Offset(0, 0),
        org_sz=OrgSz(comp.initial_width, comp.initial_height),
        cur_sz=CurSz(comp.width, comp.height),
        flip=Flip(comp.flip & 1, (comp.flip >> 1) & 1),
        rotation_info=RotationInfo(angle=comp.angle, center_x=comp.center_x,
                                   center_y=comp.center_y, rotate_image=0),
        rendering_info=RenderingInfo(trans=_matrix(comp.trans_matrix),
                                     sca=_matrix(comp.scaler_matrix),
                                     rot=_matrix(comp.rotator_matrix)),
        line_shape=LineShape(
            color=ls.color, width=ls.width,
            style=_STROKE.get(ls.stroke, "SOLID"),
            end_cap=_LINE_END.get(ls.line_end, "FLAT"),
            head_style=_ARROW_STYLE.get(ls.arrow_start, "NORMAL"),
            tail_style=_ARROW_STYLE.get(ls.arrow_end, "NORMAL"),
            head_fill=ls.arrow_start_fill, tail_fill=ls.arrow_end_fill,
            head_sz=_ARROW_SIZE.get(ls.arrow_start_size, "SMALL_SMALL"),
            tail_sz=_ARROW_SIZE.get(ls.arrow_end_size, "SMALL_SMALL")),
        win_brush=WinBrush(),
        shadow=Shadow(),
        start_pt=Pt(ls.p0[0], ls.p0[1]),
        end_pt=Pt(ls.p1[0], ls.p1[1]),
        sz=ShapeSz(width=hd.width, width_rel_to=_SZ_RELTO.get(hd.width_relto, "ABSOLUTE"),
                   height=hd.height, height_rel_to=_SZ_RELTO.get(hd.height_relto, "ABSOLUTE")),
        pos=ShapePos(treat_as_char=hd.inline,
                     vert_rel_to=_POS_RELTO.get(hd.vrelto, "PAPER"),
                     horz_rel_to=_POS_RELTO.get(hd.hrelto, "PAPER"),
                     vert_align=_VALIGN.get(hd.valign, "TOP"),
                     horz_align=_HALIGN.get(hd.halign, "LEFT"),
                     vert_offset=hd.y, horz_offset=hd.x),
        out_margin=ShapeOutMargin(hd.margin_left, hd.margin_right,
                                  hd.margin_top, hd.margin_bottom),
    )
