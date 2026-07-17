"""Serialize an OWPML Section to Contents/sectionN.xml."""
from lxml import etree
from ..constants import NS, XML_DECL
from ..owpml.model import (
    Control, Pic, Rect, MarkpenBegin, MarkpenEnd, PageHiding, Bookmark, NewNum,
)

_NSMAP = {k: v for k, v in NS.items()}


def _hs(tag):
    return "{%s}%s" % (NS["hs"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _hc(tag):
    return "{%s}%s" % (NS["hc"], tag)


def _run_has_inline_object(run):
    """True when the run carries an inline (treatAsChar=1) object — a table
    (always emitted inline) or a drawing whose pos.treat_as_char is 1. Such a
    run gets a trailing empty <hp:t/> anchor, matching Hancom."""
    if getattr(run, "table", None) is not None:
        return True
    d = getattr(run, "drawing", None)
    if d is not None:
        pos = getattr(d, "pos", None)
        return pos is not None and getattr(pos, "treat_as_char", 0) == 1
    return False


def _write_ctrl(run_el, c):
    """Emit one <hp:ctrl> wrapping a single control (pageHiding/bookmark/newNum)."""
    ctrl = etree.SubElement(run_el, _hp("ctrl"))
    if isinstance(c, PageHiding):
        ph = etree.SubElement(ctrl, _hp("pageHiding"))
        ph.set("hideHeader", str(c.hide_header))
        ph.set("hideFooter", str(c.hide_footer))
        ph.set("hideMasterPage", str(c.hide_master_page))
        ph.set("hideBorder", str(c.hide_border))
        ph.set("hideFill", str(c.hide_fill))
        ph.set("hidePageNum", str(c.hide_page_num))
    elif isinstance(c, Bookmark):
        etree.SubElement(ctrl, _hp("bookmark")).set("name", c.name)
    elif isinstance(c, NewNum):
        nn = etree.SubElement(ctrl, _hp("newNum"))
        nn.set("num", str(c.num))
        nn.set("numType", c.num_type)


def _write_run(p_el, run, state):
    r = etree.SubElement(p_el, _hp("run"))
    r.set("charPrIDRef", str(run.char_pr_id))
    for c in getattr(run, "ctrls", ()):
        _write_ctrl(r, c)
    if run.texts:
        te = etree.SubElement(r, _hp("t"))
        last = None  # last inline child; text after it goes to its .tail
        for item in run.texts:
            if isinstance(item, Control):
                last = etree.SubElement(te, _hp(item.kind))
                if item.kind == "tab":
                    last.set("width", "0")
                    last.set("leader", "0")
                    last.set("type", "0")
                elif item.kind == "titleMark":
                    last.set("ignore", "1")
            elif isinstance(item, MarkpenBegin):
                last = etree.SubElement(te, _hp("markpenBegin"))
                last.set("color", item.color)
            elif isinstance(item, MarkpenEnd):
                last = etree.SubElement(te, _hp("markpenEnd"))
            else:  # Text
                if last is None:
                    te.text = (te.text or "") + item.content
                else:
                    last.tail = (last.tail or "") + item.content
    if getattr(run, "table", None) is not None:
        _write_table(r, run.table, state)
    if getattr(run, "drawing", None) is not None:
        if isinstance(run.drawing, Pic):
            _write_pic(r, run.drawing)
        elif isinstance(run.drawing, Rect):
            _write_rect(r, run.drawing, state)
        else:
            _write_line(r, run.drawing)
    if _run_has_inline_object(run):
        # inline object anchor: Hancom writes a trailing empty <hp:t/> here.
        etree.SubElement(r, _hp("t"))
    for c in getattr(run, "ctrls_after", ()):
        # trailing ctrls (e.g. bookmark) sit after the run's <hp:t>.
        _write_ctrl(r, c)


def _write_sec_pr(run_el, sp):
    s = etree.SubElement(run_el, _hp("secPr"))
    for k, v in (("id", sp.id), ("textDirection", sp.text_direction),
                 ("spaceColumns", str(sp.space_columns)),
                 ("tabStop", str(sp.tab_stop)),
                 ("tabStopVal", str(sp.tab_stop_val)),
                 ("tabStopUnit", sp.tab_stop_unit),
                 ("outlineShapeIDRef", str(sp.outline_shape_id)),
                 ("memoShapeIDRef", str(sp.memo_shape_id)),
                 ("textVerticalWidthHead", str(sp.text_vertical_width_head)),
                 ("masterPageCnt", str(sp.master_page_cnt))):
        s.set(k, v)

    g = etree.SubElement(s, _hp("grid"))
    g.set("lineGrid", str(sp.grid.line_grid))
    g.set("charGrid", str(sp.grid.char_grid))
    g.set("wonggojiFormat", str(sp.grid.wonggoji_format))

    sn = etree.SubElement(s, _hp("startNum"))
    sn.set("pageStartsOn", sp.start_num.page_starts_on)
    for k, val in (("page", sp.start_num.page), ("pic", sp.start_num.pic),
                   ("tbl", sp.start_num.tbl), ("equation", sp.start_num.equation)):
        sn.set(k, str(val))

    v = sp.visibility
    vis = etree.SubElement(s, _hp("visibility"))
    vis.set("hideFirstHeader", str(v.hide_first_header))
    vis.set("hideFirstFooter", str(v.hide_first_footer))
    vis.set("hideFirstMasterPage", str(v.hide_first_master_page))
    vis.set("border", v.border)
    vis.set("fill", v.fill)
    vis.set("hideFirstPageNum", str(v.hide_first_page_num))
    vis.set("hideFirstEmptyLine", str(v.hide_first_empty_line))
    vis.set("showLineNumber", str(v.show_line_number))

    ln = sp.line_number_shape
    lns = etree.SubElement(s, _hp("lineNumberShape"))
    lns.set("restartType", str(ln.restart_type))
    lns.set("countBy", str(ln.count_by))
    lns.set("distance", str(ln.distance))
    lns.set("startNumber", str(ln.start_number))

    if sp.page_pr is not None:
        pp = etree.SubElement(s, _hp("pagePr"))
        pp.set("landscape", sp.page_pr.landscape)
        pp.set("width", str(sp.page_pr.width))
        pp.set("height", str(sp.page_pr.height))
        pp.set("gutterType", sp.page_pr.gutter_type)
        mg = sp.page_pr.margin
        m = etree.SubElement(pp, _hp("margin"))
        for k, val in (("header", mg.header), ("footer", mg.footer),
                       ("gutter", mg.gutter), ("left", mg.left),
                       ("right", mg.right), ("top", mg.top), ("bottom", mg.bottom)):
            m.set(k, str(val))

    for tag, note in (("footNotePr", sp.foot_note_pr),
                      ("endNotePr", sp.end_note_pr)):
        if note is None:
            continue
        n = etree.SubElement(s, _hp(tag))
        anf = etree.SubElement(n, _hp("autoNumFormat"))
        anf.set("type", note.auto_num_format.type)
        anf.set("userChar", note.auto_num_format.user_char)
        anf.set("prefixChar", note.auto_num_format.prefix_char)
        anf.set("suffixChar", note.auto_num_format.suffix_char)
        anf.set("supscript", str(note.auto_num_format.supscript))
        nl = etree.SubElement(n, _hp("noteLine"))
        nl.set("length", str(note.note_line.length))
        nl.set("type", note.note_line.type)
        nl.set("width", note.note_line.width)
        nl.set("color", note.note_line.color)
        ns = etree.SubElement(n, _hp("noteSpacing"))
        ns.set("betweenNotes", str(note.note_spacing.between_notes))
        ns.set("belowLine", str(note.note_spacing.below_line))
        ns.set("aboveLine", str(note.note_spacing.above_line))
        nm = etree.SubElement(n, _hp("numbering"))
        nm.set("type", note.numbering.type)
        nm.set("newNum", str(note.numbering.new_num))
        pl = etree.SubElement(n, _hp("placement"))
        pl.set("place", note.placement.place)
        pl.set("beneathText", str(note.placement.beneath_text))

    for pbf in sp.page_border_fills:
        b = etree.SubElement(s, _hp("pageBorderFill"))
        b.set("type", pbf.type)
        b.set("borderFillIDRef", str(pbf.border_fill_id))
        b.set("textBorder", pbf.text_border)
        b.set("headerInside", str(pbf.header_inside))
        b.set("footerInside", str(pbf.footer_inside))
        b.set("fillArea", pbf.fill_area)
        o = etree.SubElement(b, _hp("offset"))
        o.set("left", str(pbf.offset.left))
        o.set("right", str(pbf.offset.right))
        o.set("top", str(pbf.offset.top))
        o.set("bottom", str(pbf.offset.bottom))


def _write_ctrl_colpr(run_el, col_pr):
    ctrl = etree.SubElement(run_el, _hp("ctrl"))
    c = etree.SubElement(ctrl, _hp("colPr"))
    c.set("id", col_pr.id)
    c.set("type", col_pr.type)
    c.set("layout", col_pr.layout)
    c.set("colCount", str(col_pr.col_count))
    c.set("sameSz", str(col_pr.same_sz))
    c.set("sameGap", str(col_pr.same_gap))


def _write_ctrl_pagenum(run_el, page_num):
    ctrl = etree.SubElement(run_el, _hp("ctrl"))
    pn = etree.SubElement(ctrl, _hp("pageNum"))
    pn.set("pos", page_num.pos)
    pn.set("formatType", page_num.format_type)
    pn.set("sideChar", page_num.side_char)


def _write_paragraph(parent_el, para, state, sec_pr=None):
    p = etree.SubElement(parent_el, _hp("p"))
    p.set("id", str(state["para_id"]))
    state["para_id"] += 1
    p.set("paraPrIDRef", str(para.para_pr_id))
    p.set("styleIDRef", str(para.style_id))
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")
    if sec_pr is not None:
        cref = para.runs[0].char_pr_id if para.runs else 0
        lead = etree.SubElement(p, _hp("run"))
        lead.set("charPrIDRef", str(cref))
        _write_sec_pr(lead, sec_pr)
        if sec_pr.col_pr is not None:
            _write_ctrl_colpr(lead, sec_pr.col_pr)
        if sec_pr.page_num is not None:
            _write_ctrl_pagenum(lead, sec_pr.page_num)
    for run in para.runs:
        _write_run(p, run, state)
    if para.line_segs:
        lsa = etree.SubElement(p, _hp("linesegarray"))
        for ls in para.line_segs:
            seg = etree.SubElement(lsa, _hp("lineseg"))
            seg.set("textpos", str(ls.text_pos))
            seg.set("vertpos", str(ls.vert_pos))
            seg.set("vertsize", str(ls.vert_size))
            seg.set("textheight", str(ls.text_height))
            seg.set("baseline", str(ls.baseline))
            seg.set("spacing", str(ls.spacing))
            seg.set("horzpos", str(ls.horz_pos))
            seg.set("horzsize", str(ls.horz_size))
            seg.set("flags", str(ls.flags))


def _write_pic(run_el, p):
    e = etree.SubElement(run_el, _hp("pic"))
    for k, v in (("id", str(p.id)), ("zOrder", str(p.z_order)),
                 ("numberingType", "PICTURE"), ("textWrap", p.text_wrap),
                 ("textFlow", p.text_flow), ("lock", "0"),
                 ("dropcapstyle", "None"), ("href", ""), ("groupLevel", "0"),
                 ("instid", str(p.instid)), ("reverse", str(p.reverse))):
        e.set(k, v)
    off = etree.SubElement(e, _hp("offset"))
    off.set("x", str(p.offset.x)); off.set("y", str(p.offset.y))
    osz = etree.SubElement(e, _hp("orgSz"))
    osz.set("width", str(p.org_sz.width)); osz.set("height", str(p.org_sz.height))
    csz = etree.SubElement(e, _hp("curSz"))
    csz.set("width", str(p.cur_sz.width)); csz.set("height", str(p.cur_sz.height))
    fl = etree.SubElement(e, _hp("flip"))
    fl.set("horizontal", str(p.flip.horizontal)); fl.set("vertical", str(p.flip.vertical))
    ri = p.rotation_info
    r = etree.SubElement(e, _hp("rotationInfo"))
    r.set("angle", str(ri.angle)); r.set("centerX", str(ri.center_x))
    r.set("centerY", str(ri.center_y)); r.set("rotateimage", str(ri.rotate_image))
    rend = etree.SubElement(e, _hp("renderingInfo"))
    for tag, m in (("transMatrix", p.rendering_info.trans),
                   ("scaMatrix", p.rendering_info.sca),
                   ("rotMatrix", p.rendering_info.rot)):
        me = etree.SubElement(rend, _hc(tag))
        for i in range(1, 7):
            me.set("e%d" % i, getattr(m, "e%d" % i))
    im = etree.SubElement(e, _hc("img"))
    im.set("binaryItemIDRef", p.img.bin_item_id); im.set("bright", str(p.img.bright))
    im.set("contrast", str(p.img.contrast)); im.set("effect", p.img.effect)
    im.set("alpha", str(p.img.alpha))
    irc = etree.SubElement(e, _hp("imgRect"))
    for name, pt in (("pt0", p.img_rect.pt0), ("pt1", p.img_rect.pt1),
                     ("pt2", p.img_rect.pt2), ("pt3", p.img_rect.pt3)):
        pe = etree.SubElement(irc, _hc(name))
        pe.set("x", str(pt.x)); pe.set("y", str(pt.y))
    ic = etree.SubElement(e, _hp("imgClip"))
    ic.set("left", str(p.img_clip.left)); ic.set("right", str(p.img_clip.right))
    ic.set("top", str(p.img_clip.top)); ic.set("bottom", str(p.img_clip.bottom))
    inm = etree.SubElement(e, _hp("inMargin"))
    for side in ("left", "right", "top", "bottom"):
        inm.set(side, str(getattr(p.in_margin, side)))
    idim = etree.SubElement(e, _hp("imgDim"))
    idim.set("dimwidth", str(p.img_dim.dim_width))
    idim.set("dimheight", str(p.img_dim.dim_height))
    etree.SubElement(e, _hp("effects"))
    sz = etree.SubElement(e, _hp("sz"))
    sz.set("width", str(p.sz.width)); sz.set("widthRelTo", p.sz.width_rel_to)
    sz.set("height", str(p.sz.height)); sz.set("heightRelTo", p.sz.height_rel_to)
    sz.set("protect", str(p.sz.protect))
    po = p.pos
    pe = etree.SubElement(e, _hp("pos"))
    for k, v in (("treatAsChar", str(po.treat_as_char)),
                 ("affectLSpacing", str(po.affect_lspacing)),
                 ("flowWithText", str(po.flow_with_text)),
                 ("allowOverlap", str(po.allow_overlap)),
                 ("holdAnchorAndSO", str(po.hold_anchor_and_so)),
                 ("vertRelTo", po.vert_rel_to), ("horzRelTo", po.horz_rel_to),
                 ("vertAlign", po.vert_align), ("horzAlign", po.horz_align),
                 ("vertOffset", str(po.vert_offset)), ("horzOffset", str(po.horz_offset))):
        pe.set(k, v)
    om = etree.SubElement(e, _hp("outMargin"))
    for side in ("left", "right", "top", "bottom"):
        om.set(side, str(getattr(p.out_margin, side)))
    sc = etree.SubElement(e, _hp("shapeComment"))
    sc.text = p.shape_comment.text if p.shape_comment is not None else ""


def _write_shape_geom(el, obj):
    """Shared offset/orgSz/curSz/flip/rotationInfo prologue, common to all
    drawing-shape kinds. Only `_write_rect` uses this so far; refactoring
    `_write_pic`/`_write_line` onto it is out of scope for this change."""
    off = etree.SubElement(el, _hp("offset"))
    off.set("x", str(obj.offset.x)); off.set("y", str(obj.offset.y))
    osz = etree.SubElement(el, _hp("orgSz"))
    osz.set("width", str(obj.org_sz.width)); osz.set("height", str(obj.org_sz.height))
    csz = etree.SubElement(el, _hp("curSz"))
    csz.set("width", str(obj.cur_sz.width)); csz.set("height", str(obj.cur_sz.height))
    fl = etree.SubElement(el, _hp("flip"))
    fl.set("horizontal", str(obj.flip.horizontal)); fl.set("vertical", str(obj.flip.vertical))
    ri = obj.rotation_info
    r = etree.SubElement(el, _hp("rotationInfo"))
    r.set("angle", str(ri.angle)); r.set("centerX", str(ri.center_x))
    r.set("centerY", str(ri.center_y)); r.set("rotateimage", str(ri.rotate_image))


def _write_rect(run_el, rc, state):
    e = etree.SubElement(run_el, _hp("rect"))
    for k, v in (("id", str(rc.id)), ("zOrder", str(rc.z_order)),
                 ("numberingType", "NONE"), ("textWrap", rc.text_wrap),
                 ("textFlow", rc.text_flow), ("lock", "0"),
                 ("dropcapstyle", "None"), ("href", ""),
                 ("groupLevel", str(rc.group_level)), ("instid", str(rc.instid)),
                 ("ratio", str(rc.ratio))):
        e.set(k, v)
    _write_shape_geom(e, rc)          # offset/orgSz/curSz/flip/rotationInfo
    rend = etree.SubElement(e, _hp("renderingInfo"))
    for tag, m in (("transMatrix", rc.rendering_info.trans),
                   ("scaMatrix", rc.rendering_info.sca),
                   ("rotMatrix", rc.rendering_info.rot),
                   ("scaMatrix", rc.sca2), ("rotMatrix", rc.rot2)):
        me = etree.SubElement(rend, _hc(tag))
        for i in range(1, 7):
            me.set("e%d" % i, getattr(m, "e%d" % i))
    ls = rc.line_shape
    lsh = etree.SubElement(e, _hp("lineShape"))
    for k, v in (("color", ls.color), ("width", str(ls.width)), ("style", ls.style),
                 ("endCap", "FLAT"), ("headStyle", "NORMAL"), ("tailStyle", "NORMAL"),
                 ("headfill", "1"), ("tailfill", "1"), ("headSz", "MEDIUM_MEDIUM"),
                 ("tailSz", "MEDIUM_MEDIUM"), ("outlineStyle", "NORMAL"), ("alpha", "0")):
        lsh.set(k, v)
    sh = etree.SubElement(e, _hp("shadow"))
    for k, v in (("type", "NONE"), ("color", "#000000"), ("offsetX", "0"),
                 ("offsetY", "0"), ("alpha", "0")):
        sh.set(k, v)
    _write_draw_text(e, rc.draw_text, state)


def _write_draw_text(rect_el, dt, state):
    if dt is None:
        return
    if state is None:
        state = {"para_id": 0, "tbl_id": 0}
    dte = etree.SubElement(rect_el, _hp("drawText"))
    dte.set("lastWidth", str(dt.last_width)); dte.set("name", ""); dte.set("editable", "0")
    sl = dt.sub_list
    sle = etree.SubElement(dte, _hp("subList"))
    for k, v in (("id", ""), ("textDirection", "HORIZONTAL"), ("lineWrap", "BREAK"),
                 ("vertAlign", sl.vert_align), ("linkListIDRef", "0"),
                 ("linkListNextIDRef", "0"), ("textWidth", "0"), ("textHeight", "0"),
                 ("hasTextRef", "0"), ("hasNumRef", "0")):
        sle.set(k, v)
    for para in sl.paras:
        _write_paragraph(sle, para, state)


def _write_line(run_el, ln):
    e = etree.SubElement(run_el, _hp("line"))
    for k, v in (("id", str(ln.id)), ("zOrder", str(ln.z_order)),
                 ("numberingType", "PICTURE"), ("textWrap", ln.text_wrap),
                 ("textFlow", ln.text_flow), ("lock", "0"),
                 ("dropcapstyle", "None"), ("href", ""), ("groupLevel", "0"),
                 ("instid", str(ln.instid)), ("isReverseHV", "0")):
        e.set(k, v)
    off = etree.SubElement(e, _hp("offset"))
    off.set("x", str(ln.offset.x)); off.set("y", str(ln.offset.y))
    osz = etree.SubElement(e, _hp("orgSz"))
    osz.set("width", str(ln.org_sz.width)); osz.set("height", str(ln.org_sz.height))
    csz = etree.SubElement(e, _hp("curSz"))
    csz.set("width", str(ln.cur_sz.width)); csz.set("height", str(ln.cur_sz.height))
    fl = etree.SubElement(e, _hp("flip"))
    fl.set("horizontal", str(ln.flip.horizontal))
    fl.set("vertical", str(ln.flip.vertical))
    ri = ln.rotation_info
    r = etree.SubElement(e, _hp("rotationInfo"))
    r.set("angle", str(ri.angle)); r.set("centerX", str(ri.center_x))
    r.set("centerY", str(ri.center_y)); r.set("rotateimage", str(ri.rotate_image))
    rend = etree.SubElement(e, _hp("renderingInfo"))
    for tag, m in (("transMatrix", ln.rendering_info.trans),
                   ("scaMatrix", ln.rendering_info.sca),
                   ("rotMatrix", ln.rendering_info.rot)):
        me = etree.SubElement(rend, _hc(tag))
        for i in range(1, 7):
            me.set("e%d" % i, getattr(m, "e%d" % i))
    lsh = ln.line_shape
    lse = etree.SubElement(e, _hp("lineShape"))
    for k, v in (("color", lsh.color), ("width", str(lsh.width)),
                 ("style", lsh.style), ("endCap", lsh.end_cap),
                 ("headStyle", lsh.head_style), ("tailStyle", lsh.tail_style),
                 ("headfill", str(lsh.head_fill)), ("tailfill", str(lsh.tail_fill)),
                 ("headSz", lsh.head_sz), ("tailSz", lsh.tail_sz),
                 ("outlineStyle", lsh.outline_style), ("alpha", str(lsh.alpha))):
        lse.set(k, v)
    fb = etree.SubElement(e, _hc("fillBrush"))
    wb = etree.SubElement(fb, _hc("winBrush"))
    wb.set("faceColor", ln.win_brush.face_color)
    wb.set("hatchColor", ln.win_brush.hatch_color)
    wb.set("alpha", str(ln.win_brush.alpha))
    sh = etree.SubElement(e, _hp("shadow"))
    sh.set("type", ln.shadow.type); sh.set("color", ln.shadow.color)
    sh.set("offsetX", str(ln.shadow.offset_x)); sh.set("offsetY", str(ln.shadow.offset_y))
    sh.set("alpha", str(ln.shadow.alpha))
    sp = etree.SubElement(e, _hc("startPt"))
    sp.set("x", str(ln.start_pt.x)); sp.set("y", str(ln.start_pt.y))
    ep = etree.SubElement(e, _hc("endPt"))
    ep.set("x", str(ln.end_pt.x)); ep.set("y", str(ln.end_pt.y))
    sz = etree.SubElement(e, _hp("sz"))
    sz.set("width", str(ln.sz.width)); sz.set("widthRelTo", ln.sz.width_rel_to)
    sz.set("height", str(ln.sz.height)); sz.set("heightRelTo", ln.sz.height_rel_to)
    sz.set("protect", str(ln.sz.protect))
    po = ln.pos
    pe = etree.SubElement(e, _hp("pos"))
    for k, v in (("treatAsChar", str(po.treat_as_char)),
                 ("affectLSpacing", str(po.affect_lspacing)),
                 ("flowWithText", str(po.flow_with_text)),
                 ("allowOverlap", str(po.allow_overlap)),
                 ("holdAnchorAndSO", str(po.hold_anchor_and_so)),
                 ("vertRelTo", po.vert_rel_to), ("horzRelTo", po.horz_rel_to),
                 ("vertAlign", po.vert_align), ("horzAlign", po.horz_align),
                 ("vertOffset", str(po.vert_offset)),
                 ("horzOffset", str(po.horz_offset))):
        pe.set(k, v)
    om = etree.SubElement(e, _hp("outMargin"))
    for side in ("left", "right", "top", "bottom"):
        om.set(side, str(getattr(ln.out_margin, side)))


def _write_table(run_el, table, state):
    state["tbl_id"] += 1
    t = etree.SubElement(run_el, _hp("tbl"))
    t.set("id", str(state["tbl_id"]))
    for k, v in (("zOrder", "0"), ("numberingType", "TABLE"),
                 ("textWrap", "TOP_AND_BOTTOM"), ("textFlow", "BOTH_SIDES"),
                 ("lock", "0"), ("dropcapstyle", "None"), ("pageBreak", "NONE"),
                 ("repeatHeader", "1")):
        t.set(k, v)
    t.set("rowCnt", str(table.row_cnt))
    t.set("colCnt", str(table.col_cnt))
    t.set("cellSpacing", str(table.cell_spacing))
    t.set("borderFillIDRef", str(table.border_fill_id))
    t.set("noAdjust", "0")
    sz = etree.SubElement(t, _hp("sz"))
    sz.set("width", str(table.width))
    sz.set("widthRelTo", "ABSOLUTE")
    sz.set("height", str(table.height))
    sz.set("heightRelTo", "ABSOLUTE")
    sz.set("protect", "0")
    pos = etree.SubElement(t, _hp("pos"))
    for k, v in (("treatAsChar", "1"), ("affectLSpacing", "0"),
                 ("flowWithText", "1"), ("allowOverlap", "0"),
                 ("holdAnchorAndSO", "0"), ("vertRelTo", "PARA"),
                 ("horzRelTo", "COLUMN"), ("vertAlign", "TOP"),
                 ("horzAlign", "LEFT")):
        pos.set(k, v)
    for tag in ("outMargin", "inMargin"):
        m = etree.SubElement(t, _hp(tag))
        for side in ("left", "right", "top", "bottom"):
            m.set(side, "141")
    for row in table.rows:
        tr = etree.SubElement(t, _hp("tr"))
        for cell in row.cells:
            _write_cell(tr, cell, state)


def _write_cell(tr_el, cell, state):
    tc = etree.SubElement(tr_el, _hp("tc"))
    tc.set("name", "")
    tc.set("header", "0")
    tc.set("hasMargin", "0")
    tc.set("protect", "0")
    tc.set("editable", "0")
    tc.set("dirty", "0")
    tc.set("borderFillIDRef", str(cell.border_fill_id))
    sub = etree.SubElement(tc, _hp("subList"))
    for k, v in (("id", ""), ("textDirection", "HORIZONTAL"), ("lineWrap", "BREAK"),
                 ("vertAlign", cell.valign), ("linkListIDRef", "0"),
                 ("linkListNextIDRef", "0"), ("textWidth", "0"),
                 ("textHeight", "0"), ("hasTextRef", "0"), ("hasNumRef", "0")):
        sub.set(k, v)
    for para in cell.paras:
        _write_paragraph(sub, para, state)
    ca = etree.SubElement(tc, _hp("cellAddr"))
    ca.set("colAddr", str(cell.col_addr))
    ca.set("rowAddr", str(cell.row_addr))
    cspan = etree.SubElement(tc, _hp("cellSpan"))
    cspan.set("colSpan", str(cell.col_span))
    cspan.set("rowSpan", str(cell.row_span))
    csz = etree.SubElement(tc, _hp("cellSz"))
    csz.set("width", str(cell.width))
    csz.set("height", str(cell.height))
    cm = etree.SubElement(tc, _hp("cellMargin"))
    for side in ("left", "right", "top", "bottom"):
        cm.set(side, "141")


def section_xml(section):
    root = etree.Element(_hs("sec"), nsmap=_NSMAP)
    state = {"tbl_id": 0, "para_id": 0}
    for idx, para in enumerate(section.paras):
        _write_paragraph(root, para, state,
                         sec_pr=(section.sec_pr if idx == 0 else None))
    return XML_DECL + etree.tostring(root, encoding="UTF-8")
