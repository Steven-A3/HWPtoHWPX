# tests/test_convert_styles.py
import zipfile
import re
from hwp2hwpx.convert import convert

SAMPLE_HWP = "samples/3.과업지시서_070.hwp"


def _out(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return (z.read("Contents/header.xml").decode("utf-8"),
                z.read("Contents/section0.xml").decode("utf-8"))


def test_real_styles_present(tmp_path):
    hdr, _ = _out(tmp_path)
    styles = re.search(r'<hh:styles itemCnt="(\d+)">', hdr)
    assert styles and int(styles.group(1)) == 63
    assert 'name="바탕글"' in hdr
    assert 'engName="Normal"' in hdr


def test_style_refs_resolve(tmp_path):
    hdr, sec = _out(tmp_path)
    style_ids = set(re.findall(r'<hh:style id="(\d+)"', hdr))
    para_ids = set(re.findall(r'<hh:paraPr id="(\d+)"', hdr))
    char_ids = set(re.findall(r'<hh:charPr id="(\d+)"', hdr))
    # every style's refs resolve
    for m in re.finditer(r'<hh:style\b[^>]*>', hdr):
        tag = m.group(0)
        pr = re.search(r'paraPrIDRef="(\d+)"', tag)
        cr = re.search(r'charPrIDRef="(\d+)"', tag)
        nr = re.search(r'nextStyleIDRef="(\d+)"', tag)
        if pr:
            assert pr.group(1) in para_ids
        if cr:
            assert cr.group(1) in char_ids
        if nr:
            assert nr.group(1) in style_ids
    # every paragraph styleIDRef resolves
    for ref in re.findall(r'styleIDRef="(\d+)"', sec):
        assert ref in style_ids


def test_real_style_ids_used(tmp_path):
    _, sec = _out(tmp_path)
    refs = set(re.findall(r'styleIDRef="(\d+)"', sec))
    assert refs, "paragraphs must carry styleIDRef"
    assert refs != {"0"}, "real (non-default) style ids should appear"
