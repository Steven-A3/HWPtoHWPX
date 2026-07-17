from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing, parse_paragraph

LINE_GSO = '''
<GShapeObjectControl chid="gso " flow="front" halign="left" height="1504"
  height-relto="absolute" hrelto="paper" inline="0" instance-id="1111203675"
  margin-bottom="0" margin-left="0" margin-right="0" margin-top="0"
  number-category="figure" text-side="both" valign="top" vrelto="paper"
  width="0" width-relto="absolute" x="29344" y="24972" z-order="29">
  <ShapeComponent angle="0" chid="$lin" chid0="$lin" flip="0" height="1504"
    initial-height="100" initial-width="100" width="0" x-in-group="0" y-in-group="0">
    <Coord attribute-name="rotation_center" x="0" y="752"/>
    <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
    <Array name="scalerotations"><ScaleRotationMatrix>
      <Matrix attribute-name="scaler" a="0.0" b="0.0" c="0.0" d="15.04" e="0.0" f="0.0"/>
      <Matrix attribute-name="rotator" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
    </ScaleRotationMatrix></Array>
    <BorderLine attribute-name="line" color="#000000" width="200" stroke="solid"
      line-end="flat" arrow-start="none" arrow-end="none" arrow-start-fill="1"
      arrow-end-fill="1" arrow-start-size="smallest" arrow-end-size="smallest"/>
    <ShapeLine attr="0">
      <Coord attribute-name="p0" x="0" y="0"/>
      <Coord attribute-name="p1" x="100" y="100"/>
    </ShapeLine>
  </ShapeComponent>
</GShapeObjectControl>'''

CONTAINER_GSO = '''
<GShapeObjectControl chid="gso " instance-id="5" z-order="1">
  <ShapeComponent chid="$con" chid0="$con" width="10" height="10"
    initial-width="10" initial-height="10"/>
</GShapeObjectControl>'''


def test_parse_line_drawing():
    d = _parse_drawing(etree.fromstring(LINE_GSO))
    assert d is not None and d.kind == "line"
    assert d.instance_id == 1111203675 and d.z_order == 29
    assert d.x == 29344 and d.y == 24972
    assert d.flow == "front" and d.inline == 0
    c = d.component
    assert c.initial_width == 100 and c.width == 0 and c.height == 1504
    assert c.center_x == 0 and c.center_y == 752
    assert c.trans_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert c.scaler_matrix[3] == 15.04     # d position
    assert d.line.color == "#000000" and d.line.width == 200
    assert d.line.p0 == (0, 0) and d.line.p1 == (100, 100)


def test_container_component_parses_as_container_kind():
    # $con (container/group) is handled (Task 2): a childless container
    # still parses, just with an empty children list.
    d = _parse_drawing(etree.fromstring(CONTAINER_GSO))
    assert d is not None and d.kind == "container"
    assert d.children == []


def test_parse_paragraph_puts_drawing_in_its_own_run():
    para = etree.fromstring(
        '<Paragraph parashape-id="0" style-id="0"><LineSeg>' + LINE_GSO +
        '</LineSeg></Paragraph>')
    p = parse_paragraph(para)
    drawing_runs = [r for r in p.runs if r.drawing is not None]
    assert len(drawing_runs) == 1
    assert drawing_runs[0].drawing.instance_id == 1111203675
