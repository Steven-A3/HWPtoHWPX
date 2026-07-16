from hwp2hwpx.hwpmodel.reader import read_docinfo, read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _bytes():
    with open(FIXTURE, "rb") as f:
        return f.read()


def test_tab_defs_parsed():
    di = read_docinfo(_bytes())
    assert len(di.tab_defs) == 7
    assert [len(td.tabs) for td in di.tab_defs] == [0, 31, 2, 39, 1, 33, 0]
    assert di.tab_defs[6].auto_tab_left == 1


def test_tab_values():
    di = read_docinfo(_bytes())
    # TabDef 2 has 2 tabs: pos 3216 (left, fill 0) and 37296 (left, fill 3)
    td2 = di.tab_defs[2]
    assert td2.tabs[0].pos == 3216
    assert td2.tabs[0].kind == "left"
    assert td2.tabs[0].fill_type == 0
    assert td2.tabs[1].pos == 37296
    assert td2.tabs[1].fill_type == 3


def test_parashape_tab_def_id_parsed_and_in_range():
    di = read_docinfo(_bytes())
    n = len(di.tab_defs)
    ids = {ps.tab_def_id for ps in di.para_shapes}
    assert ids == {0, 1, 2, 3, 4, 5, 6}
    assert all(0 <= ps.tab_def_id < n for ps in di.para_shapes)
