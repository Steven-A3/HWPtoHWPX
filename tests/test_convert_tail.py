import zipfile
from hwp2hwpx.convert import convert

SAMPLE1 = "samples/3.과업지시서_070.hwp"
SAMPLE2 = "samples/4.제안요청서_070.hwp"


def _parts(tmp_path, src):
    out = tmp_path / "out.hwpx"
    convert(src, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return (z.read("Contents/header.xml").decode("utf-8"),
                z.read("Contents/section0.xml").decode("utf-8"))


def test_typeinfo_emitted_both_samples(tmp_path):
    hdr1, _ = _parts(tmp_path, SAMPLE1)
    assert "<hh:typeInfo " in hdr1
    # sample 1: every font carries a typeInfo (one per <hh:font>)
    assert hdr1.count("<hh:typeInfo ") == hdr1.count("<hh:font ")

    hdr2, _ = _parts(tmp_path, SAMPLE2)
    assert "<hh:typeInfo " in hdr2
    # sample 2 has one alternate/substitute FaceName ("신명조■얒a") whose HWP
    # record has flags.metric=0, so pyhwp never parses a Panose1 for it (see
    # hwp5/binmodel/tagid19_face_name.py: FaceName.attributes -> `panose1`
    # is conditioned on has_metric). That single font is replicated across
    # all 7 language buckets, so it's short exactly 7 typeInfo elements
    # relative to font elements. This is real source data, not a bug.
    assert hdr2.count("<hh:font ") - hdr2.count("<hh:typeInfo ") == 7


def test_tab_emitted_sample2(tmp_path):
    _, sec = _parts(tmp_path, SAMPLE2)
    assert "<hp:tab " in sec


def test_sample1_still_valid(tmp_path):
    hdr, sec = _parts(tmp_path, SAMPLE1)
    # typeInfo present on sample 1 too; linesegarray/tabs unaffected
    assert "<hh:typeInfo " in hdr
    assert sec.count("<hp:linesegarray") == 749
