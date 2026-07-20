from lxml import etree
from hwp2hwpx.constants import NS
from hwp2hwpx.owpml.model import Para, Run, Text, MarkpenBegin, MarkpenEnd
from hwp2hwpx.owpml.section_writer import _write_run


def _run_xml(run):
    p = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"], "hc": NS["hc"]})
    _write_run(p, run, state=None)
    return etree.tostring(p, encoding="unicode")


def test_markpen_markers_emit_inside_t_with_tail_text():
    run = Run(char_pr_id=96, texts=[
        Text("before, "), MarkpenBegin(color="#FFFFFF"),
        Text("highlighted"), MarkpenEnd(),
    ])
    xml = _run_xml(run)
    assert '<hp:markpenBegin color="#FFFFFF"/>' in xml
    assert '<hp:markpenEnd/>' in xml
    # text before the begin marker stays on hp:t; text after begin is its tail
    assert "before, <hp:markpenBegin" in xml
    assert 'color="#FFFFFF"/>highlighted<hp:markpenEnd/>' in xml
