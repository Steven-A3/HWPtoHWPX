import glob
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _score(prefix, tmp_path):
    hwp = glob.glob(prefix + "*.hwp")[0]
    ref = glob.glob(prefix + "*.hwpx")[0]
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(ref)["Contents/section0.xml"]
    return score_part(ours, theirs)


def test_sample3_pagehiding_present(tmp_path):
    s = _score("samples/3.", tmp_path)
    assert s["missing"].get("pageHiding", 0) == 0


def test_sample4_pagehiding_present(tmp_path):
    s = _score("samples/4.", tmp_path)
    assert s["missing"].get("pageHiding", 0) == 0


def test_sample4_pagehiding_serialization(tmp_path):
    hwp = glob.glob("samples/4.*.hwp")[0]
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    xml = unzip_parts(str(out))["Contents/section0.xml"].decode("utf-8")
    assert '<hp:ctrl><hp:pageHiding hideHeader="0" hideFooter="0" hideMasterPage="0" hideBorder="0" hideFill="0" hidePageNum="1"/></hp:ctrl>' in xml
