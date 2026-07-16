from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


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
