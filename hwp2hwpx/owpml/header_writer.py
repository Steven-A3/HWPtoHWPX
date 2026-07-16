"""Serialize an OWPML Header to Contents/header.xml."""
from lxml import etree
from ..constants import NS, XML_DECL

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
        if bf.fill_color:
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

    tabs_el = etree.SubElement(ref, _hh("tabProperties"))
    tabs_el.set("itemCnt", "1")
    tab_el = etree.SubElement(tabs_el, _hh("tabPr"))
    tab_el.set("id", "0")
    tab_el.set("autoTabLeft", "0")
    tab_el.set("autoTabRight", "0")

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

    # Real style mapping is a follow-up milestone; for now emit a single
    # default style (id 0) so every paragraph's styleIDRef="0" resolves
    # to something instead of dangling.
    styles_el = etree.SubElement(ref, _hh("styles"))
    styles_el.set("itemCnt", "1")
    style_el = etree.SubElement(styles_el, _hh("style"))
    style_el.set("id", "0")

    return XML_DECL + etree.tostring(root, encoding="UTF-8")
