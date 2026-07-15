from hwp2hwpx.owpml.model import (
    Font, CharPr, ParaPr, Text, Run, Para, Header, Section, Metadata, OwpmlDocument,
)


def test_build_minimal_document():
    header = Header(
        fonts_by_lang={"HANGUL": [Font(id=0, face="바탕")]},
        char_prs=[CharPr(id=0)],
        para_prs=[ParaPr(id=0, align="CENTER")],
    )
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[Text("안녕")])])
    doc = OwpmlDocument(header=header, sections=[Section(paras=[para])],
                        metadata=Metadata(title="t"))
    assert doc.sections[0].paras[0].runs[0].texts[0].content == "안녕"
    assert doc.header.para_prs[0].align == "CENTER"
    assert doc.header.fonts_by_lang["HANGUL"][0].face == "바탕"
