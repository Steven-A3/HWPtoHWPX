"""Read a .hwp file into an in-memory model, via pyhwp's hwp5proc XML dump."""
import os
import sys
import subprocess
from lxml import etree
from .model import (
    HwpFont, HwpCharShape, HwpParaShape, HwpDocInfo,
    HwpRun, HwpParagraph, HwpSection, HwpDocument,
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


def _font_group_offsets(id_mappings):
    """Global start index of each language group within the flat FaceName list."""
    offsets = {}
    running = 0
    for lang in _FONT_LANGS:
        offsets[lang] = running
        running += _int(id_mappings.get("%s-fonts" % lang))
    return offsets


def read_docinfo(xml_bytes):
    root = etree.fromstring(xml_bytes)
    id_mappings = root.find(".//IdMappings")
    if id_mappings is None:
        return HwpDocInfo()
    offsets = _font_group_offsets(id_mappings)

    fonts = [HwpFont(index=i, name=el.get("name") or "")
             for i, el in enumerate(id_mappings.findall("FaceName"))]

    char_shapes = []
    for i, el in enumerate(id_mappings.findall("CharShape")):
        ff = el.find("FontFace")
        ko_local = _int(ff.get("ko")) if ff is not None else 0
        char_shapes.append(HwpCharShape(
            index=i,
            base_size=_int(el.get("basesize"), 1000),
            text_color=el.get("text-color") or "#000000",
            font_id=offsets.get("ko", 0) + ko_local,
            bold=el.get("bold") == "1",
            italic=el.get("italic") == "1",
        ))

    para_shapes = []
    for i, el in enumerate(id_mappings.findall("ParaShape")):
        raw = (el.get("align") or "left").lower()
        para_shapes.append(HwpParaShape(index=i, align=_ALIGN_MAP.get(raw, "LEFT")))

    return HwpDocInfo(fonts=fonts, char_shapes=char_shapes, para_shapes=para_shapes)


def _paragraph_runs(para_el):
    """One run per <Text> directly under the paragraph's LineSegs (skips
    ControlChars and any table-cell text nested deeper)."""
    runs = []
    for text_el in para_el.findall("LineSeg/Text"):
        content = text_el.text or ""
        if content:
            runs.append(HwpRun(
                char_shape_id=_int(text_el.get("charshape-id")),
                text=content,
            ))
    return runs


def read_document(xml_bytes):
    docinfo = read_docinfo(xml_bytes)
    root = etree.fromstring(xml_bytes)
    sections = []
    for sec_el in root.findall(".//SectionDef"):
        paras = []
        for col in sec_el.findall("ColumnSet"):
            for para_el in col.findall("Paragraph"):
                paras.append(HwpParagraph(
                    para_shape_id=_int(para_el.get("parashape-id")),
                    style_id=_int(para_el.get("style-id")),
                    runs=_paragraph_runs(para_el),
                ))
        sections.append(HwpSection(paragraphs=paras))
    if not sections:
        sections = [HwpSection(paragraphs=[])]
    return HwpDocument(docinfo=docinfo, sections=sections)
