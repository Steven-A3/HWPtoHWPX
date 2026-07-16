from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import (
    Section, Para, Run, Line, Offset, OrgSz, CurSz, Flip, RotationInfo, Matrix,
    RenderingInfo, LineShape, WinBrush, Shadow, Pt, ShapeSz, ShapePos,
    ShapeOutMargin,
)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HC = "http://www.hancom.co.kr/hwpml/2011/core"


def _qp(t):
    return "{%s}%s" % (HP, t)


def _qc(t):
    return "{%s}%s" % (HC, t)


def _line():
    return Line(
        id=111, z_order=29, text_wrap="IN_FRONT_OF_TEXT",
        offset=Offset(0, 0), org_sz=OrgSz(100, 100), cur_sz=CurSz(0, 1504),
        flip=Flip(0, 0),
        rotation_info=RotationInfo(0, 0, 752, 0),
        rendering_info=RenderingInfo(trans=Matrix(), sca=Matrix(e5="15.04"),
                                     rot=Matrix()),
        line_shape=LineShape(color="#000000", width=200),
        win_brush=WinBrush(), shadow=Shadow(),
        start_pt=Pt(0, 0), end_pt=Pt(100, 100),
        sz=ShapeSz(width=0, height=1504),
        pos=ShapePos(horz_offset=29344, vert_offset=24972),
        out_margin=ShapeOutMargin(),
    )


def _root(section):
    return etree.fromstring(section_xml(section).split(b"?>", 1)[1])


def test_line_emitted_with_correct_children_and_namespaces():
    sec = Section(paras=[Para(id=0, para_pr_id=0,
                              runs=[Run(char_pr_id=0, drawing=_line())])])
    line = _root(sec).find(".//" + _qp("line"))
    assert line is not None
    assert line.get("id") == "111" and line.get("zOrder") == "29"
    kids = [etree.QName(c).localname for c in line]
    assert kids == ["offset", "orgSz", "curSz", "flip", "rotationInfo",
                    "renderingInfo", "lineShape", "fillBrush", "shadow",
                    "startPt", "endPt", "sz", "pos", "outMargin"]
    # namespace checks: matrices + points + brush are hc:, rest hp:
    ri = line.find(_qp("renderingInfo"))
    assert ri.find(_qc("transMatrix")) is not None
    assert ri.find(_qc("scaMatrix")).get("e5") == "15.04"
    assert line.find(_qc("startPt")).get("x") == "0"
    assert line.find(_qc("endPt")).get("y") == "100"
    assert line.find(_qc("fillBrush")).find(_qc("winBrush")) is not None
    assert line.find(_qp("lineShape")).get("style") == "SOLID"
    assert line.find(_qp("pos")).get("horzOffset") == "29344"


def test_run_without_drawing_emits_no_line():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0)])])
    assert _root(sec).find(".//" + _qp("line")) is None
