from hwp2hwpx.mapper.body import map_document
from hwp2hwpx.hwpmodel.model import (
    HwpDocument, HwpDocInfo, HwpFont, HwpCharShape, HwpParaShape,
    HwpSection, HwpParagraph, HwpRun,
)


def _hwp_doc():
    di = HwpDocInfo(
        fonts=[HwpFont(0, "바탕")],
        char_shapes=[HwpCharShape(index=0, base_size=1000)],
        para_shapes=[HwpParaShape(index=0, align="CENTER")],
    )
    sec = HwpSection(paragraphs=[
        HwpParagraph(para_shape_id=0, style_id=5,
                     runs=[HwpRun(char_shape_id=0, text="가나다")])
    ])
    return HwpDocument(docinfo=di, sections=[sec])


def test_map_document_builds_owpml():
    doc = map_document(_hwp_doc(), title="T")
    assert doc.metadata.title == "T"
    assert doc.header.fonts_by_lang["HANGUL"][0].face == "바탕"
    assert len(doc.header.char_prs) == 1
    assert len(doc.header.para_prs) == 1
    para = doc.sections[0].paras[0]
    assert para.para_pr_id == 0
    assert para.style_id == 5
    assert para.runs[0].char_pr_id == 0
    assert para.runs[0].texts[0].content == "가나다"
