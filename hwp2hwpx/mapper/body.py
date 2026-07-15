"""Map a whole HwpDocument to an OwpmlDocument."""
from ..owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Text, Metadata,
)
from .fonts import map_fonts
from .char_pr import map_char_shapes
from .para_pr import map_para_shapes


def map_document(hwp_doc, title=""):
    di = hwp_doc.docinfo
    header = Header(
        fonts_by_lang=map_fonts(di.fonts),
        char_prs=map_char_shapes(di.char_shapes),
        para_prs=map_para_shapes(di.para_shapes),
    )
    sections = []
    para_id = 0
    for hsec in hwp_doc.sections:
        paras = []
        for hpar in hsec.paragraphs:
            runs = [Run(char_pr_id=r.char_shape_id, texts=[Text(r.text)])
                    for r in hpar.runs]
            paras.append(Para(id=para_id, para_pr_id=hpar.para_shape_id,
                              style_id=hpar.style_id, runs=runs))
            para_id += 1
        sections.append(Section(paras=paras))
    return OwpmlDocument(header=header, sections=sections,
                         metadata=Metadata(title=title))
