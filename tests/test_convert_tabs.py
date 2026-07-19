# tests/test_convert_tabs.py
import zipfile
import re
from hwp2hwpx.convert import convert
from tests.samplepaths import S3

SAMPLE_HWP = S3


def _out(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return (z.read("Contents/header.xml").decode("utf-8"),
                z.read("Contents/section0.xml").decode("utf-8"))


def test_tab_properties_counts_match_hancom(tmp_path):
    hdr, _ = _out(tmp_path)
    tp = re.search(r'<hh:tabProperties itemCnt="(\d+)">', hdr)
    assert tp and int(tp.group(1)) == 7
    # 106 tabs -> 106 tab switches; paraPr contributes 126 switches -> 232 total
    assert hdr.count("<hp:switch") == 232
    assert hdr.count("<hh:tabItem ") == 212
    # trailing space so "<hh:tabPr " does not also match "<hh:tabProperties"
    assert hdr.count("<hh:tabPr ") == 7


def test_no_dangling_tab_pr_ref(tmp_path):
    hdr, _ = _out(tmp_path)
    tab_ids = set(re.findall(r'<hh:tabPr id="(\d+)"', hdr))
    refs = set(re.findall(r'<hh:paraPr[^>]*tabPrIDRef="(\d+)"', hdr))
    assert refs, "paraPr must carry tabPrIDRef"
    assert refs <= tab_ids, "no tabPrIDRef may dangle"


def test_real_tab_pr_ids_used(tmp_path):
    hdr, _ = _out(tmp_path)
    refs = set(re.findall(r'<hh:paraPr[^>]*tabPrIDRef="(\d+)"', hdr))
    assert refs != {"0"}, "real (non-default) tabPrIDRefs should appear"
