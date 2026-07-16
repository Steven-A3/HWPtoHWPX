"""Map a whole HwpDocument to an OwpmlDocument."""
from ..owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Text, Metadata,
)
from .fonts import map_fonts
from .char_pr import map_char_shapes
from .para_pr import map_para_shapes
from .border_fill import map_border_fills
from .style import map_styles


def map_paragraph(hpar, para_id):
    """Map one HwpParagraph to an OWPML Para. A table run becomes a Run whose
    `table` is set (deferred import breaks the body<->table recursion cycle)."""
    runs = []
    for r in hpar.runs:
        if getattr(r, "table", None) is not None:
            from .table import map_table
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[],
                            table=map_table(r.table)))
        else:
            runs.append(Run(char_pr_id=r.char_shape_id, texts=[Text(r.text)]))
    if not runs:
        # Hancom always emits at least one <hp:run> per <hp:p>.
        runs = [Run(char_pr_id=0, texts=[])]
    return Para(id=para_id, para_pr_id=hpar.para_shape_id,
                style_id=hpar.style_id, runs=runs)


def map_document(hwp_doc, title=""):
    di = hwp_doc.docinfo
    header = Header(
        fonts_by_lang=map_fonts(di.fonts),
        char_prs=map_char_shapes(di.char_shapes),
        para_prs=map_para_shapes(di.para_shapes),
        border_fills=map_border_fills(di.border_fills),
        styles=map_styles(di.styles),
    )
    sections = []
    para_id = 0
    for hsec in hwp_doc.sections:
        paras = []
        for hpar in hsec.paragraphs:
            paras.append(map_paragraph(hpar, para_id))
            para_id += 1
        sections.append(Section(paras=paras))
    return OwpmlDocument(header=header, sections=sections,
                         metadata=Metadata(title=title))
