"""Map an HWP drawing (GShapeObjectControl) to an OWPML Line, Pic, or Rect."""
from ..owpml.model import (
    Line, Offset, OrgSz, CurSz, Flip, RotationInfo, Matrix, RenderingInfo,
    LineShape, WinBrush, Shadow, Pt, ShapeSz, ShapePos, ShapeOutMargin,
    Pic, Img, ImgRect, ImgClip, InMargin, ImgDim, ShapeComment,
    Rect, DrawText, SubList, TextMargin, Container,
)
from .body import map_paragraph

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
_PIC_EFFECT = {0: "REAL_PIC", 1: "GRAY_SCALE", 2: "BLACK_WHITE"}


def _fmt(x):
    # matrix floats: 1.0 -> "1", 15.04 -> "15.04". Count-neutral (values ignored
    # by the count-based score); formatted to resemble Hancom's output.
    return str(int(x)) if float(x) == int(x) else ("%g" % float(x))


def _matrix(vals):
    a, b, c, d, e, f = vals
    return Matrix(e1=_fmt(a), e2=_fmt(c), e3=_fmt(e),
                  e4=_fmt(b), e5=_fmt(d), e6=_fmt(f))


def _common_container(hd, comp, rotate_image):
    return dict(
        id=hd.instance_id,
        z_order=hd.z_order,
        text_wrap=_TEXT_WRAP.get(hd.flow, "TOP_AND_BOTTOM"),
        offset=Offset(0, 0),
        org_sz=OrgSz(comp.initial_width, comp.initial_height),
        cur_sz=CurSz(comp.width, comp.height),
        flip=Flip(comp.flip & 1, (comp.flip >> 1) & 1),
        rotation_info=RotationInfo(angle=comp.angle, center_x=comp.center_x,
                                   center_y=comp.center_y, rotate_image=rotate_image),
        rendering_info=RenderingInfo(trans=_matrix(comp.trans_matrix),
                                     sca=_matrix(comp.scaler_matrix),
                                     rot=_matrix(comp.rotator_matrix)),
        sz=ShapeSz(width=hd.width,
                   width_rel_to=_SZ_RELTO.get(hd.width_relto, "ABSOLUTE"),
                   height=hd.height,
                   height_rel_to=_SZ_RELTO.get(hd.height_relto, "ABSOLUTE")),
        pos=ShapePos(treat_as_char=hd.inline,
                     vert_rel_to=_POS_RELTO.get(hd.vrelto, "PAPER"),
                     horz_rel_to=_POS_RELTO.get(hd.hrelto, "PAPER"),
                     vert_align=_VALIGN.get(hd.valign, "TOP"),
                     horz_align=_HALIGN.get(hd.halign, "LEFT"),
                     vert_offset=hd.y, horz_offset=hd.x),
        out_margin=ShapeOutMargin(hd.margin_left, hd.margin_right,
                                  hd.margin_top, hd.margin_bottom),
    )


def _map_line(hd):
    comp, ls = hd.component, hd.line
    return Line(
        **_common_container(hd, comp, 0),
        line_shape=LineShape(
            color=ls.color, width=ls.width,
            style=_STROKE.get(ls.stroke, "SOLID"),
            end_cap=_LINE_END.get(ls.line_end, "FLAT"),
            head_style=_ARROW_STYLE.get(ls.arrow_start, "NORMAL"),
            tail_style=_ARROW_STYLE.get(ls.arrow_end, "NORMAL"),
            head_fill=ls.arrow_start_fill, tail_fill=ls.arrow_end_fill,
            head_sz=_ARROW_SIZE.get(ls.arrow_start_size, "SMALL_SMALL"),
            tail_sz=_ARROW_SIZE.get(ls.arrow_end_size, "SMALL_SMALL")),
        win_brush=WinBrush(), shadow=Shadow(),
        start_pt=Pt(ls.p0[0], ls.p0[1]), end_pt=Pt(ls.p1[0], ls.p1[1]),
    )


def _map_pic(hd, bin_index=None):
    comp, pic = hd.component, hd.picture
    r = pic.img_rect
    idx = (bin_index or {}).get(pic.bindata_id, pic.bindata_id)
    return Pic(
        **_common_container(hd, comp, 1),
        instid=pic.instance_id,
        img=Img(bin_item_id="image%d" % idx, bright=pic.brightness,
                contrast=pic.contrast, effect=_PIC_EFFECT.get(pic.effect, "REAL_PIC")),
        img_rect=ImgRect(pt0=Pt(*r[0]), pt1=Pt(*r[1]), pt2=Pt(*r[2]), pt3=Pt(*r[3])),
        img_clip=ImgClip(left=pic.img_clip[0], right=pic.img_clip[1],
                         top=pic.img_clip[2], bottom=pic.img_clip[3]),
        in_margin=InMargin(),
        img_dim=ImgDim(pic.dim_width, pic.dim_height),
        shape_comment=ShapeComment(text="그림"),   # Hancom alt-text not stored in HWP
    )


def _map_rect(hd, bin_index=None):
    comp, rc = hd.component, hd.rect
    dt = None
    if rc.draw_text is not None:
        sub = SubList(vert_align=rc.draw_text.vert_align,
                      paras=[map_paragraph(p, 0, bin_index) for p in rc.draw_text.paragraphs])
        l, r, t, b = rc.text_margin
        dt = DrawText(last_width=rc.draw_text.last_width, sub_list=sub,
                     text_margin=TextMargin(left=l, right=r, top=t, bottom=b))
    common = _common_container(hd, comp, 0)
    return Rect(
        id=common["id"], z_order=common["z_order"], text_wrap=common["text_wrap"],
        instid=hd.instance_id, group_level=0, ratio=0,
        offset=common["offset"], org_sz=common["org_sz"], cur_sz=common["cur_sz"],
        flip=common["flip"], rotation_info=common["rotation_info"],
        rendering_info=common["rendering_info"],
        # 2nd matrix pair is present only when the source actually had one.
        sca2=_matrix(comp.scaler_matrix2) if comp.has_matrix2 else None,
        rot2=_matrix(comp.rotator_matrix2) if comp.has_matrix2 else None,
        line_shape=LineShape(color=rc.line_color, width=rc.line_width,
                             style="NONE", end_cap="FLAT"),
        shadow=Shadow(),
        draw_text=dt,
        points=[Pt(x, y) for x, y in rc.points],
        # sz/pos/outMargin are the GShapeObjectControl placement, present
        # for top-level rects (this task); nested rects (a later task) are
        # not wrapped in their own GSO and won't populate these.
        sz=common["sz"], pos=common["pos"], out_margin=common["out_margin"],
    )


def _map_shape(hd, group_level, bin_index=None):
    """Map any HwpDrawing child at a given group level -- shared by a
    container's recursive children. A nested shape (group_level > 0) never
    carries its own GShapeObjectControl, so its trailing placement block
    (sz/pos/outMargin, plus shapeComment for pics) is suppressed here; only
    the top-level container/shape (mapped outside this helper) keeps it.

    A nested $lin (line) child is deliberately dropped (returns None)
    rather than mapped: unlike Pic/Rect/Container, _write_line has no
    None-guard on ln.sz/ln.pos/ln.out_margin -- it unconditionally
    dereferences them for the trailing placement block. Nulling them out
    here the way we do for the other kinds would just move the crash into
    the writer instead of avoiding it, and no current sample nests a line
    in a container. Until _write_line grows the same guard _write_pic has,
    treat this as a recoverable fidelity miss (consistent with the
    existing "unsupported chid -> None" pattern elsewhere), not a crash."""
    if hd.kind == "pic" and hd.picture is not None:
        m = _map_pic(hd, bin_index)
    elif hd.kind == "rect" and hd.rect is not None:
        m = _map_rect(hd, bin_index)
    elif hd.kind == "container":
        m = _map_container(hd, group_level, bin_index)
    else:
        return None
    if hasattr(m, "group_level"):
        m.group_level = group_level
    if group_level > 0:
        if hasattr(m, "sz"):
            m.sz = None
        if hasattr(m, "pos"):
            m.pos = None
        if hasattr(m, "out_margin"):
            m.out_margin = None
        if hasattr(m, "shape_comment"):
            m.shape_comment = None
    return m


def _map_container(hd, group_level=0, bin_index=None):
    comp = hd.component
    common = _common_container(hd, comp, 0)
    children = [c for c in (_map_shape(ch, group_level + 1, bin_index) for ch in hd.children)
                if c is not None]
    return Container(
        id=common["id"], z_order=common["z_order"], text_wrap=common["text_wrap"],
        instid=hd.instance_id, group_level=group_level,
        offset=common["offset"], org_sz=common["org_sz"], cur_sz=common["cur_sz"],
        flip=common["flip"], rotation_info=common["rotation_info"],
        rendering_info=common["rendering_info"],
        children=children,
        sz=common["sz"], pos=common["pos"], out_margin=common["out_margin"],
    )


def map_drawing(hd, bin_index=None):
    if hd is None or hd.component is None:
        return None
    if hd.kind == "line" and hd.line is not None:
        return _map_line(hd)
    if hd.kind == "pic" and hd.picture is not None:
        return _map_pic(hd, bin_index)
    if hd.kind == "rect" and hd.rect is not None:
        return _map_rect(hd, bin_index)
    if hd.kind == "container":
        return _map_container(hd, 0, bin_index)
    return None
