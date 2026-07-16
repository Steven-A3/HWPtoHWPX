from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing

PIC_GSO = '''
<GShapeObjectControl chid="gso " flow="block" halign="left" height="65913"
  hrelto="paragraph" inline="1" instance-id="1111203703" margin-left="0"
  margin-right="0" margin-top="0" margin-bottom="0" text-side="both"
  valign="top" vrelto="paragraph" width="46545" width-relto="absolute"
  x="0" y="0" z-order="15">
  <ShapeComponent chid="$pic" chid0="$pic" angle="0" flip="0" width="46545"
    height="65913" initial-width="36480" initial-height="51660">
    <Coord attribute-name="rotation_center" x="23272" y="32956"/>
    <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
    <ShapePicture instance-id="37461880" padding-left="0" padding-right="0"
      padding-top="0" padding-bottom="0" border-transparency="0">
      <ImageRect attribute-name="rect">
        <Coord attribute-name="p0" x="0" y="0"/>
        <Coord attribute-name="p1" x="36480" y="0"/>
        <Coord attribute-name="p2" x="36480" y="51660"/>
        <Coord attribute-name="p3" x="0" y="51660"/>
      </ImageRect>
      <ImageClip attribute-name="clip" left="0" right="36480" top="0" bottom="51660"/>
      <PictureInfo attribute-name="picture" bindata-id="1" brightness="0" contrast="0" effect="0"/>
    </ShapePicture>
  </ShapeComponent>
</GShapeObjectControl>'''


def test_parse_picture_drawing():
    d = _parse_drawing(etree.fromstring(PIC_GSO))
    assert d is not None and d.kind == "pic"
    assert d.instance_id == 1111203703 and d.z_order == 15
    assert d.component.initial_width == 36480
    p = d.picture
    assert p is not None
    assert p.instance_id == 37461880 and p.bindata_id == 1
    assert p.img_rect == [(0, 0), (36480, 0), (36480, 51660), (0, 51660)]
    assert p.img_clip == (0, 36480, 0, 51660)     # left,right,top,bottom
    assert p.brightness == 0 and p.effect == 0
    assert p.dim_width == 36480 and p.dim_height == 51660
    assert d.line is None
