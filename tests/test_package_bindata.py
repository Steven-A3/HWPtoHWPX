import zipfile
from hwp2hwpx.owpml.writer import write_hwpx
from hwp2hwpx.owpml.package_parts import content_hpf
from hwp2hwpx.owpml.model import (
    OwpmlDocument, Header, Metadata, Section, BinItem,
)


def test_content_hpf_declares_images():
    hpf = content_hpf(Metadata(title="t"), 1, [
        BinItem(id="image1", filename="image1.bmp", media_type="image/bmp", data=b"BM"),
    ]).decode("utf-8")
    assert '<opf:item id="image1" href="BinData/image1.bmp" media-type="image/bmp" isEmbeded="1"/>' in hpf


def test_content_hpf_no_images_when_empty():
    hpf = content_hpf(Metadata(title="t"), 1).decode("utf-8")
    assert "BinData/" not in hpf


def test_write_hwpx_embeds_bindata(tmp_path):
    doc = OwpmlDocument(
        header=Header(), sections=[Section(paras=[])], metadata=Metadata(title="t"),
        bin_items=[BinItem(id="image1", filename="image1.bmp",
                           media_type="image/bmp", data=b"BMdata")])
    out = tmp_path / "o.hwpx"
    write_hwpx(doc, str(out))
    with zipfile.ZipFile(str(out)) as z:
        assert z.read("BinData/image1.bmp") == b"BMdata"
        assert "image1" in z.read("Contents/content.hpf").decode("utf-8")
