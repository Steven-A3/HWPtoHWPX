"""The empty <hp:t/> anchor now comes from the run's interleaved contents (a
materialized empty Text("")), not from a writer-side heuristic. These tests
pin the writer's emission of that anchor and of inline objects."""
from lxml import etree

from hwp2hwpx.owpml.section_writer import _write_run
from hwp2hwpx.owpml.model import Run, Text, Table
from hwp2hwpx.constants import NS


def _run_xml(run):
    p_el = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"], "hc": NS["hc"]})
    _write_run(p_el, run, state={"tbl_id": 0, "para_id": 0})
    return etree.tostring(p_el, encoding="unicode")


def test_empty_text_span_emits_self_closing_t():
    xml = _run_xml(Run(char_pr_id=0, texts=[Text("")]))
    assert "<hp:t/>" in xml


def test_table_then_empty_span_emits_tbl_then_anchor():
    xml = _run_xml(Run(char_pr_id=0, texts=[Table(), Text("")]))
    assert xml.index("<hp:tbl") < xml.index("<hp:t/>")


def test_object_without_trailing_empty_span_has_no_anchor_t():
    # a run holding only an object (no empty Text) emits no <hp:t> at all.
    xml = _run_xml(Run(char_pr_id=0, texts=[Table()]))
    assert "<hp:t/>" not in xml and "<hp:t>" not in xml


def test_plain_text_run_emits_single_t():
    xml = _run_xml(Run(char_pr_id=5, texts=[Text("가나다")]))
    assert xml.count("<hp:t>") == 1 and "가나다" in xml


def test_text_then_object_then_empty_span():
    xml = _run_xml(Run(char_pr_id=0, texts=[Text("a"), Table(), Text("")]))
    # <t>a</t> before the tbl, empty <t/> after it
    assert xml.index("<hp:t>a</hp:t>") < xml.index("<hp:tbl")
    assert xml.index("<hp:tbl") < xml.index("<hp:t/>")
