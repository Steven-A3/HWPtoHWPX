from lxml import etree
from hwp2hwpx.constants import NS
from hwp2hwpx.owpml.model import Run, Text, PageHiding
from hwp2hwpx.owpml.section_writer import _write_run


def _run_el(run):
    p = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"], "hc": NS["hc"]})
    _write_run(p, run, state=None)
    return p[0]


def _localnames(el):
    return [etree.QName(c).localname for c in el]


def test_pagehiding_emits_ctrl_before_t():
    run = Run(char_pr_id=48, texts=[Text("hi")],
              ctrls=[PageHiding(hide_page_num=1)])
    r = _run_el(run)
    assert _localnames(r) == ["ctrl", "t"]          # ctrl before t
    ph = r.find("{%s}ctrl/{%s}pageHiding" % (NS["hp"], NS["hp"]))
    assert ph is not None
    assert ph.get("hidePageNum") == "1"
    assert ph.get("hideHeader") == "0"


def test_two_pagehidings_emit_two_ctrls():
    run = Run(char_pr_id=48, texts=[Text("hi")],
              ctrls=[PageHiding(hide_page_num=1), PageHiding(hide_page_num=1)])
    r = _run_el(run)
    assert _localnames(r) == ["ctrl", "ctrl", "t"]


def test_no_ctrls_unchanged():
    run = Run(char_pr_id=5, texts=[Text("hi")])
    r = _run_el(run)
    assert _localnames(r) == ["t"]
