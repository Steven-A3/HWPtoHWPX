import glob
import zipfile

import pytest

from hwp2hwpx.hwpmodel.reader import hwp5_xml, read_document
from hwp2hwpx.hwpmodel.bindata import extract_bin_items
from tests.samplepaths import S3, S4, S4_REF


def _doc(hwp):
    return read_document(hwp5_xml(hwp))


def test_extract_three_byte_identical_images():
    items, bin_index = extract_bin_items(S4, _doc(S4))
    assert len(items) == 3
    assert sorted(i.id for i in items) == ["image1", "image2", "image3"]
    assert all(i.media_type == "image/bmp" for i in items)
    assert all(i.filename.endswith(".bmp") for i in items)
    ref = zipfile.ZipFile(S4_REF)
    for it in items:
        want = ref.read("BinData/%s" % it.filename)
        assert it.data == want, "%s not byte-identical" % it.filename
        assert len(it.data) > 0


def test_no_pictures_no_bin_items():
    assert extract_bin_items(S3, _doc(S3)) == ([], {})


def test_extract_reaches_pic_nested_in_container():
    """Task 2: a $con container's child pic is never its own top-level
    run.drawing (it only shows up in the container's .children), so the
    bindata collector must recurse into container children or the nested
    JPEG's binaryItemIDRef="image2" dangles with no embedded file."""
    s2013 = glob.glob("samples/2013*.hwp")[0]
    items, bin_index = extract_bin_items(s2013, _doc(s2013))
    ids = sorted(i.id for i in items)
    assert ids == ["image1", "image2", "image3"]
    jpeg = [i for i in items if i.id == "image1"][0]
    # Hancom spells this "image/jpg" (non-standard) in content.hpf, not the
    # RFC-correct "image/jpeg" -- matched here for fidelity. See
    # test_2013_jpeg_media_type_matches_hancom_content_hpf for the e2e check.
    assert jpeg.media_type == "image/jpg"
    assert jpeg.filename.endswith(".jpg")
    assert len(jpeg.data) > 0


@pytest.mark.sample_free
def test_stream_num_parses_hex_not_decimal():
    # pyhwp names BinData streams BIN%04X (hex); bindata-id is decimal. The two
    # only coincide for ids 1-9, so parsing must be hex to survive >= 10 images.
    from hwp2hwpx.hwpmodel.bindata import _stream_num
    assert _stream_num("BIN0001.bmp") == 1
    assert _stream_num("BIN0009.bmp") == 9
    assert _stream_num("BIN000A.bmp") == 10   # was ValueError -> image dropped
    assert _stream_num("BIN0010.png") == 16   # was wrongly parsed as 10
