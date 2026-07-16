"""Read a .hwp file into an in-memory model, via pyhwp's hwp5proc XML dump."""
import os
import sys
import subprocess
from lxml import etree
from .model import (
    HwpFont, HwpCharShape, HwpParaShape, HwpDocInfo,
    HwpRun, HwpParagraph, HwpSection, HwpDocument,
    HwpBorder, HwpBorderFill, HwpTable, HwpTableRow, HwpTableCell,
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


def _border_fill_id(v):
    """HWP5 borderfill-id is 1-based and equals the OWPML borderFill id we
    emit (definition id = document-order index + 1). Use the raw value; a
    missing/<1 value falls back to the first definition (id 1)."""
    n = _int(v, 0)
    return n if n >= 1 else 1


def _font_group_offsets(id_mappings):
    """Global start index of each language group within the flat FaceName list."""
    offsets = {}
    running = 0
    for lang in _FONT_LANGS:
        offsets[lang] = running
        running += _int(id_mappings.get("%s-fonts" % lang))
    return offsets


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
        ))

    return HwpDocInfo(fonts=fonts, char_shapes=char_shapes,
                      para_shapes=para_shapes,
                      border_fills=_parse_border_fills(id_mappings))


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


def parse_paragraph(para_el):
    """Build one HwpParagraph, walking LineSeg children in reading order:
    Text -> text run; TableControl -> table run; other controls skipped."""
    runs = []
    for child in para_el.findall("LineSeg/*"):
        if child.tag == "Text":
            content = child.text or ""
            if content:
                runs.append(HwpRun(
                    char_shape_id=_int(child.get("charshape-id")),
                    text=content,
                ))
        elif child.tag == "TableControl":
            runs.append(HwpRun(
                char_shape_id=_int(child.get("charshape-id")),
                text="",
                table=_parse_table(child),
            ))
    return HwpParagraph(
        para_shape_id=_int(para_el.get("parashape-id")),
        style_id=_int(para_el.get("style-id")),
        runs=runs,
    )


def _clamp_table_border_fill_ids(sections, border_fill_count):
    """`_border_fill_id` only guards the low end (raw 0/missing -> 1); a raw
    id past the last defined BorderFill would still dangle. Clamp every
    table/cell border_fill_id into [1, border_fill_count] here, once the
    definition count is known, by walking the already-parsed section tree
    (including nested tables inside cell paragraphs)."""
    if border_fill_count <= 0:
        return
    last = border_fill_count  # ids are 1..count

    def _clamp(n):
        if n < 1:
            return 1
        if n > last:
            return last
        return n

    def _walk_table(table):
        table.border_fill_id = _clamp(table.border_fill_id)
        for row in table.table_rows:
            for cell in row.cells:
                cell.border_fill_id = _clamp(cell.border_fill_id)
                _walk_paragraphs(cell.paragraphs)

    def _walk_paragraphs(paragraphs):
        for para in paragraphs:
            for run in para.runs:
                if run.table is not None:
                    _walk_table(run.table)

    for sec in sections:
        _walk_paragraphs(sec.paragraphs)


def read_document(xml_bytes):
    docinfo = read_docinfo(xml_bytes)
    root = etree.fromstring(xml_bytes)
    sections = []
    for sec_el in root.findall(".//SectionDef"):
        paras = []
        for col in sec_el.findall("ColumnSet"):
            for para_el in col.findall("Paragraph"):
                paras.append(parse_paragraph(para_el))
        sections.append(HwpSection(paragraphs=paras))
    if not sections:
        sections = [HwpSection(paragraphs=[])]
    _clamp_table_border_fill_ids(sections, len(docinfo.border_fills))
    return HwpDocument(docinfo=docinfo, sections=sections)
