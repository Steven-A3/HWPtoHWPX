"""Serialize an OWPML Section to Contents/sectionN.xml."""
from lxml import etree
from ..constants import NS, XML_DECL

_NSMAP = {k: v for k, v in NS.items()}


def _hs(tag):
    return "{%s}%s" % (NS["hs"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def section_xml(section):
    root = etree.Element(_hs("sec"), nsmap=_NSMAP)
    for para in section.paras:
        p = etree.SubElement(root, _hp("p"))
        p.set("id", str(para.id))
        p.set("paraPrIDRef", str(para.para_pr_id))
        p.set("styleIDRef", str(para.style_id))
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")
        for run in para.runs:
            r = etree.SubElement(p, _hp("run"))
            r.set("charPrIDRef", str(run.char_pr_id))
            for t in run.texts:
                te = etree.SubElement(r, _hp("t"))
                te.text = t.content
    return XML_DECL + etree.tostring(root, encoding="UTF-8")
