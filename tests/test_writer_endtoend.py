import zipfile
from lxml import etree
from hwp2hwpx.owpml.writer import write_hwpx
from hwp2hwpx.owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Text, Font, CharPr, ParaPr, Metadata,
)


def _doc():
    header = Header(fonts_by_lang={"HANGUL": [Font(id=0, face="바탕")]},
                    char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)])
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[Text("가나다")])])
    return OwpmlDocument(header=header, sections=[Section(paras=[para])],
                         metadata=Metadata(title="T"))


def test_full_package_structure(tmp_path):
    out = tmp_path / "out.hwpx"
    write_hwpx(_doc(), str(out))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names[0] == "mimetype"
        for required in ["version.xml", "settings.xml", "Contents/header.xml",
                         "Contents/section0.xml", "Contents/content.hpf",
                         "META-INF/container.xml", "META-INF/manifest.xml",
                         "Preview/PrvText.txt"]:
            assert required in names, required
        # every XML part is well-formed
        for n in names:
            if n.endswith(".xml") or n.endswith(".hpf"):
                etree.fromstring(z.read(n))
        assert "가나다" in z.read("Preview/PrvText.txt").decode("utf-8")


def test_header_sec_cnt_matches_section_count(tmp_path):
    """write_hwpx must thread the real section count into header.xml's
    secCnt attribute rather than hardcoding 1."""
    out = tmp_path / "out.hwpx"
    doc = _doc()
    doc.sections.append(Section(paras=[
        Para(id=1, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[Text("라마바")])]),
    ]))
    write_hwpx(doc, str(out))
    with zipfile.ZipFile(out) as z:
        assert "Contents/section1.xml" in z.namelist()
        root = etree.fromstring(z.read("Contents/header.xml"))
        assert root.get("secCnt") == "2"


def test_prv_image_emitted_when_present(tmp_path):
    out = tmp_path / "out.hwpx"
    doc = _doc()
    doc.prv_image = b"\x89PNG\r\n\x1a\npayload"
    write_hwpx(doc, str(out))
    with zipfile.ZipFile(out) as z:
        assert "Preview/PrvImage.png" in z.namelist()
        assert z.read("Preview/PrvImage.png") == b"\x89PNG\r\n\x1a\npayload"


def test_prv_image_absent_when_none(tmp_path):
    out = tmp_path / "out.hwpx"
    doc = _doc()  # prv_image defaults to None
    write_hwpx(doc, str(out))
    with zipfile.ZipFile(out) as z:
        assert "Preview/PrvImage.png" not in z.namelist()
