# tests/test_convert_docsettings.py
import zipfile
import pytest
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

PAIRS = [
    ("samples/3.과업지시서_070.hwp", "samples/3.과업지시서_070.hwpx"),
    ("samples/4.제안요청서_070.hwp", "samples/4.제안요청서_070.hwpx"),
]


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_docsettings_tags_leave_header_miss_list(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/header.xml"]
    theirs = unzip_parts(ref)["Contents/header.xml"]
    missing = score_part(ours, theirs)["missing"]
    for tag in ("beginNum", "compatibleDocument", "layoutCompatibility",
                "docOption", "linkinfo", "trackchageConfig"):
        assert missing.get(tag, 0) == 0, "%s still missing on %s" % (tag, hwp)


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_begin_num_present_all_one(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    with zipfile.ZipFile(str(out)) as z:
        h = z.read("Contents/header.xml").decode("utf-8")
    assert '<hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>' in h


@pytest.mark.parametrize("hwp,ref", PAIRS)
def test_header_match_high(tmp_path, hwp, ref):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/header.xml"]
    theirs = unzip_parts(ref)["Contents/header.xml"]
    assert score_part(ours, theirs)["match"] > 0.998
