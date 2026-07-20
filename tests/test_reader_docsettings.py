import pytest

from hwp2hwpx.hwpmodel.reader import read_docinfo

from tests.samplepaths import fixture3

FIXTURE = fixture3()


def _di():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read())


def test_doc_properties_parsed():
    dp = _di().doc_properties
    assert dp is not None
    assert dp.page_start == 1 and dp.footnote_start == 1 and dp.endnote_start == 1
    assert dp.pic_start == 1 and dp.tbl_start == 1 and dp.equation_start == 1


def test_compat_parsed():
    c = _di().compat
    assert c is not None and c.target == 0


@pytest.mark.sample_free
def test_doc_properties_distinct_values_no_field_swap():
    # fixture is all 1s, so it can't catch a swapped math->equation / picture->pic
    # mapping. Parse a synthetic record with distinct startnums to pin the mapping.
    from lxml import etree
    from hwp2hwpx.hwpmodel.reader import _parse_doc_properties
    root = etree.fromstring(
        '<DocInfo><DocumentProperties page-startnum="2" footnote-startnum="3"'
        ' endnote-startnum="4" picture-startnum="5" table-startnum="6"'
        ' math-startnum="7"/></DocInfo>')
    dp = _parse_doc_properties(root)
    assert (dp.page_start, dp.footnote_start, dp.endnote_start,
            dp.pic_start, dp.tbl_start, dp.equation_start) == (2, 3, 4, 5, 6, 7)
