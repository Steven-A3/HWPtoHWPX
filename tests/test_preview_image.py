import glob
import zipfile

from hwp2hwpx.hwpmodel.bindata import (
    _preview_png_or_none,
    extract_preview_image,
)

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def test_sniff_accepts_png():
    data = PNG_SIG + b"payload"
    assert _preview_png_or_none(data) == data


def test_sniff_rejects_gif():
    assert _preview_png_or_none(b"GIF89a....") is None


def test_sniff_rejects_bmp():
    assert _preview_png_or_none(b"BM\x00\x00....") is None


def test_sniff_rejects_empty():
    assert _preview_png_or_none(b"") is None


def test_extract_returns_png_for_png_source():
    hwp = glob.glob("samples/3.*.hwp")[0]
    data = extract_preview_image(hwp)
    assert data is not None
    assert data.startswith(PNG_SIG)


def test_extract_skips_non_png_source():
    # The 2013 sample's PrvImage stream is a GIF, not a PNG.
    hwp = glob.glob("samples/2013*.hwp")[0]
    assert extract_preview_image(hwp) is None
