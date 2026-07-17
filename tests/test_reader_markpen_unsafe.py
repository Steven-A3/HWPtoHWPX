"""Reader-side guard for markpen char-offset safety.

HWP range-tag positions index the raw paragraph WCHAR stream, where TAB and
extended controls (field/bookmark/newNum/etc.) occupy 8 stream positions (or
are dropped entirely), and non-BMP text characters occupy two
UTF-16 code units. The mapper (hwp2hwpx/mapper/markpen.py) counts every
Control as width 1 and text with Python len() (code points), so it cannot
reproduce the HWP offset basis for such paragraphs. The reader flags these
paragraphs `markpen_unsafe=True` so attach_range_tags can skip them rather
than risk mis-assigning a marker (fail-safe, per the milestone contract)."""
from lxml import etree
from hwp2hwpx.hwpmodel.model import HwpRangeTag
from hwp2hwpx.hwpmodel.reader import parse_paragraph
from hwp2hwpx.hwpmodel import rangetags
from hwp2hwpx.hwpmodel.rangetags import attach_range_tags


def _para(inner):
    return etree.fromstring(
        '<Paragraph parashape-id="0" style-id="0"><LineSeg>' + inner +
        '</LineSeg></Paragraph>')


def test_pure_text_paragraph_is_safe():
    para = _para('<Text charshape-id="0">hello world</Text>'
                 '<ControlChar char="&#13;" charshape-id="0" code="13" '
                 'kind="CHAR" name="PARAGRAPH_BREAK"/>')
    p = parse_paragraph(para)
    assert p.markpen_unsafe is False


def test_tab_control_marks_paragraph_unsafe():
    para = _para('<Text charshape-id="0">ab</Text>'
                 '<ControlChar char="&#9;" charshape-id="0" code="9" '
                 'kind="CHAR" name="TAB"/>'
                 '<Text charshape-id="0">cd</Text>')
    p = parse_paragraph(para)
    assert p.markpen_unsafe is True


def test_title_mark_control_is_safe_width_one():
    # The real TITLE_MARK in the samples is code=8 kind=INLINE -- a single
    # WCHAR -- and the reader maps it to a width-1 titleMark control, so the
    # paragraph's char-offset basis stays reproducible (markpen-safe).
    para = _para('<ControlChar char="?" charshape-id="0" code="8" '
                 'kind="INLINE" name="TITLE_MARK"/>'
                 '<Text charshape-id="0">title</Text>')
    p = parse_paragraph(para)
    assert p.markpen_unsafe is False
    assert p.runs[0].contents[0].kind == "titleMark"


def test_non_bmp_text_marks_paragraph_unsafe():
    # U+1F600 (an astral char) is one Python code point but two UTF-16 code
    # units in the HWP WCHAR stream -- the mapper's len()-based accounting
    # can't reproduce that.
    para = _para('<Text charshape-id="0">a\U0001F600b</Text>')
    p = parse_paragraph(para)
    assert p.markpen_unsafe is True


def test_attach_skips_paragraph_flagged_unsafe(monkeypatch):
    para = _para('<Text charshape-id="0">ab</Text>'
                 '<ControlChar char="&#9;" charshape-id="0" code="9" '
                 'kind="CHAR" name="TAB"/>'
                 '<Text charshape-id="0">cd</Text>')
    p = parse_paragraph(para)
    assert p.markpen_unsafe is True

    class _FakeSection:
        pass

    class _FakeDoc:
        pass

    sec = _FakeSection()
    sec.paragraphs = [p]
    doc = _FakeDoc()
    doc.sections = [sec]

    # A bucket that targets this paragraph's index with a count that
    # satisfies the per-section equality guard.
    fake_buckets = {0: [HwpRangeTag(start=0, end=1, color="#FFFFFF")]}
    monkeypatch.setattr(
        rangetags, "extract_markpens", lambda path: [(fake_buckets, 1)])

    attach_range_tags("irrelevant.hwp", doc)
    assert p.markpens == []
