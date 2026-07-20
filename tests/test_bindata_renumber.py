import re
import tempfile
import zipfile

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.samplepaths import hwp as _hwp


def _bindata(path):
    return sorted(n for n in zipfile.ZipFile(path).namelist() if n.startswith("BinData/"))


def test_2013_images_renumbered_document_order():
    hwp = _hwp("2013")
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    assert _bindata(out) == ["BinData/image1.jpg", "BinData/image2.bmp",
                             "BinData/image3.png"]


def test_2013_binaryitemidref_matches_names():
    hwp = _hwp("2013")
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    xml = unzip_parts(out)["Contents/section0.xml"].decode("utf-8")
    refs = set(re.findall(r'binaryItemIDRef="([^"]+)"', xml))
    assert refs == {"image1", "image2", "image3"}


def test_sample4_bindata_unchanged():
    hwp = _hwp("4.")
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    assert _bindata(out) == ["BinData/image1.bmp", "BinData/image2.bmp",
                             "BinData/image3.bmp"]


def test_2013_jpeg_media_type_matches_hancom_content_hpf():
    """Hancom's content.hpf spells the JPEG media type "image/jpg" (not the
    RFC-correct "image/jpeg") -- matched here for fidelity. Confirmed against
    samples/20131106*.hwpx's own content.hpf, which uses the same spelling."""
    hwp = _hwp("2013")
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    hpf = unzip_parts(out)["Contents/content.hpf"].decode("utf-8")
    assert 'href="BinData/image1.jpg" media-type="image/jpg"' in hpf
    assert "image/jpeg" not in hpf
