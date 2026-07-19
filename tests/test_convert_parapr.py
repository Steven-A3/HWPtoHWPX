import zipfile
from lxml import etree
from hwp2hwpx.convert import convert
from hwp2hwpx.constants import NS
from tests.samplepaths import S3

SAMPLE = S3


def _hh(t):
    return "{%s}%s" % (NS["hh"], t)


def _hp(t):
    return "{%s}%s" % (NS["hp"], t)


def _convert(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE, str(out))
    with zipfile.ZipFile(out) as z:
        return (etree.fromstring(z.read("Contents/header.xml")),
                etree.fromstring(z.read("Contents/section0.xml")))


def test_parapr_has_margin_switch_linespacing_border(tmp_path):
    head, _ = _convert(tmp_path)
    pps = head.findall(".//" + _hh("paraPr"))
    assert len(pps) == 126
    # every paraPr carries the full structure
    for pp in pps:
        assert pp.find(_hp("switch")) is not None
        assert pp.find(_hh("border")) is not None
    # a known non-zero margin (paraShape 11: intent -2000, left 1000)
    pp11 = [p for p in pps if p.get("id") == "11"][0]
    intent = pp11.find(".//" + "{%s}intent" % NS["hc"]).get("value")
    assert intent == "-2000"


def test_borderfill_ids_are_1_based_and_no_dangling(tmp_path):
    head, sec = _convert(tmp_path)
    defined = {int(bf.get("id")) for bf in head.iter(_hh("borderFill"))}
    assert min(defined) == 1 and max(defined) == 52
    refs = {int(e.get("borderFillIDRef")) for e in list(head.iter()) + list(sec.iter())
            if e.get("borderFillIDRef") is not None}
    assert refs <= defined            # every paraPr/table/cell ref resolves


def test_tables_still_intact(tmp_path):
    _, sec = _convert(tmp_path)
    assert len(sec.findall(".//" + _hp("tbl"))) == 33
