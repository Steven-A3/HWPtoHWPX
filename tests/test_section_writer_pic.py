from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import (
    Section, Para, Run, Pic, Line, Offset, OrgSz, CurSz, Flip, RotationInfo,
    Matrix, RenderingInfo, Img, ImgRect, ImgClip, InMargin, ImgDim, ShapeComment,
    ShapeSz, ShapePos, ShapeOutMargin, Pt, LineShape, WinBrush, Shadow,
)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HC = "http://www.hancom.co.kr/hwpml/2011/core"


def _qp(t):
    return "{%s}%s" % (HP, t)


def _qc(t):
    return "{%s}%s" % (HC, t)


def _pic():
    return Pic(
        id=111, z_order=15, instid=37461880,
        offset=Offset(0, 0), org_sz=OrgSz(36480, 51660), cur_sz=CurSz(46545, 65913),
        flip=Flip(0, 0), rotation_info=RotationInfo(0, 23272, 32956, 1),
        rendering_info=RenderingInfo(trans=Matrix(), sca=Matrix(), rot=Matrix()),
        img=Img(bin_item_id="image1"),
        img_rect=ImgRect(pt0=Pt(0, 0), pt1=Pt(36480, 0), pt2=Pt(36480, 51660), pt3=Pt(0, 51660)),
        img_clip=ImgClip(0, 36480, 0, 51660), in_margin=InMargin(),
        img_dim=ImgDim(36480, 51660),
        sz=ShapeSz(width=46545, height=65913), pos=ShapePos(treat_as_char=1),
        out_margin=ShapeOutMargin(), shape_comment=ShapeComment(text="그림"),
    )


def _root(section):
    return etree.fromstring(section_xml(section).split(b"?>", 1)[1])


def test_pic_child_order_and_namespaces():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, drawing=_pic())])])
    pic = _root(sec).find(".//" + _qp("pic"))
    assert pic is not None and pic.get("id") == "111" and pic.get("reverse") == "0"
    kids = [etree.QName(c).localname for c in pic]
    assert kids == ["offset", "orgSz", "curSz", "flip", "rotationInfo",
                    "renderingInfo", "img", "imgRect", "imgClip", "inMargin",
                    "imgDim", "effects", "sz", "pos", "outMargin", "shapeComment"]
    assert pic.find(_qc("img")).get("binaryItemIDRef") == "image1"
    ir = pic.find(_qp("imgRect"))
    assert ir.find(_qc("pt2")).get("x") == "36480"
    assert pic.find(_qp("imgClip")).get("right") == "36480"
    assert pic.find(_qp("imgDim")).get("dimwidth") == "36480"
    assert pic.find(_qp("effects")) is not None
    assert pic.find(_qp("shapeComment")).text == "그림"


def test_line_still_emitted_via_dispatch():
    ln = Line(id=9, offset=Offset(0, 0), org_sz=OrgSz(), cur_sz=CurSz(), flip=Flip(),
              rotation_info=RotationInfo(), rendering_info=RenderingInfo(
                  trans=Matrix(), sca=Matrix(), rot=Matrix()),
              line_shape=LineShape(), win_brush=WinBrush(), shadow=Shadow(),
              start_pt=Pt(0, 0), end_pt=Pt(1, 1), sz=ShapeSz(), pos=ShapePos(),
              out_margin=ShapeOutMargin())
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, drawing=ln)])])
    root = _root(sec)
    assert root.find(".//" + _qp("line")) is not None
    assert root.find(".//" + _qp("pic")) is None
