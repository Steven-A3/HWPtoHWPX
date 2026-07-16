from hwp2hwpx.hwpmodel.model import HwpPicture, HwpDrawing
from hwp2hwpx.owpml.model import (
    Pic, Img, ImgRect, ImgClip, InMargin, ImgDim, ShapeComment, BinItem,
    OwpmlDocument, Header, Metadata,
)


def test_hwp_picture_defaults():
    p = HwpPicture()
    assert p.bindata_id == 0
    assert p.img_rect == [(0, 0), (0, 0), (0, 0), (0, 0)]
    assert p.img_clip == (0, 0, 0, 0)
    assert HwpDrawing(kind="pic", picture=p).picture.bindata_id == 0


def test_owpml_pic_and_binitem_defaults():
    assert Img().effect == "REAL_PIC"
    assert Pic(id=5).text_wrap == "TOP_AND_BOTTOM"
    assert Pic().img is None and Pic().shape_comment is None
    b = BinItem(id="image1", filename="image1.bmp", media_type="image/bmp", data=b"BM")
    assert b.data == b"BM"


def test_owpml_document_has_bin_items():
    d = OwpmlDocument(header=Header(), sections=[], metadata=Metadata())
    assert d.bin_items == []
