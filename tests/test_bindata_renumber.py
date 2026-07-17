import glob
import re
import tempfile
import zipfile

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _bindata(path):
    return sorted(n for n in zipfile.ZipFile(path).namelist() if n.startswith("BinData/"))


def test_2013_images_renumbered_document_order():
    hwp = glob.glob("samples/2013*.hwp")[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    assert _bindata(out) == ["BinData/image1.jpg", "BinData/image2.bmp",
                             "BinData/image3.png"]


def test_2013_binaryitemidref_matches_names():
    hwp = glob.glob("samples/2013*.hwp")[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    xml = unzip_parts(out)["Contents/section0.xml"].decode("utf-8")
    refs = set(re.findall(r'binaryItemIDRef="([^"]+)"', xml))
    assert refs == {"image1", "image2", "image3"}


def test_sample4_bindata_unchanged():
    hwp = glob.glob("samples/4.*.hwp")[0]
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    assert _bindata(out) == ["BinData/image1.bmp", "BinData/image2.bmp",
                             "BinData/image3.bmp"]
