"""Inline controls milestone: titleMark (inline, in <hp:t>), bookmark
(trailing <hp:ctrl> after text), newNum (leading <hp:ctrl> before an object)."""
import glob
from lxml import etree

from hwp2hwpx.constants import NS
from hwp2hwpx.hwpmodel.reader import parse_paragraph
from hwp2hwpx.hwpmodel.model import (
    HwpParagraph, HwpRun, HwpBookmark, HwpNewNumbering,
)
from hwp2hwpx.owpml.model import Bookmark, NewNum, Control, Text
from hwp2hwpx.mapper.body import map_paragraph, _map_ctrls
from hwp2hwpx.owpml.section_writer import _write_run
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _para(inner):
    return etree.fromstring(
        '<Paragraph parashape-id="0" style-id="0"><LineSeg>' + inner +
        '</LineSeg></Paragraph>')


# ---- reader ---------------------------------------------------------------

def test_reader_bookmark_trails_preceding_text_run():
    para = _para('<Text charshape-id="5">hi</Text>'
                 '<BookmarkControl chid="bokm">'
                 '<BookmarkControlData name="bm1"/></BookmarkControl>'
                 '<Text charshape-id="6">bye</Text>')
    p = parse_paragraph(para)
    assert p.runs[0].char_shape_id == 5
    assert p.runs[0].ctrls_after == [HwpBookmark(name="bm1")]
    assert p.runs[0].ctrls == []
    assert p.runs[1].char_shape_id == 6  # text after the bookmark, separate run


def test_reader_newnum_leads_following_table_run():
    para = _para('<NewNumbering chid="nwno" kind="page" number="1"/>'
                 '<TableControl charshape-id="3">'
                 '<TableBody/></TableControl>')
    p = parse_paragraph(para)
    assert p.runs[0].table is not None
    assert p.runs[0].ctrls == [HwpNewNumbering(num=1, num_type="PAGE")]
    assert p.runs[0].ctrls_after == []


def test_reader_titlemark_is_inline_content():
    para = _para('<ControlChar char="?" charshape-id="0" code="8" '
                 'kind="INLINE" name="TITLE_MARK"/>'
                 '<Text charshape-id="0">t</Text>')
    p = parse_paragraph(para)
    assert p.runs[0].contents[0].kind == "titleMark"
    assert p.markpen_unsafe is False


def test_reader_newnum_default_and_kind_mapping():
    para = _para('<NewNumbering chid="nwno" kind="table" number="7"/>'
                 '<Text charshape-id="0">x</Text>')
    p = parse_paragraph(para)
    assert p.runs[0].ctrls == [HwpNewNumbering(num=7, num_type="TABLE")]


# ---- mapper ---------------------------------------------------------------

def test_mapper_maps_bookmark_and_newnum():
    out = _map_ctrls([HwpBookmark(name="b"), HwpNewNumbering(num=2, num_type="PAGE")])
    assert out == [Bookmark(name="b"), NewNum(num=2, num_type="PAGE")]


def test_mapper_passes_ctrls_after_through():
    hpar = HwpParagraph(para_shape_id=0,
                        runs=[HwpRun(char_shape_id=5, contents=["hi"],
                                     ctrls_after=[HwpBookmark(name="b")])])
    para = map_paragraph(hpar, 0)
    assert para.runs[0].ctrls_after == [Bookmark(name="b")]


# ---- writer ---------------------------------------------------------------

def _run_xml(run):
    p_el = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"]})
    _write_run(p_el, run, state=None)
    return etree.tostring(p_el, encoding="unicode")


def test_writer_bookmark_after_text():
    from hwp2hwpx.owpml.model import Run
    xml = _run_xml(Run(char_pr_id=5, texts=[Text("hi")],
                       ctrls_after=[Bookmark(name="bm1")]))
    assert '<hp:t>hi</hp:t><hp:ctrl><hp:bookmark name="bm1"/></hp:ctrl>' in xml


def test_writer_newnum_before_no_text():
    from hwp2hwpx.owpml.model import Run
    xml = _run_xml(Run(char_pr_id=0, texts=[],
                       ctrls=[NewNum(num=1, num_type="PAGE")]))
    assert '<hp:ctrl><hp:newNum num="1" numType="PAGE"/></hp:ctrl>' in xml


def test_writer_titlemark_inline_with_ignore():
    from hwp2hwpx.owpml.model import Run
    xml = _run_xml(Run(char_pr_id=0, texts=[Control("titleMark"), Text("x")]))
    assert '<hp:t><hp:titleMark ignore="1"/>x</hp:t>' in xml


# ---- end-to-end fidelity --------------------------------------------------

def _score(prefix, tmp_path):
    hwp = glob.glob(prefix + "*.hwp")[0]
    ref = glob.glob(prefix + "*.hwpx")[0]
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return score_part(unzip_parts(str(out))["Contents/section0.xml"],
                      unzip_parts(ref)["Contents/section0.xml"])


def test_sample3_bookmark_and_newnum_present(tmp_path):
    s = _score("samples/3.", tmp_path)
    assert s["missing"].get("bookmark", 0) == 0
    assert s["missing"].get("newNum", 0) == 0
    assert s["missing"].get("ctrl", 0) == 0


def test_sample4_titlemark_present(tmp_path):
    s = _score("samples/4.", tmp_path)
    assert s["missing"].get("titleMark", 0) == 0


def test_both_sections_reach_full_match(tmp_path):
    assert _score("samples/3.", tmp_path)["match"] == 1.0
    assert _score("samples/4.", tmp_path)["match"] == 1.0
