import tempfile

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from hwp2hwpx.fidelity.diff import score_part
from tests.samplepaths import hwp as _hwp, hwpx as _hwpx


def test_summary_info_parsed():
    from hwp2hwpx.hwpmodel.summary import read_summary_info
    si = read_summary_info(_hwp("2013"))
    assert si.creator == "최병철"
    assert si.title == "ETRI 미래가치 제고 방안"
    assert si.created_date == "2008-05-01T06:01:38Z"


def test_content_hpf_meta_blocks_present():
    hwp = _hwp("2013")
    ref = _hwpx("2013")
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    o = unzip_parts(out)["Contents/content.hpf"]
    t = unzip_parts(ref)["Contents/content.hpf"]
    assert score_part(o, t)["missing"].get("meta", 0) == 0
    xml = o.decode("utf-8")
    assert '<opf:meta name="creator" content="text">최병철</opf:meta>' in xml
    assert '<opf:meta name="keyword" content="text"/>' in xml
