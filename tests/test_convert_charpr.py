# tests/test_convert_charpr.py
import zipfile
import re
from hwp2hwpx.convert import convert

SAMPLE_HWP = "samples/3.과업지시서_070.hwp"


def _out_header(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/header.xml").decode("utf-8")


def test_charpr_full_subtree_present(tmp_path):
    hdr = _out_header(tmp_path)
    # every charPr carries the new sub-elements and attributes
    assert "<hh:ratio " in hdr
    assert "<hh:spacing " in hdr
    assert "<hh:relSz " in hdr
    assert "<hh:offset " in hdr
    assert "<hh:underline " in hdr
    assert "<hh:strikeout " in hdr
    assert "<hh:outline " in hdr
    assert "<hh:shadow " in hdr
    assert 'symMark="NONE"' in hdr


def test_charpr_borderfill_refs_resolve(tmp_path):
    hdr = _out_header(tmp_path)
    defined = set(re.findall(r'<hh:borderFill id="(\d+)"', hdr))
    refs = set(re.findall(r'<hh:charPr[^>]*borderFillIDRef="(\d+)"', hdr))
    assert refs, "charPr must carry borderFillIDRef"
    assert refs <= defined, "no charPr borderFillIDRef may dangle"


def test_fontref_within_font_range(tmp_path):
    hdr = _out_header(tmp_path)
    # count fonts in the HANGUL bucket (flat list replicated per language)
    block = re.search(r'<hh:fontface lang="HANGUL".*?</hh:fontface>', hdr, re.S).group(0)
    n = len(re.findall(r'<hh:font ', block))
    hangul_refs = [int(v) for v in re.findall(r'<hh:fontRef[^>]*hangul="(\d+)"', hdr)]
    assert hangul_refs
    assert all(0 <= v < n for v in hangul_refs), "fontRef must resolve within its bucket"
