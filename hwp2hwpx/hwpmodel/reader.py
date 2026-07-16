"""Read a .hwp file into an in-memory model, via pyhwp's hwp5proc XML dump."""
import os
import sys
import subprocess
from lxml import etree
from .model import (
    HwpFont, HwpCharShape, HwpParaShape, HwpDocInfo,
    HwpRun, HwpParagraph, HwpSection, HwpDocument,
    HwpBorder, HwpBorderFill, HwpTable, HwpTableRow, HwpTableCell,
    HwpStyle, HwpTab, HwpTabDef,
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
                      tab_defs=_parse_tab_defs(id_mappings))


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
    border_fill_count = len(docinfo.border_fills)
    _clamp_table_border_fill_ids(sections, border_fill_count)
    _clamp_para_shape_border_fill_ids(docinfo.para_shapes, border_fill_count)
    _clamp_style_refs(docinfo.styles, len(docinfo.char_shapes),
                      len(docinfo.para_shapes))
    _clamp_paragraph_style_ids(sections, len(docinfo.styles))
    _clamp_para_shape_tab_def_ids(docinfo.para_shapes, len(docinfo.tab_defs))
    return HwpDocument(docinfo=docinfo, sections=sections)
