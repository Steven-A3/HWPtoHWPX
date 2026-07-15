"""Serialize an OWPML Header to Contents/header.xml."""
from lxml import etree
from ..constants import NS, XML_DECL

_NSMAP = {k: v for k, v in NS.items()}


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


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

    cps = etree.SubElement(ref, _hh("charProperties"))
    cps.set("itemCnt", str(len(header.char_prs)))
    for cp in header.char_prs:
        ce = etree.SubElement(cps, _hh("charPr"))
        ce.set("id", str(cp.id))
        ce.set("height", str(cp.height))
        ce.set("textColor", cp.text_color)
        fr = etree.SubElement(ce, _hh("fontRef"))
        for lang in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user"):
            fr.set(lang, str(cp.font_ref_id))
        if cp.bold:
            etree.SubElement(ce, _hh("bold"))
        if cp.italic:
            etree.SubElement(ce, _hh("italic"))

    pps = etree.SubElement(ref, _hh("paraProperties"))
    pps.set("itemCnt", str(len(header.para_prs)))
    for pp in header.para_prs:
        pe = etree.SubElement(pps, _hh("paraPr"))
        pe.set("id", str(pp.id))
        al = etree.SubElement(pe, _hh("align"))
        al.set("horizontal", pp.align)
        al.set("vertical", "BASELINE")

    # Real style mapping is a follow-up milestone; for now emit a single
    # default style (id 0) so every paragraph's styleIDRef="0" resolves
    # to something instead of dangling.
    styles_el = etree.SubElement(ref, _hh("styles"))
    styles_el.set("itemCnt", "1")
    style_el = etree.SubElement(styles_el, _hh("style"))
    style_el.set("id", "0")

    return XML_DECL + etree.tostring(root, encoding="UTF-8")
