"""Read a .hwp file into an in-memory model, via pyhwp's hwp5proc XML dump."""
import os
import sys
import subprocess
from lxml import etree
from .model import (
    HwpFont, HwpPanose, HwpCharShape, HwpParaShape, HwpDocInfo,
    HwpRun, HwpControl, HwpParagraph, HwpSection, HwpDocument,
    HwpBorder, HwpBorderFill, HwpTable, HwpTableRow, HwpTableCell,
    HwpStyle, HwpTab, HwpTabDef, HwpLineSeg,
    HwpPageDef, HwpNoteShape, HwpPageBorder, HwpColumnsDef, HwpPageNum,
    HwpSectionDef, HwpShapeComponent, HwpLineShape, HwpDrawing, HwpPicture,
    HwpDocProperties, HwpCompatDocument, HwpPageHide,
    HwpBookmark, HwpNewNumbering, HwpBullet,
    HwpRect, HwpDrawText,
)

_ALIGN_MAP = {
    "left": "LEFT", "center": "CENTER", "right": "RIGHT",
    "both": "JUSTIFY", "justify": "JUSTIFY",
    "distribute": "DISTRIBUTE", "divide": "DISTRIBUTE",
}

# HWP5 font language groups, in the fixed order pyhwp lays FaceName elements out.
_FONT_LANGS = ("ko", "en", "cn", "jp", "other", "symbol", "user")


def _hwp5proc():
    """Locate hwp5proc next to the current interpreter, else rely on PATH."""
    candidate = os.path.join(os.path.dirname(sys.executable), "hwp5proc")
    return candidate if os.path.exists(candidate) else "hwp5proc"


def hwp5_xml(hwp_path):
    """Return pyhwp's full XML dump of the parsed HWP record tree."""
    return subprocess.check_output([_hwp5proc(), "xml", hwp_path])


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _border_fill_id(v):
    """HWP5 borderfill-id is 1-based and equals the OWPML borderFill id we
    emit (definition id = document-order index + 1). Use the raw value; a
    missing/<1 value falls back to the first definition (id 1)."""
    n = _int(v, 0)
    return n if n >= 1 else 1


def _parse_panose(face_el):
    p = face_el.find("Panose1")
    if p is None:
        return None
    return HwpPanose(
        family_type=_int(p.get("family-type")),
        weight=_int(p.get("weight")),
        proportion=_int(p.get("proportion")),
        contrast=_int(p.get("contrast")),
        stroke_variation=_int(p.get("stroke-variation")),
        arm_style=_int(p.get("arm-style")),
        letterform=_int(p.get("letterform")),
        midline=_int(p.get("midline")),
        x_height=_int(p.get("x-height")),
    )


def _font_group_offsets(id_mappings):
    """Global start index of each language group within the flat FaceName list."""
    offsets = {}
    running = 0
    for lang in _FONT_LANGS:
        offsets[lang] = running
        running += _int(id_mappings.get("%s-fonts" % lang))
    return offsets


def _lang_metric(el, default):
    """Per-language child element -> HWP-keyed dict of ints (raw values)."""
    d = {}
    for lang in _FONT_LANGS:
        d[lang] = _int(el.get(lang), default) if el is not None else default
    return d


def _font_ref(ff, offsets):
    """FontFace element -> HWP-keyed dict of global font indices."""
    d = {}
    for lang in _FONT_LANGS:
        local = _int(ff.get(lang), 0) if ff is not None else 0
        d[lang] = offsets.get(lang, 0) + local
    return d


def _shadow_space(char_shape_el, axis):
    """ShadowSpace/@x|@y -> int (default 10)."""
    ss = char_shape_el.find("ShadowSpace")
    return _int(ss.get(axis), 10) if ss is not None else 10


def _parse_border_fills(id_mappings):
    out = []
    for i, bf_el in enumerate(id_mappings.findall("BorderFill")):
        borders = []
        for b in bf_el.findall("Border"):
            borders.append(HwpBorder(
                kind=b.get("attribute-name") or "",
                stroke_type=b.get("stroke-type") or "none",
                width=b.get("width") or "0.1mm",
                color=b.get("color") or "#000000",
            ))
        fcp = bf_el.find("FillColorPattern")
        fill_color = None
        if fcp is not None:
            bg = fcp.get("background-color")
            if bg and bg.lower() != "none":
                fill_color = bg
        out.append(HwpBorderFill(index=i, borders=borders, fill_color=fill_color))
    return out


def _parse_styles(id_mappings):
    out = []
    for i, el in enumerate(id_mappings.findall("Style")):
        out.append(HwpStyle(
            index=i,
            kind=(el.get("kind") or "paragraph").lower(),
            local_name=el.get("local-name") or "",
            eng_name=el.get("name") or "",
            para_shape_id=_int(el.get("parashape-id")),
            char_shape_id=_int(el.get("charshape-id")),
            next_style_id=_int(el.get("next-style-id")),
            lang_id=_int(el.get("lang-id"), 1042),
        ))
    return out


def _parse_tab_defs(id_mappings):
    out = []
    for i, el in enumerate(id_mappings.findall("TabDef")):
        tabs = []
        arr = el.find("Array")
        if arr is not None:
            for t in arr.findall("Tab"):
                tabs.append(HwpTab(
                    pos=_int(t.get("pos")),
                    kind=(t.get("kind") or "left").lower(),
                    fill_type=_int(t.get("fill-type")),
                ))
        out.append(HwpTabDef(
            index=i,
            auto_tab_left=_int(el.get("autotab-left")),
            auto_tab_right=_int(el.get("autotab-right")),
            tabs=tabs,
        ))
    return out


def _parse_bullets(id_mappings):
    out = []
    for el in id_mappings.findall("Bullet"):
        out.append(HwpBullet(
            char=el.get("char") or "-",
            align=(el.get("align") or "left").lower(),
            auto_indent=_int(el.get("auto-indent")),
            text_offset=_int(el.get("space")),
            width_adjust=_int(el.get("width")),
            char_shape_id=_int(el.get("charshape-id"), -1),
        ))
    return out


def _parse_doc_properties(root):
    el = root.find(".//DocumentProperties")
    if el is None:
        return None
    return HwpDocProperties(
        page_start=_int(el.get("page-startnum"), 1),
        footnote_start=_int(el.get("footnote-startnum"), 1),
        endnote_start=_int(el.get("endnote-startnum"), 1),
        pic_start=_int(el.get("picture-startnum"), 1),
        tbl_start=_int(el.get("table-startnum"), 1),
        equation_start=_int(el.get("math-startnum"), 1),
    )


def _parse_compat(root):
    el = root.find(".//CompatibleDocument")
    if el is None:
        return None
    return HwpCompatDocument(target=_int(el.get("target")))


def read_docinfo(xml_bytes):
    root = etree.fromstring(xml_bytes)
    id_mappings = root.find(".//IdMappings")
    if id_mappings is None:
        return HwpDocInfo()
    offsets = _font_group_offsets(id_mappings)

    fonts = [HwpFont(index=i, name=el.get("name") or "",
                     panose=_parse_panose(el))
             for i, el in enumerate(id_mappings.findall("FaceName"))]

    char_shapes = []
    for i, el in enumerate(id_mappings.findall("CharShape")):
        ff = el.find("FontFace")
        ko_local = _int(ff.get("ko")) if ff is not None else 0
        font_ref = _font_ref(ff, offsets)
        underline_raw = (el.get("underline") or "none").lower()
        char_shapes.append(HwpCharShape(
            index=i,
            base_size=_int(el.get("basesize"), 1000),
            text_color=el.get("text-color") or "#000000",
            font_id=offsets.get("ko", 0) + ko_local,
            bold=el.get("bold") == "1",
            italic=el.get("italic") == "1",
            font_ref=font_ref,
            ratio=_lang_metric(el.find("LetterWidthExpansion"), 100),
            spacing=_lang_metric(el.find("LetterSpacing"), 0),
            rel_sz=_lang_metric(el.find("RelativeSize"), 100),
            offset=_lang_metric(el.find("Position"), 0),
            shade_color=el.get("shade-color") or "#ffffff",
            underline_type="BOTTOM" if underline_raw not in ("none", "") else "NONE",
            underline_shape=(el.get("underline-style") or "solid").upper(),
            underline_color=el.get("underline-color") or "#000000",
            outline_type="SOLID" if _int(el.get("outline")) else "NONE",
            shadow_type="DROP" if _int(el.get("shadow")) else "NONE",
            shadow_color=(el.get("shadow-color") or "#c0c0c0").upper(),
            shadow_offset_x=_shadow_space(el, "x"),
            shadow_offset_y=_shadow_space(el, "y"),
            subscript=((_hex_int(el.get("charshapeflags")) >> 16) & 1) == 1,
        ))

    para_shapes = []
    for i, el in enumerate(id_mappings.findall("ParaShape")):
        raw = (el.get("align") or "left").lower()
        para_shapes.append(HwpParaShape(
            index=i,
            align=_ALIGN_MAP.get(raw, "LEFT"),
            indent=_int(el.get("indent")),
            margin_left=_int(el.get("doubled-margin-left")),
            margin_right=_int(el.get("doubled-margin-right")),
            margin_top=_int(el.get("doubled-margin-top")),
            margin_bottom=_int(el.get("doubled-margin-bottom")),
            line_spacing=_int(el.get("linespacing"), 100),
            line_spacing_type=el.get("linespacing-type") or "ratio",
            border_fill_id=_border_fill_id(el.get("borderfill-id")),
            level=_int(el.get("level")),
            tab_def_id=_int(el.get("tabdef-id")),
        ))

    return HwpDocInfo(fonts=fonts, char_shapes=char_shapes,
                      para_shapes=para_shapes,
                      border_fills=_parse_border_fills(id_mappings),
                      styles=_parse_styles(id_mappings),
                      tab_defs=_parse_tab_defs(id_mappings),
                      bullets=_parse_bullets(id_mappings),
                      doc_properties=_parse_doc_properties(root),
                      compat=_parse_compat(root))


def _parse_table(tc_el):
    body = tc_el.find("TableBody")
    if body is None:
        return HwpTable()
    rows = []
    for row_el in body.findall("TableRow"):
        cells = []
        for cell_el in row_el.findall("TableCell"):
            cells.append(HwpTableCell(
                col=_int(cell_el.get("col")),
                row=_int(cell_el.get("row")),
                col_span=_int(cell_el.get("colspan"), 1),
                row_span=_int(cell_el.get("rowspan"), 1),
                width=_int(cell_el.get("width")),
                height=_int(cell_el.get("height")),
                border_fill_id=_border_fill_id(cell_el.get("borderfill-id")),
                valign=cell_el.get("valign") or "middle",
                paragraphs=[parse_paragraph(p) for p in cell_el.findall("Paragraph")],
            ))
        rows.append(HwpTableRow(cells=cells))
    width = sum(c.width for c in rows[0].cells) if rows else 0
    return HwpTable(
        rows=_int(body.get("rows")),
        cols=_int(body.get("cols")),
        cell_spacing=_int(body.get("cellspacing")),
        border_fill_id=_border_fill_id(body.get("borderfill-id")),
        width=width,
        height=_int(tc_el.get("height")),
        table_rows=rows,
    )


_CONTROL_KIND = {"FIXWIDTH_SPACE": "fwSpace", "LINE_BREAK": "lineBreak",
                 "TAB": "tab", "TITLE_MARK": "titleMark"}

# ControlChar names whose HWP WCHAR-stream width is exactly 1 (matches the
# mapper's per-item width accounting). TITLE_MARK is code=8 kind=INLINE, a
# single WCHAR, so it is width-1 safe. Any other control char -- TAB (width
# 8), field/bookmark/etc. (width 8, or dropped/width 0 by the reader) --
# makes the paragraph's char-offset basis unreproducible by the mapper, so
# markpen attachment must be skipped for it (see markpen_unsafe).
_MARKPEN_SAFE_CONTROL_NAMES = {"LINE_BREAK", "FIXWIDTH_SPACE",
                               "PARAGRAPH_BREAK", "TITLE_MARK"}


def _hex_int(v):
    try:
        return int(v, 16)
    except (TypeError, ValueError):
        return 0


def _parse_line_segs(para_el):
    out = []
    for el in para_el.findall("LineSeg"):
        out.append(HwpLineSeg(
            text_pos=_int(el.get("chpos")),
            vert_pos=_int(el.get("y")),
            vert_size=_int(el.get("height")),
            text_height=_int(el.get("height-text")),
            baseline=_int(el.get("height-baseline")),
            spacing=_int(el.get("space-below")),
            horz_pos=_int(el.get("x")),
            horz_size=_int(el.get("width")),
            flags=_hex_int(el.get("lineseg-flags")),
        ))
    return out


def _matrix_values(m_el):
    if m_el is None:
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    return [_float(m_el.get(k)) for k in ("a", "b", "c", "d", "e", "f")]


def _parse_shape_component(comp_el):
    center = comp_el.find("Coord[@attribute-name='rotation_center']")
    trans = comp_el.find("Matrix[@attribute-name='translation']")
    srms = comp_el.findall(".//ScaleRotationMatrix")

    def _pair(idx):
        if idx < len(srms):
            return (_matrix_values(srms[idx].find("Matrix[@attribute-name='scaler']")),
                    _matrix_values(srms[idx].find("Matrix[@attribute-name='rotator']")))
        return ([1.0, 0.0, 0.0, 1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 1.0, 0.0, 0.0])

    # fall back to the pre-existing flat lookup when there is no ScaleRotationMatrix
    if srms:
        (sca1, rot1) = _pair(0)
        (sca2, rot2) = _pair(1)
    else:
        sca1 = _matrix_values(comp_el.find(".//Matrix[@attribute-name='scaler']"))
        rot1 = _matrix_values(comp_el.find(".//Matrix[@attribute-name='rotator']"))
        sca2, rot2 = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    return HwpShapeComponent(
        angle=_int(comp_el.get("angle")),
        flip=_int(comp_el.get("flip")),
        initial_width=_int(comp_el.get("initial-width")),
        initial_height=_int(comp_el.get("initial-height")),
        width=_int(comp_el.get("width")),
        height=_int(comp_el.get("height")),
        center_x=_int(center.get("x")) if center is not None else 0,
        center_y=_int(center.get("y")) if center is not None else 0,
        trans_matrix=_matrix_values(trans),
        scaler_matrix=sca1, rotator_matrix=rot1,
        scaler_matrix2=sca2, rotator_matrix2=rot2,
        has_matrix2=len(srms) >= 2,
    )


def _parse_line_shape(comp_el):
    bl = comp_el.find("BorderLine[@attribute-name='line']")
    if bl is None:
        bl = etree.Element("BorderLine")
    sl = comp_el.find("ShapeLine")
    p0 = sl.find("Coord[@attribute-name='p0']") if sl is not None else None
    p1 = sl.find("Coord[@attribute-name='p1']") if sl is not None else None
    return HwpLineShape(
        color=bl.get("color") or "#000000",
        width=_int(bl.get("width")),
        stroke=bl.get("stroke") or "solid",
        line_end=bl.get("line-end") or "flat",
        arrow_start=bl.get("arrow-start") or "none",
        arrow_end=bl.get("arrow-end") or "none",
        arrow_start_fill=_int(bl.get("arrow-start-fill"), 1),
        arrow_end_fill=_int(bl.get("arrow-end-fill"), 1),
        arrow_start_size=bl.get("arrow-start-size") or "smallest",
        arrow_end_size=bl.get("arrow-end-size") or "smallest",
        p0=(_int(p0.get("x")), _int(p0.get("y"))) if p0 is not None else (0, 0),
        p1=(_int(p1.get("x")), _int(p1.get("y"))) if p1 is not None else (0, 0),
    )


def _parse_picture(comp_el):
    sp = comp_el.find("ShapePicture")
    if sp is None:
        return None
    rect = sp.find("ImageRect")
    pts = [(0, 0), (0, 0), (0, 0), (0, 0)]
    if rect is not None:
        for i in range(4):
            c = rect.find("Coord[@attribute-name='p%d']" % i)
            if c is not None:
                pts[i] = (_int(c.get("x")), _int(c.get("y")))
    clip = sp.find("ImageClip")
    img_clip = ((_int(clip.get("left")), _int(clip.get("right")),
                 _int(clip.get("top")), _int(clip.get("bottom")))
                if clip is not None else (0, 0, 0, 0))
    info = sp.find("PictureInfo")
    return HwpPicture(
        instance_id=_int(sp.get("instance-id")),
        bindata_id=_int(info.get("bindata-id")) if info is not None else 0,
        img_rect=pts,
        img_clip=img_clip,
        brightness=_int(info.get("brightness")) if info is not None else 0,
        contrast=_int(info.get("contrast")) if info is not None else 0,
        effect=_int(info.get("effect")) if info is not None else 0,
        dim_width=_int(comp_el.get("initial-width")),
        dim_height=_int(comp_el.get("initial-height")),
    )


_VALIGN_BOX = {"top": "TOP", "middle": "CENTER", "bottom": "BOTTOM"}


def _parse_shape_rectangle_points(comp_el):
    """ShapeComponent > ShapeRectangle > Coord[@attribute-name='p0'..'p3'] ->
    4 (x, y) tuples. Defaults to a degenerate zero rect when absent."""
    pts = [(0, 0), (0, 0), (0, 0), (0, 0)]
    sr = comp_el.find("ShapeRectangle")
    if sr is None:
        return pts
    for i in range(4):
        c = sr.find("Coord[@attribute-name='p%d']" % i)
        if c is not None:
            pts[i] = (_int(c.get("x")), _int(c.get("y")))
    return pts


def _parse_rect(comp_el):
    bl = comp_el.find("BorderLine[@attribute-name='border']")
    tpl = comp_el.find("TextboxParagraphList")
    paras = []
    if tpl is not None:
        for p_el in tpl.findall("Paragraph"):
            paras.append(parse_paragraph(p_el))
    # A TextboxParagraphList with no actual paragraphs is treated the same as
    # no TextboxParagraphList at all: no <hp:drawText> gets emitted.
    dt = None
    if tpl is not None and paras:
        dt = HwpDrawText(
            last_width=_int(tpl.get("maxwidth")),
            vert_align=_VALIGN_BOX.get(tpl.get("valign") or "middle", "CENTER"),
            paragraphs=paras,
        )
    text_margin = (0, 0, 0, 0)
    if tpl is not None:
        text_margin = (_int(tpl.get("padding-left")), _int(tpl.get("padding-right")),
                       _int(tpl.get("padding-top")), _int(tpl.get("padding-bottom")))
    return HwpRect(
        line_color=(bl.get("color") if bl is not None else None) or "#000000",
        line_width=_int(bl.get("width")) if bl is not None else 0,
        draw_text=dt,
        points=_parse_shape_rectangle_points(comp_el),
        text_margin=text_margin,
    )


def _parse_child_component(comp_el):
    """A bare ShapeComponent nested inside a $con container (not wrapped in
    its own GShapeObjectControl) -> HwpDrawing. Reuses the same per-kind
    parsers as _parse_drawing; the shape-object placement attrs (flow, x, y,
    width, height, ...) are absent on nested components and stay defaulted."""
    chid = (comp_el.get("chid0") or comp_el.get("chid") or "").strip()
    if chid not in ("$lin", "$pic", "$rec", "$con"):
        return None
    common = dict(component=_parse_shape_component(comp_el))
    if chid == "$lin":
        return HwpDrawing(kind="line", line=_parse_line_shape(comp_el), **common)
    if chid == "$rec":
        return HwpDrawing(kind="rect", rect=_parse_rect(comp_el), **common)
    if chid == "$pic":
        return HwpDrawing(kind="pic", picture=_parse_picture(comp_el), **common)
    return HwpDrawing(kind="container", children=_parse_container_children(comp_el), **common)


def _parse_container_children(con_comp_el):
    """Direct ShapeComponent children of a $con component (findall is not
    recursive, so this returns only the immediate group members)."""
    out = []
    for child in con_comp_el.findall("ShapeComponent"):
        d = _parse_child_component(child)
        if d is not None:
            out.append(d)
    return out


def _parse_drawing(gso_el):
    """GShapeObjectControl -> HwpDrawing. Slice A+B+C: line ($lin), picture
    ($pic), rectangle ($rec), container ($con, recursive); other kinds
    return None (skipped)."""
    comp = gso_el.find("ShapeComponent")
    if comp is None:
        return None
    chid0 = (comp.get("chid0") or comp.get("chid") or "").strip()
    if chid0 not in ("$lin", "$pic", "$rec", "$con"):
        return None
    common = dict(
        instance_id=_int(gso_el.get("instance-id")),
        z_order=_int(gso_el.get("z-order")),
        flow=gso_el.get("flow") or "block",
        text_side=gso_el.get("text-side") or "both",
        x=_int(gso_el.get("x")),
        y=_int(gso_el.get("y")),
        width=_int(gso_el.get("width")),
        height=_int(gso_el.get("height")),
        hrelto=gso_el.get("hrelto") or "paper",
        vrelto=gso_el.get("vrelto") or "paper",
        halign=gso_el.get("halign") or "left",
        valign=gso_el.get("valign") or "top",
        inline=_int(gso_el.get("inline")),
        margin_left=_int(gso_el.get("margin-left")),
        margin_right=_int(gso_el.get("margin-right")),
        margin_top=_int(gso_el.get("margin-top")),
        margin_bottom=_int(gso_el.get("margin-bottom")),
        width_relto=gso_el.get("width-relto") or "absolute",
        height_relto=gso_el.get("height-relto") or "absolute",
        component=_parse_shape_component(comp),
    )
    if chid0 == "$lin":
        return HwpDrawing(kind="line", line=_parse_line_shape(comp), **common)
    if chid0 == "$rec":
        return HwpDrawing(kind="rect", rect=_parse_rect(comp), **common)
    if chid0 == "$con":
        return HwpDrawing(kind="container", children=_parse_container_children(comp), **common)
    return HwpDrawing(kind="pic", picture=_parse_picture(comp), **common)


def parse_paragraph(para_el):
    """Build one HwpParagraph. Walk LineSeg children in reading order,
    grouping consecutive Text + inline ControlChar (fwSpace/lineBreak) that
    share a charshape-id into one HwpRun; a charshape-id change, a table, or
    a PARAGRAPH_BREAK starts a new run. Finally, when the paragraph mark
    (PARAGRAPH_BREAK) carries a different char shape than the last visible run,
    append a trailing empty run for it — matching Hancom's one-run-per-charshape-
    segment output (the mark segment has no visible text)."""
    runs = []
    cur_cs = None
    cur_contents = []
    markpen_unsafe = False
    break_cs = None
    pending_ctrls = []       # leading ctrls for the next run (before <hp:t>)
    cur_trailing_ctrls = []  # trailing ctrls for the current run (after <hp:t>)

    def flush():
        nonlocal cur_cs, cur_contents, pending_ctrls, cur_trailing_ctrls
        if cur_contents:
            runs.append(HwpRun(char_shape_id=cur_cs, contents=cur_contents,
                               ctrls=pending_ctrls, ctrls_after=cur_trailing_ctrls))
            pending_ctrls = []
            cur_trailing_ctrls = []
        cur_cs = None
        cur_contents = []

    def attach_ctrl(ctrl):
        # An extended control met with pending text trails the current run;
        # met with none, it leads the next run. Reproduces Hancom's placement
        # (bookmark after its text, newNum before the following object).
        if cur_contents:
            cur_trailing_ctrls.append(ctrl)
        else:
            pending_ctrls.append(ctrl)

    for child in para_el.findall("LineSeg/*"):
        if child.tag == "Text":
            content = child.text or ""
            if not content:
                continue
            if any(ord(ch) > 0xFFFF for ch in content):
                markpen_unsafe = True
            cs = _int(child.get("charshape-id"))
            if cur_contents and cs != cur_cs:
                flush()
            cur_cs = cs
            cur_contents.append(content)
        elif child.tag == "ControlChar":
            if child.get("name") not in _MARKPEN_SAFE_CONTROL_NAMES:
                markpen_unsafe = True
            if child.get("name") == "PARAGRAPH_BREAK":
                v = child.get("charshape-id")
                break_cs = _int(v) if v is not None else None
            kind = _CONTROL_KIND.get(child.get("name"))
            if kind is None:
                continue  # PARAGRAPH_BREAK and any other control chars
            cs = _int(child.get("charshape-id"))
            if cur_contents and cs != cur_cs:
                flush()
            cur_cs = cs
            cur_contents.append(HwpControl(kind))
        elif child.tag == "TableControl":
            flush()
            runs.append(HwpRun(
                char_shape_id=_int(child.get("charshape-id")),
                contents=[],
                table=_parse_table(child),
                ctrls=pending_ctrls,
            ))
            pending_ctrls = []
        elif child.tag == "GShapeObjectControl":
            drawing = _parse_drawing(child)
            if drawing is not None:
                flush()
                runs.append(HwpRun(
                    char_shape_id=_int(child.get("charshape-id")),
                    contents=[],
                    drawing=drawing,
                    ctrls=pending_ctrls,
                ))
                pending_ctrls = []
        elif child.tag == "BookmarkControl":
            attach_ctrl(_parse_bookmark(child))
            markpen_unsafe = True   # extended control occupies char positions
        elif child.tag == "NewNumbering":
            attach_ctrl(_parse_new_numbering(child))
            markpen_unsafe = True   # extended control occupies char positions
        elif child.tag == "PageHide":
            pending_ctrls.append(_parse_page_hide(child))
            markpen_unsafe = True   # extended control occupies char positions
    flush()
    if pending_ctrls:
        # PageHide(s) with no following text run (e.g. an otherwise-empty
        # paragraph): Hancom emits a ctrl-only run carrying the paragraph-mark
        # char shape. Attach the leftover ctrls to such a run.
        runs.append(HwpRun(char_shape_id=break_cs if break_cs is not None else 0,
                           contents=[], ctrls=pending_ctrls))
        pending_ctrls = []
    last_cs = None
    for run in runs:
        if run.contents:
            last_cs = run.char_shape_id
    if break_cs is not None and last_cs is not None and break_cs != last_cs:
        runs.append(HwpRun(char_shape_id=break_cs, contents=[]))
    return HwpParagraph(
        para_shape_id=_int(para_el.get("parashape-id")),
        style_id=_int(para_el.get("style-id")),
        runs=runs,
        line_segs=_parse_line_segs(para_el),
        markpen_unsafe=markpen_unsafe,
    )


def _clamp_border_fill_id(n, border_fill_count):
    """Clamp a raw (1-based) borderfill-id ref into [1, border_fill_count],
    the range of actually-defined BorderFill ids, so it can never dangle."""
    if n < 1:
        return 1
    if n > border_fill_count:
        return border_fill_count
    return n


def _clamp_table_border_fill_ids(sections, border_fill_count):
    """`_border_fill_id` only guards the low end (raw 0/missing -> 1); a raw
    id past the last defined BorderFill would still dangle. Clamp every
    table/cell border_fill_id into [1, border_fill_count] here, once the
    definition count is known, by walking the already-parsed section tree
    (including nested tables inside cell paragraphs)."""
    if border_fill_count <= 0:
        return

    def _walk_table(table):
        table.border_fill_id = _clamp_border_fill_id(table.border_fill_id, border_fill_count)
        for row in table.table_rows:
            for cell in row.cells:
                cell.border_fill_id = _clamp_border_fill_id(cell.border_fill_id, border_fill_count)
                _walk_paragraphs(cell.paragraphs)

    def _walk_paragraphs(paragraphs):
        for para in paragraphs:
            for run in para.runs:
                if run.table is not None:
                    _walk_table(run.table)

    for sec in sections:
        _walk_paragraphs(sec.paragraphs)


def _clamp_para_shape_border_fill_ids(para_shapes, border_fill_count):
    """Mirror of `_clamp_table_border_fill_ids` for ParaShape refs: a
    paraShape's borderfill-id must also resolve to a defined BorderFill, or
    it emits a dangling `paraPr/@borderFillIDRef` in header.xml."""
    if border_fill_count <= 0:
        return
    for ps in para_shapes:
        ps.border_fill_id = _clamp_border_fill_id(ps.border_fill_id, border_fill_count)


def _clamp_index(n, count):
    """Clamp a 0-based ref into [0, count-1]; empty target -> 0."""
    if count <= 0:
        return 0
    if n < 0:
        return 0
    if n >= count:
        return count - 1
    return n


def _clamp_style_refs(styles, char_count, para_count):
    """Style paraPrIDRef/charPrIDRef/nextStyleIDRef must resolve or they
    dangle in header.xml. Clamp against the known definition counts."""
    style_count = len(styles)
    for s in styles:
        s.char_shape_id = _clamp_index(s.char_shape_id, char_count)
        s.para_shape_id = _clamp_index(s.para_shape_id, para_count)
        s.next_style_id = _clamp_index(s.next_style_id, style_count)


def _clamp_para_shape_tab_def_ids(para_shapes, tab_def_count):
    """Every paraPr tabPrIDRef must resolve to an emitted <hh:tabPr>."""
    for ps in para_shapes:
        ps.tab_def_id = _clamp_index(ps.tab_def_id, tab_def_count)


def _clamp_paragraph_style_ids(sections, style_count):
    """Every paragraph styleIDRef must resolve to an emitted <hh:style>."""
    def _walk(paragraphs):
        for para in paragraphs:
            para.style_id = _clamp_index(para.style_id, style_count)
            for run in para.runs:
                if run.table is not None:
                    for row in run.table.table_rows:
                        for cell in row.cells:
                            _walk(cell.paragraphs)
    for sec in sections:
        _walk(sec.paragraphs)


def _parse_page_hide(el):
    return HwpPageHide(
        hide_header=_int(el.get("header")),
        hide_footer=_int(el.get("footer")),
        hide_master_page=_int(el.get("basepage")),
        hide_border=_int(el.get("pageborder")),
        hide_fill=_int(el.get("pagefill")),
        hide_page_num=_int(el.get("pagenumber")),
    )


def _parse_bookmark(el):
    """<BookmarkControl><BookmarkControlData name="..."/></BookmarkControl>."""
    data = el.find("BookmarkControlData")
    name = data.get("name") if data is not None else el.get("name")
    return HwpBookmark(name=name or "")


# HWP NewNumbering @kind -> OWPML hp:newNum @numType. Only "page" occurs in the
# samples; other kinds map by upper-casing, with PAGE as the fallback.
_NEW_NUM_TYPE = {"page": "PAGE", "figure": "FIGURE", "picture": "PICTURE",
                 "table": "TABLE", "equation": "EQUATION"}


def _parse_new_numbering(el):
    """<NewNumbering kind="page" number="1"/> -> HwpNewNumbering."""
    kind = (el.get("kind") or "page").lower()
    return HwpNewNumbering(
        num=_int(el.get("number")) or 1,
        num_type=_NEW_NUM_TYPE.get(kind, kind.upper() or "PAGE"),
    )


def _parse_page_def(sec_el):
    pd = sec_el.find("PageDef")
    if pd is None:
        return None
    return HwpPageDef(
        width=_int(pd.get("width")),
        height=_int(pd.get("height")),
        orientation=pd.get("orientation") or "portrait",
        bookbinding=pd.get("bookbinding") or "left",
        bookbinding_offset=_int(pd.get("bookbinding-offset")),
        left_offset=_int(pd.get("left-offset")),
        right_offset=_int(pd.get("right-offset")),
        top_offset=_int(pd.get("top-offset")),
        bottom_offset=_int(pd.get("bottom-offset")),
        header_offset=_int(pd.get("header-offset")),
        footer_offset=_int(pd.get("footer-offset")),
    )


def _parse_note_shape(el):
    return HwpNoteShape(
        notes_spacing=_int(el.get("notes-spacing")),
        prefix=el.get("prefix") or "",
        suffix=el.get("suffix") or "",
        usersymbol=el.get("usersymbol") or "",
        stroke_type=el.get("stroke-type") or "none",
        line_width=el.get("width") or "0.12mm",
        splitter_length=_int(el.get("splitter-length")),
        splitter_color=el.get("splitter-color") or "#000000",
        splitter_margin_top=_int(el.get("splitter-margin-top")),
        splitter_margin_bottom=_int(el.get("splitter-margin-bottom")),
        starting_number=_int(el.get("starting-number"), 1),
    )


def _parse_page_borders(sec_el):
    out = []
    for el in sec_el.findall("PageBorderFill"):
        out.append(HwpPageBorder(
            borderfill_id=_int(el.get("borderfill-id"), 1),
            relative_to=el.get("relative-to") or "paper",
            fill=el.get("fill") or "paper",
            include_header=_int(el.get("include-header")),
            include_footer=_int(el.get("include-footer")),
            margin_left=_int(el.get("margin-left")),
            margin_right=_int(el.get("margin-right")),
            margin_top=_int(el.get("margin-top")),
            margin_bottom=_int(el.get("margin-bottom")),
        ))
    return out


def _parse_section_def(sec_el):
    first_para = sec_el.find("ColumnSet/Paragraph")  # per-section scope
    columns = None
    page_num = None
    if first_para is not None:
        cd = first_para.find(".//ColumnsDef")
        if cd is not None:
            columns = HwpColumnsDef(
                count=_int(cd.get("count"), 1),
                kind=cd.get("kind") or "normal",
                direction=cd.get("direction") or "l2r",
                same_widths=_int(cd.get("same-widths"), 1),
            )
        pn = first_para.find(".//PageNumberPosition")
        if pn is not None:
            page_num = HwpPageNum(
                position=pn.get("position") or "bottom_center",
                shape=_int(pn.get("shape")),
                dash=pn.get("dash") or "-",
            )
    foots = sec_el.findall("FootnoteShape")
    return HwpSectionDef(
        column_spacing=_int(sec_el.get("columnspacing")),
        default_tab_stops=_int(sec_el.get("defaultTabStops")),
        text_direction=_int(sec_el.get("text-direction")),
        grid_horizontal=_int(sec_el.get("grid-horizontal")),
        grid_vertical=_int(sec_el.get("grid-vertical")),
        squared_manuscript_paper=_int(sec_el.get("squared-manuscript-paper")),
        numbering_shape_id=_int(sec_el.get("numbering-shape-id")),
        starting_pagenum=_int(sec_el.get("starting-pagenum")),
        starting_picturenum=_int(sec_el.get("starting-picturenum")),
        starting_tablenum=_int(sec_el.get("starting-tablenum")),
        starting_equationnum=_int(sec_el.get("starting-equationnum")),
        pagenum_on_split_section=_int(sec_el.get("pagenum-on-split-section")),
        hide_header=_int(sec_el.get("hide-header")),
        hide_footer=_int(sec_el.get("hide-footer")),
        hide_border=_int(sec_el.get("hide-border")),
        hide_pagenumber=_int(sec_el.get("hide-pagenumber")),
        hide_blank_line=_int(sec_el.get("hide-blank-line")),
        show_background_on_first_page_only=_int(
            sec_el.get("show-background-on-first-page-only")),
        page=_parse_page_def(sec_el),
        footnote=_parse_note_shape(foots[0]) if len(foots) >= 1 else None,
        endnote=_parse_note_shape(foots[1]) if len(foots) >= 2 else None,
        page_borders=_parse_page_borders(sec_el),
        columns=columns,
        page_num=page_num,
    )


def read_document(xml_bytes):
    docinfo = read_docinfo(xml_bytes)
    root = etree.fromstring(xml_bytes)
    sections = []
    for sec_el in root.findall(".//SectionDef"):
        paras = []
        for col in sec_el.findall("ColumnSet"):
            for para_el in col.findall("Paragraph"):
                paras.append(parse_paragraph(para_el))
        sections.append(HwpSection(paragraphs=paras,
                                   sec_def=_parse_section_def(sec_el)))
    if not sections:
        sections = [HwpSection(paragraphs=[])]
    border_fill_count = len(docinfo.border_fills)
    _clamp_table_border_fill_ids(sections, border_fill_count)
    _clamp_para_shape_border_fill_ids(docinfo.para_shapes, border_fill_count)
    _clamp_style_refs(docinfo.styles, len(docinfo.char_shapes),
                      len(docinfo.para_shapes))
    _clamp_paragraph_style_ids(sections, len(docinfo.styles))
    _clamp_para_shape_tab_def_ids(docinfo.para_shapes, len(docinfo.tab_defs))
    return HwpDocument(docinfo=docinfo, sections=sections)
