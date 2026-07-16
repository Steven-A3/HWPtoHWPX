import zipfile
from hwp2hwpx.hwpmodel.reader import hwp5_xml, read_document
from hwp2hwpx.hwpmodel.bindata import extract_bin_items

S4 = "samples/4.제안요청서_070.hwp"
S4_REF = "samples/4.제안요청서_070.hwpx"
S3 = "samples/3.과업지시서_070.hwp"


def _doc(hwp):
    return read_document(hwp5_xml(hwp))


def test_extract_three_byte_identical_images():
    items = extract_bin_items(S4, _doc(S4))
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
    assert extract_bin_items(S3, _doc(S3)) == []
