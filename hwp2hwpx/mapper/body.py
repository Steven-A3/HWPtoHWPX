"""Map a whole HwpDocument to an OwpmlDocument."""
from ..owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Text, Metadata, Control, LineSeg,
    PageHiding, Bookmark, NewNum,
)
from ..hwpmodel.model import HwpPageHide, HwpBookmark, HwpNewNumbering
from .fonts import map_fonts
from .char_pr import map_char_shapes
from .para_pr import map_para_shapes
from .border_fill import map_border_fills
from .style import map_styles
from .tab import map_tab_defs
from .bullet import map_bullets
from .section import map_section_def
from .docsettings import map_begin_num, map_compat
from .markpen import apply_markpens


def _map_contents(contents):
    """HwpRun.contents (str | HwpControl) -> OWPML Run.texts (Text | Control)."""
    out = []
    for item in contents:
        if isinstance(item, str):
            out.append(Text(item))
        else:  # HwpControl
            out.append(Control(item.kind))
    return out


def _map_ctrls(ctrls):
    out = []
    for c in ctrls:
        if isinstance(c, HwpPageHide):
            out.append(PageHiding(
                hide_header=c.hide_header, hide_footer=c.hide_footer,
                hide_master_page=c.hide_master_page, hide_border=c.hide_border,
                hide_fill=c.hide_fill, hide_page_num=c.hide_page_num))
        elif isinstance(c, HwpBookmark):
            out.append(Bookmark(name=c.name))
        elif isinstance(c, HwpNewNumbering):
            out.append(NewNum(num=c.num, num_type=c.num_type))
    return out


def _map_line_segs(line_segs):
    return [LineSeg(
        text_pos=ls.text_pos, vert_pos=ls.vert_pos, vert_size=ls.vert_size,
        text_height=ls.text_height, baseline=ls.baseline, spacing=ls.spacing,
        horz_pos=ls.horz_pos, horz_size=ls.horz_size, flags=ls.flags,
    ) for ls in line_segs]


def map_paragraph(hpar, para_id, bin_index=None):
    """Map one HwpParagraph to an OWPML Para. A table run becomes a Run whose
    `table` is set (deferred import breaks the body<->table recursion cycle)."""
    runs = []
    for r in hpar.runs:
        if getattr(r, "table", None) is not None:
            from .table import map_table
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[],
                            table=map_table(r.table, bin_index),
                            ctrls=_map_ctrls(r.ctrls),
                            ctrls_after=_map_ctrls(r.ctrls_after)))
        elif getattr(r, "drawing", None) is not None:
            from .drawing import map_drawing
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[],
                            drawing=map_drawing(r.drawing, bin_index),
                            ctrls=_map_ctrls(r.ctrls),
                            ctrls_after=_map_ctrls(r.ctrls_after)))
        else:
            runs.append(Run(char_pr_id=r.char_shape_id,
                            texts=_map_contents(r.contents),
                            ctrls=_map_ctrls(r.ctrls),
                            ctrls_after=_map_ctrls(r.ctrls_after)))
    if not runs:
        # Hancom always emits at least one <hp:run> per <hp:p>.
        runs = [Run(char_pr_id=0, texts=[])]
    apply_markpens(runs, getattr(hpar, "markpens", []))
    return Para(id=para_id, para_pr_id=hpar.para_shape_id,
                style_id=hpar.style_id, runs=runs,
                line_segs=_map_line_segs(hpar.line_segs))


def map_document(hwp_doc, title="", bin_index=None):
    di = hwp_doc.docinfo
    header = Header(
        fonts_by_lang=map_fonts(di.fonts),
        char_prs=map_char_shapes(di.char_shapes),
        para_prs=map_para_shapes(di.para_shapes),
        border_fills=map_border_fills(di.border_fills),
        styles=map_styles(di.styles),
        tab_defs=map_tab_defs(di.tab_defs),
        bullets=map_bullets(di.bullets),
        begin_num=map_begin_num(di.doc_properties),
        compat=map_compat(di.compat),
    )
    sections = []
    para_id = 0
    for hsec in hwp_doc.sections:
        paras = []
        for hpar in hsec.paragraphs:
            paras.append(map_paragraph(hpar, para_id, bin_index))
            para_id += 1
        sections.append(Section(paras=paras,
                                sec_pr=map_section_def(getattr(hsec, "sec_def", None))))
    si = hwp_doc.summary_info
    if si is not None:
        metadata = Metadata(
            title=si.title or title,
            creator=si.creator,
            subject=si.subject,
            description=si.description,
            last_saved_by=si.last_saved_by,
            created_date=si.created_date,
            modified_date=si.modified_date,
            date=si.date,
            keyword=si.keyword,
        )
    else:
        metadata = Metadata(title=title)
    return OwpmlDocument(header=header, sections=sections, metadata=metadata)
