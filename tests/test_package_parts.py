from lxml import etree
from hwp2hwpx.owpml import package_parts as pp
from hwp2hwpx.owpml.model import Metadata, Section, Para, Run, Text
from hwp2hwpx.constants import NS


def _parse(b):
    return etree.fromstring(b)


def test_version_xml_wellformed_and_targets_wordprocessor():
    root = _parse(pp.version_xml())
    assert root.tag == "{%s}HCFVersion" % NS["hv"]
    assert root.get("tagetApplication") == "WORDPROCESSOR"  # sic: Hancom's real attribute spelling


def test_container_lists_content_hpf():
    root = _parse(pp.container_xml())
    fulls = [e.get("full-path") for e in root.iter("{%s}rootfile" % NS["ocf"])]
    assert "Contents/content.hpf" in fulls


def test_content_hpf_has_manifest_items_and_spine():
    root = _parse(pp.content_hpf(Metadata(title="T"), section_count=1))
    ids = [e.get("id") for e in root.iter("{%s}item" % NS["opf"])]
    assert "header" in ids and "section0" in ids


def test_prv_text_extracts_visible_text():
    sec = Section(paras=[Para(id=0, para_pr_id=0,
                              runs=[Run(char_pr_id=0, texts=[Text("가나다")])])])
    assert "가나다" in pp.prv_text([sec]).decode("utf-8")
