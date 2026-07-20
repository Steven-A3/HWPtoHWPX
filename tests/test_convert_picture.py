import zipfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.samplepaths import S3, S4, S4_REF


def _convert(hwp, tmp_path, name):
    out = tmp_path / name
    convert(hwp, str(out))
    return zipfile.ZipFile(str(out))


def test_sample4_three_pics(tmp_path):
    z = _convert(S4, tmp_path, "s4.hwpx")
    sec = z.read("Contents/section0.xml").decode("utf-8")
    assert sec.count("<hp:pic ") == 3


def test_sample4_images_byte_identical_and_declared(tmp_path):
    z = _convert(S4, tmp_path, "s4.hwpx")
    ref = zipfile.ZipFile(S4_REF)
    names = [n for n in z.namelist() if n.startswith("BinData/")]
    assert len(names) == 3
    for n in names:
        assert z.read(n) == ref.read(n), "%s not byte-identical" % n
    hpf = z.read("Contents/content.hpf").decode("utf-8")
    for i in (1, 2, 3):
        assert 'href="BinData/image%d.bmp"' % i in hpf
        assert 'id="image%d"' % i in hpf


def test_sample4_pic_tags_leave_miss_list(tmp_path):
    out = tmp_path / "s4b.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    for tag in ("pic", "img", "imgRect", "imgClip", "imgDim", "shapeComment"):
        assert missing.get(tag, 0) == 0, "%s still missing x%d" % (tag, missing.get(tag, 0))


def test_sample4_section0_match_rose(tmp_path):
    out = tmp_path / "s4c.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    # baseline after Slice A (lines) was 0.9824; pictures lift it further
    assert score_part(ours, theirs)["match"] > 0.99


def test_sample3_unchanged_no_pic_no_bindata(tmp_path):
    z = _convert(S3, tmp_path, "s3.hwpx")
    sec = z.read("Contents/section0.xml").decode("utf-8")
    assert sec.count("<hp:pic ") == 0
    assert [n for n in z.namelist() if n.startswith("BinData/")] == []
    assert "BinData/" not in z.read("Contents/content.hpf").decode("utf-8")
