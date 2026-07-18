"""Serialize an OWPML Header to Contents/header.xml."""
from lxml import etree
from ..constants import NS, XML_DECL
from .model import BeginNum, CompatDocument

_NSMAP = {k: v for k, v in NS.items()}


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def _hc(tag):
    return "{%s}%s" % (NS["hc"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def _write_margin_and_spacing(parent, pp):
    m = etree.SubElement(parent, _hh("margin"))
    for tag, val in (("intent", pp.intent), ("left", pp.margin_left),
                     ("right", pp.margin_right), ("prev", pp.margin_prev),
                     ("next", pp.margin_next)):
        e = etree.SubElement(m, _hc(tag))
        e.set("value", str(val))
        e.set("unit", "HWPUNIT")
    ls = etree.SubElement(parent, _hh("lineSpacing"))
    ls.set("type", pp.line_spacing_type)
    ls.set("value", str(pp.line_spacing))
    ls.set("unit", "HWPUNIT")


def header_xml(header, sec_cnt=1):
    root = etree.Element(_hh("head"), nsmap=_NSMAP)
    root.set("version", "1.5")
    root.set("secCnt", str(sec_cnt))

    bn = header.begin_num or BeginNum()
    be = etree.SubElement(root, _hh("beginNum"))
    be.set("page", str(bn.page))
    be.set("footnote", str(bn.footnote))
    be.set("endnote", str(bn.endnote))
    be.set("pic", str(bn.pic))
    be.set("tbl", str(bn.tbl))
    be.set("equation", str(bn.equation))

    ref = etree.SubElement(root, _hh("refList"))

    fonts_el = etree.SubElement(ref, _hh("fontfaces"))
    for lang, fonts in header.fonts_by_lang.items():
        ff = etree.SubElement(fonts_el, _hh("fontface"))
        ff.set("lang", lang)
        ff.set("fontCnt", str(len(fonts)))
        for f in fonts:
            fe = etree.SubElement(ff, _hh("font"))
            fe.set("id", str(f.id))
            fe.set("face", f.face)
            fe.set("type", f.type)
            fe.set("isEmbedded", "1" if f.is_embedded else "0")
            if f.type_info is not None:
                ti = f.type_info
                te = etree.SubElement(fe, _hh("typeInfo"))
                te.set("familyType", ti.family_type)
                te.set("weight", str(ti.weight))
                te.set("proportion", str(ti.proportion))
                te.set("contrast", str(ti.contrast))
                te.set("strokeVariation", str(ti.stroke_variation))
                te.set("armStyle", str(ti.arm_style))
                te.set("letterform", str(ti.letterform))
                te.set("midline", str(ti.midline))
                te.set("xHeight", str(ti.x_height))

    bfs_el = etree.SubElement(ref, _hh("borderFills"))
    bfs_el.set("itemCnt", str(len(header.border_fills)))
    for bf in header.border_fills:
        be = etree.SubElement(bfs_el, _hh("borderFill"))
        be.set("id", str(bf.id))
        be.set("threeD", "0")
        be.set("shadow", "0")
        be.set("centerLine", "NONE")
        be.set("breakCellSeparateLine", "0")
        for slash in ("slash", "backSlash"):
            se = etree.SubElement(be, _hh(slash))
            se.set("type", "NONE")
            se.set("Crooked", "0")
            se.set("isCounter", "0")
        by_kind = {b.kind: b for b in bf.borders}
        for kind, tag in (("left", "leftBorder"), ("right", "rightBorder"),
                          ("top", "topBorder"), ("bottom", "bottomBorder"),
                          ("diagonal", "diagonal")):
            b = by_kind.get(kind)
            el = etree.SubElement(be, _hh(tag))
            el.set("type", b.type if b else "NONE")
            el.set("width", b.width if b else "0.1 mm")
            el.set("color", b.color if b else "#000000")
        if bf.gradation is not None:
            g = bf.gradation
            fb = etree.SubElement(be, _hc("fillBrush"))
            ge = etree.SubElement(fb, _hc("gradation"))
            ge.set("type", g.type)
            ge.set("angle", str(g.angle))
            ge.set("centerX", str(g.center_x))
            ge.set("centerY", str(g.center_y))
            ge.set("step", str(g.step))
            ge.set("colorNum", str(len(g.colors)))
            ge.set("stepCenter", str(g.step_center))
            ge.set("alpha", str(g.alpha))
            for color in g.colors:
                etree.SubElement(ge, _hc("color")).set("value", color)
        elif bf.fill_color:
            fb = etree.SubElement(be, _hc("fillBrush"))
            wb = etree.SubElement(fb, _hc("winBrush"))
            wb.set("faceColor", bf.fill_color)
            wb.set("hatchColor", "#FF000000")
            wb.set("alpha", "0")

    cps = etree.SubElement(ref, _hh("charProperties"))
    cps.set("itemCnt", str(len(header.char_prs)))
    _CP_LANGS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")
    for cp in header.char_prs:
        ce = etree.SubElement(cps, _hh("charPr"))
        ce.set("id", str(cp.id))
        ce.set("height", str(cp.height))
        ce.set("textColor", cp.text_color)
        ce.set("shadeColor", cp.shade_color)
        ce.set("useFontSpace", "0")
        ce.set("useKerning", "0")
        ce.set("symMark", "NONE")
        ce.set("borderFillIDRef", str(cp.border_fill_id))

        def _langset(tag, values, default):
            el = etree.SubElement(ce, _hh(tag))
            for lang in _CP_LANGS:
                el.set(lang, str(values.get(lang, default)))

        _langset("fontRef", cp.font_ref, 0)
        _langset("ratio", cp.ratio, 100)
        _langset("spacing", cp.spacing, 0)
        _langset("relSz", cp.rel_sz, 100)
        _langset("offset", cp.offset, 0)

        if cp.italic:
            etree.SubElement(ce, _hh("italic"))
        if cp.bold:
            etree.SubElement(ce, _hh("bold"))

        ul = etree.SubElement(ce, _hh("underline"))
        ul.set("type", cp.underline_type)
        ul.set("shape", cp.underline_shape)
        ul.set("color", cp.underline_color)

        st = etree.SubElement(ce, _hh("strikeout"))
        st.set("shape", cp.strikeout_shape)
        st.set("color", cp.strikeout_color)

        ol = etree.SubElement(ce, _hh("outline"))
        ol.set("type", cp.outline_type)

        sh = etree.SubElement(ce, _hh("shadow"))
        sh.set("type", cp.shadow_type)
        sh.set("color", cp.shadow_color)
        sh.set("offsetX", str(cp.shadow_offset_x))
        sh.set("offsetY", str(cp.shadow_offset_y))

        if cp.superscript:
            etree.SubElement(ce, _hh("supscript"))
        if cp.subscript:
            etree.SubElement(ce, _hh("subscript"))

    tabs_el = etree.SubElement(ref, _hh("tabProperties"))
    if header.tab_defs:
        tabs_el.set("itemCnt", str(len(header.tab_defs)))
        for td in header.tab_defs:
            tpe = etree.SubElement(tabs_el, _hh("tabPr"))
            tpe.set("id", str(td.id))
            tpe.set("autoTabLeft", str(td.auto_tab_left))
            tpe.set("autoTabRight", str(td.auto_tab_right))
            for item in td.tabs:
                sw = etree.SubElement(tpe, _hp("switch"))
                case = etree.SubElement(sw, _hp("case"))
                case.set("{%s}required-namespace" % NS["hp"],
                         "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar")
                ci = etree.SubElement(case, _hh("tabItem"))
                ci.set("pos", str(item.pos // 2))
                ci.set("type", item.type)
                ci.set("leader", item.leader)
                ci.set("unit", "HWPUNIT")
                default = etree.SubElement(sw, _hp("default"))
                di = etree.SubElement(default, _hh("tabItem"))
                di.set("pos", str(item.pos))
                di.set("type", item.type)
                di.set("leader", item.leader)
    else:
        tabs_el.set("itemCnt", "1")
        tab_el = etree.SubElement(tabs_el, _hh("tabPr"))
        tab_el.set("id", "0")
        tab_el.set("autoTabLeft", "0")
        tab_el.set("autoTabRight", "0")

    # <hh:numberings> precedes <hh:bullets> in refList; both sit between
    # tabProperties and paraProperties, and both are omitted entirely when the
    # document defines none.
    if header.numberings:
        nums_el = etree.SubElement(ref, _hh("numberings"))
        nums_el.set("itemCnt", str(len(header.numberings)))
        for nm in header.numberings:
            ne = etree.SubElement(nums_el, _hh("numbering"))
            ne.set("id", str(nm.id))
            ne.set("start", str(nm.start))
            for h in nm.heads:
                ph = etree.SubElement(ne, _hh("paraHead"))
                ph.set("start", "1")
                ph.set("level", str(h.level))
                ph.set("align", h.align)
                ph.set("useInstWidth", str(h.use_inst_width))
                ph.set("autoIndent", str(h.auto_indent))
                ph.set("widthAdjust", str(h.width_adjust))
                ph.set("textOffsetType", "PERCENT")
                ph.set("textOffset", str(h.text_offset))
                ph.set("numFormat", h.num_format)
                ph.set("charPrIDRef", str(h.char_pr_id))
                ph.set("checkable", str(h.checkable))
                if h.text:
                    ph.text = h.text

    # Hancom omits <hh:bullets> entirely when the document defines no bullets
    # (sample 4), rather than emitting an empty itemCnt="0" container.
    if header.bullets:
        bullets_el = etree.SubElement(ref, _hh("bullets"))
        bullets_el.set("itemCnt", str(len(header.bullets)))
        for b in header.bullets:
            be = etree.SubElement(bullets_el, _hh("bullet"))
            be.set("id", str(b.id))
            be.set("char", b.char)
            be.set("useImage", str(b.use_image))
            ph = etree.SubElement(be, _hh("paraHead"))
            ph.set("level", "0")
            ph.set("align", b.align)
            ph.set("useInstWidth", "0")
            ph.set("autoIndent", str(b.auto_indent))
            ph.set("widthAdjust", str(b.width_adjust))
            ph.set("textOffsetType", "PERCENT")
            ph.set("textOffset", str(b.text_offset))
            ph.set("numFormat", "DIGIT")
            ph.set("charPrIDRef", str(b.char_pr_id))
            ph.set("checkable", "0")

    pps = etree.SubElement(ref, _hh("paraProperties"))
    pps.set("itemCnt", str(len(header.para_prs)))
    for pp in header.para_prs:
        pe = etree.SubElement(pps, _hh("paraPr"))
        pe.set("id", str(pp.id))
        pe.set("tabPrIDRef", str(pp.tab_pr_id))
        pe.set("condense", "0")
        pe.set("fontLineHeight", "0")
        pe.set("snapToGrid", "1")
        pe.set("suppressLineNumbers", "0")
        pe.set("checked", "0")
        al = etree.SubElement(pe, _hh("align"))
        al.set("horizontal", pp.align)
        al.set("vertical", "BASELINE")
        hd = etree.SubElement(pe, _hh("heading"))
        hd.set("type", pp.heading_type)
        hd.set("idRef", "0")
        hd.set("level", str(pp.heading_level))
        bs = etree.SubElement(pe, _hh("breakSetting"))
        for k, v in (("breakLatinWord", "KEEP_WORD"),
                     ("breakNonLatinWord", "BREAK_WORD"), ("widowOrphan", "0"),
                     ("keepWithNext", "0"), ("keepLines", "0"),
                     ("pageBreakBefore", "0"), ("lineWrap", "BREAK")):
            bs.set(k, v)
        aus = etree.SubElement(pe, _hh("autoSpacing"))
        aus.set("eAsianEng", "0")
        aus.set("eAsianNum", "0")
        sw = etree.SubElement(pe, _hp("switch"))
        case = etree.SubElement(sw, _hp("case"))
        case.set("{%s}required-namespace" % NS["hp"],
                 "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar")
        _write_margin_and_spacing(case, pp)
        default = etree.SubElement(sw, _hp("default"))
        _write_margin_and_spacing(default, pp)
        bd = etree.SubElement(pe, _hh("border"))
        bd.set("borderFillIDRef", str(pp.border_fill_id))
        for k in ("offsetLeft", "offsetRight", "offsetTop", "offsetBottom"):
            bd.set(k, "0")
        bd.set("connect", "0")
        bd.set("ignoreMargin", "0")

    styles_el = etree.SubElement(ref, _hh("styles"))
    if header.styles:
        styles_el.set("itemCnt", str(len(header.styles)))
        for s in header.styles:
            se = etree.SubElement(styles_el, _hh("style"))
            se.set("id", str(s.id))
            se.set("type", s.type)
            se.set("name", s.name)
            se.set("engName", s.eng_name)
            se.set("paraPrIDRef", str(s.para_pr_id))
            se.set("charPrIDRef", str(s.char_pr_id))
            se.set("nextStyleIDRef", str(s.next_style_id))
            se.set("langID", str(s.lang_id))
            se.set("lockForm", s.lock_form)
    else:
        # No styles in the document: emit a single default so every
        # paragraph's styleIDRef="0" resolves instead of dangling.
        styles_el.set("itemCnt", "1")
        style_el = etree.SubElement(styles_el, _hh("style"))
        style_el.set("id", "0")

    compat = header.compat or CompatDocument()
    cd = etree.SubElement(root, _hh("compatibleDocument"))
    cd.set("targetProgram", compat.target_program)
    etree.SubElement(cd, _hh("layoutCompatibility"))
    do = etree.SubElement(root, _hh("docOption"))
    li = etree.SubElement(do, _hh("linkinfo"))
    li.set("path", "")
    li.set("pageInherit", "1")
    li.set("footnoteInherit", "0")
    tc = etree.SubElement(root, _hh("trackchageConfig"))
    tc.set("flags", "56")

    return XML_DECL + etree.tostring(root, encoding="UTF-8")
