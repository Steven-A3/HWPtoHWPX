import zipfile
from lxml import etree
from hwp2hwpx.convert import convert
from hwp2hwpx.constants import NS

SAMPLE = "samples/3.과업지시서_070.hwp"


def _hp(t):
    return "{%s}%s" % (NS["hp"], t)


def _hh(t):
    return "{%s}%s" % (NS["hh"], t)


def _convert(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE, str(out))
    with zipfile.ZipFile(out) as z:
        return (etree.fromstring(z.read("Contents/section0.xml")),
                etree.fromstring(z.read("Contents/header.xml")))


def test_tables_and_cells_present(tmp_path):
    sec, _ = _convert(tmp_path)
    assert len(sec.findall(".//" + _hp("tbl"))) == 33
    assert len(sec.findall(".//" + _hp("tc"))) > 300      # ~353 cells


def test_cell_text_recovered(tmp_path):
    sec, _ = _convert(tmp_path)
    # some cell subList contains real text
    texts = [t.text or "" for tc in sec.iter(_hp("tc")) for t in tc.iter(_hp("t"))]
    assert any(s.strip() for s in texts)


def test_no_dangling_borderfill_ref(tmp_path):
    sec, head = _convert(tmp_path)
    defined = {bf.get("id") for bf in head.iter(_hh("borderFill"))}
    refs = {e.get("borderFillIDRef") for e in sec.iter()
            if e.get("borderFillIDRef") is not None}
    assert refs and refs <= defined       # every ref resolves to a defined borderFill


def test_section_is_wellformed_and_tbl_inside_run(tmp_path):
    sec, _ = _convert(tmp_path)
    tbl = sec.find(".//" + _hp("tbl"))
    assert tbl.getparent().tag == _hp("run")
