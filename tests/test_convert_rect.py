from hwp2hwpx.hwpmodel.model import HwpRect, HwpDrawText, HwpShapeComponent, HwpDrawing


def test_hwp_rect_model_defaults():
    r = HwpRect()
    assert r.line_color == "#000000"
    assert r.line_width == 0
    assert r.draw_text is None
    assert r.points == [(0, 0), (0, 0), (0, 0), (0, 0)]
    assert r.text_margin == (0, 0, 0, 0)


def test_shape_component_has_second_matrix_pair():
    c = HwpShapeComponent()
    assert c.scaler_matrix2 == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert c.rotator_matrix2 == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


import glob
from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing, hwp5_xml


def _first_rec_gso(root):
    for el in root.iter():
        if isinstance(el.tag, str) and etree.QName(el).localname == "GShapeObjectControl":
            comp = el.find("ShapeComponent")
            if comp is not None and (comp.get("chid0") == "$rec" or comp.get("chid") == "$rec"):
                return el
    return None


def test_reader_parses_toplevel_rect():
    # Ground truth for this sample (verified against both the hwp5proc XML
    # dump and the reference .hwpx): the 3 top-level $rec GShapeObjectControls
    # (direct GSO children) are plain red-bordered rectangles with no
    # TextboxParagraphList and a single ScaleRotationMatrix. The 2 $rec
    # instances that DO carry text/a second matrix pair are nested inside a
    # $con container's ShapeComponent (not a direct GSO child) -- containers
    # are explicitly out of scope for Task 1 (see task-1-brief.md), so they
    # are not reachable via _first_rec_gso and stay unmapped for now.
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    gso = _first_rec_gso(root)
    d = _parse_drawing(gso)
    assert d is not None
    assert d.kind == "rect"
    assert d.rect is not None
    assert d.rect.line_color == "#ff0000"
    assert d.component.scaler_matrix2 == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert d.component.has_matrix2 is False
    assert d.rect.draw_text is None
    assert d.rect.points == [(0, 0), (8550, 0), (8550, 16050), (0, 16050)]


# Synthetic ShapeComponent covering the "$rec with text" case that the real
# 2013 sample's top-level shapes don't happen to exercise (see above): a
# second ScaleRotationMatrix pair and a TextboxParagraphList with one
# paragraph of real text.
_REC_WITH_TEXT_XML = """<ShapeComponent chid="$rec" chid0="$rec" angle="0" flip="0"
    initial-width="1000" initial-height="2000" width="1000" height="2000"
    x-in-group="0" y-in-group="0" scalerotations-count="2">
  <Coord attribute-name="rotation_center" x="500" y="1000"/>
  <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
  <Array name="scalerotations">
    <ScaleRotationMatrix>
      <Matrix attribute-name="scaler" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
      <Matrix attribute-name="rotator" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
    </ScaleRotationMatrix>
    <ScaleRotationMatrix>
      <Matrix attribute-name="scaler" a="2.0" b="0.0" c="0.0" d="3.0" e="10.0" f="20.0"/>
      <Matrix attribute-name="rotator" a="0.5" b="0.0" c="0.0" d="0.5" e="0.0" f="0.0"/>
    </ScaleRotationMatrix>
  </Array>
  <BorderLine attribute-name="border" color="#123456" width="12"/>
  <TextboxParagraphList maxwidth="900" valign="middle"
      padding-left="10" padding-right="20" padding-top="30" padding-bottom="40">
    <Paragraph parashape-id="0" style-id="0">
      <LineSeg chpos="0" y="0" height="1000" height-text="1000" height-baseline="800" space-below="0" x="0" width="500" lineseg-flags="0">
        <Text charshape-id="0">Hi</Text>
      </LineSeg>
    </Paragraph>
  </TextboxParagraphList>
  <ShapeRectangle round="0">
    <Coord attribute-name="p0" x="0" y="0"/>
    <Coord attribute-name="p1" x="1000" y="0"/>
    <Coord attribute-name="p2" x="1000" y="2000"/>
    <Coord attribute-name="p3" x="0" y="2000"/>
  </ShapeRectangle>
</ShapeComponent>"""


def test_parse_rect_with_text_and_second_matrix_pair():
    from hwp2hwpx.hwpmodel.reader import _parse_shape_component, _parse_rect
    comp = etree.fromstring(_REC_WITH_TEXT_XML)
    component = _parse_shape_component(comp)
    rect = _parse_rect(comp)
    assert component.scaler_matrix2 == [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]
    assert component.rotator_matrix2 == [0.5, 0.0, 0.0, 0.5, 0.0, 0.0]
    assert component.has_matrix2 is True
    assert rect.line_color == "#123456"
    assert rect.line_width == 12
    assert rect.draw_text.last_width == 900
    assert rect.draw_text.vert_align == "CENTER"
    assert len(rect.draw_text.paragraphs) == 1
    assert rect.draw_text.paragraphs[0].runs[0].text == "Hi"
    assert rect.points == [(0, 0), (1000, 0), (1000, 2000), (0, 2000)]
    assert rect.text_margin == (10, 20, 30, 40)


# Full GShapeObjectControl wrapping the same text-bearing $rec ShapeComponent,
# for exercising _parse_drawing end to end (mapper/writer tests below reuse
# this instead of the real 2013 sample, whose top-level $rec shapes carry no
# text -- see test_reader_parses_toplevel_rect above).
_REC_GSO_WITH_TEXT_XML = """<GShapeObjectControl chid="gso " instance-id="777"
    z-order="1" flow="block" text-side="both" x="100" y="200" width="1000" height="2000"
    hrelto="paper" vrelto="paper" halign="left" valign="top" inline="0"
    margin-left="0" margin-right="0" margin-top="0" margin-bottom="0"
    width-relto="absolute" height-relto="absolute">
%s
</GShapeObjectControl>""" % _REC_WITH_TEXT_XML


def _rec_drawing_with_text():
    from hwp2hwpx.hwpmodel.reader import _parse_drawing
    gso = etree.fromstring(_REC_GSO_WITH_TEXT_XML)
    return _parse_drawing(gso)


from hwp2hwpx.owpml.model import Rect, DrawText, SubList
from hwp2hwpx.mapper.drawing import map_drawing


def test_mapper_maps_rect_to_owpml_rect():
    d = _rec_drawing_with_text()
    m = map_drawing(d)
    assert isinstance(m, Rect)
    assert m.ratio == 0
    assert m.group_level == 0
    assert m.line_shape.color == "#123456"
    assert isinstance(m.draw_text, DrawText)
    assert isinstance(m.draw_text.sub_list, SubList)
    assert m.draw_text.sub_list.vert_align == "CENTER"
    assert len(m.draw_text.sub_list.paras) == 1   # reused map_paragraph
    assert (m.draw_text.text_margin.left, m.draw_text.text_margin.right,
            m.draw_text.text_margin.top, m.draw_text.text_margin.bottom) == (10, 20, 30, 40)
    # second matrix pair carried through (source had scalerotations-count="2")
    assert m.sca2 is not None and m.rot2 is not None
    assert (m.sca2.e1, m.sca2.e4, m.sca2.e2, m.sca2.e5) == ("2", "0", "0", "3")
    # outline points and GSO placement (top-level rect)
    assert [(p.x, p.y) for p in m.points] == [(0, 0), (1000, 0), (1000, 2000), (0, 2000)]
    assert m.sz is not None and m.pos is not None and m.out_margin is not None


def test_mapper_maps_toplevel_rect_without_text_or_second_matrix():
    """The real 2013 sample's top-level rects: no drawText, no 2nd matrix
    pair, but still carry outline points and GSO placement (sz/pos/outMargin)."""
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    d = _parse_drawing(_first_rec_gso(root))
    m = map_drawing(d)
    assert isinstance(m, Rect)
    assert m.group_level == 0
    assert m.draw_text is None
    assert m.sca2 is None and m.rot2 is None
    assert len(m.points) == 4
    assert m.sz is not None and m.pos is not None and m.out_margin is not None


from hwp2hwpx.constants import NS
from hwp2hwpx.owpml.section_writer import _write_run
from hwp2hwpx.owpml.model import Run


def _run_xml(run):
    p_el = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"], "hc": NS["hc"]})
    _write_run(p_el, run, state=None)
    return etree.tostring(p_el, encoding="unicode")


def test_writer_emits_rect_with_drawtext():
    rect = map_drawing(_rec_drawing_with_text())
    xml = _run_xml(Run(char_pr_id=0, drawing=rect))
    assert "<hp:rect " in xml and 'ratio="0"' in xml and 'groupLevel="0"' in xml
    assert xml.count("<hc:scaMatrix") == 2   # both matrix pairs
    assert "<hp:drawText " in xml and "<hp:subList " in xml
    assert 'vertAlign="CENTER"' in xml
    assert "<hp:p " in xml   # nested paragraph rendered
    assert "Hi" in xml
    assert xml.count("<hc:pt0") == 1 and xml.count("<hc:pt3") == 1
    assert '<hp:textMargin left="10" right="20" top="30" bottom="40"/>' in xml
    # element order: drawText comes before the pt0..pt3 outline points
    assert xml.index("<hp:drawText") < xml.index("<hc:pt0")
    # this fixture carries GSO placement (top-level rect) -> sz/pos/outMargin
    assert "<hp:sz " in xml and "<hp:outMargin " in xml


def test_writer_emits_toplevel_rect_without_text():
    """Real 2013 sample top-level rect: single matrix pair, no drawText,
    outline points + sz/pos/outMargin, groupLevel="0"."""
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    rect = map_drawing(_parse_drawing(_first_rec_gso(root)))
    xml = _run_xml(Run(char_pr_id=0, drawing=rect))
    assert "<hp:rect " in xml and 'groupLevel="0"' in xml
    assert xml.count("<hc:scaMatrix") == 1   # no 2nd pair
    assert "<hp:drawText" not in xml
    assert xml.count("<hc:pt0") == 1 and xml.count("<hc:pt3") == 1
    assert "<hp:sz " in xml and "<hp:pos " in xml and "<hp:outMargin " in xml
    # element order: shadow, then straight to pt0 (no drawText in between)
    assert xml.index("<hp:shadow") < xml.index("<hc:pt0")


def test_sample2013_toplevel_rects_no_text(tmp_path):
    """Integration: the real 2013 sample's 3 top-level $rec shapes convert
    without error, each emitting a structurally-correct bare <hp:rect> (no
    text -- see ground-truth note on test_reader_parses_toplevel_rect)."""
    from hwp2hwpx.convert import convert
    import zipfile
    out = tmp_path / "s2013.hwpx"
    convert(glob.glob("samples/2013*.hwp")[0], str(out))
    with zipfile.ZipFile(str(out)) as z:
        sec = z.read("Contents/section0.xml").decode("utf-8")
    root = etree.fromstring(sec.encode("utf-8"))
    ns = {"hp": NS["hp"], "hc": NS["hc"]}
    rects = root.findall(".//hp:rect", ns)
    assert len(rects) == 3
    for r in rects:
        assert r.get("groupLevel") == "0"
        assert r.find("hp:drawText", ns) is None
        rend = r.find("hp:renderingInfo", ns)
        assert len(rend.findall("hc:scaMatrix", ns)) == 1   # no 2nd pair
        assert len(rend.findall("hc:rotMatrix", ns)) == 1
        assert [etree.QName(c).localname for c in r.findall("hc:pt0", ns) +
                r.findall("hc:pt1", ns) + r.findall("hc:pt2", ns) + r.findall("hc:pt3", ns)] == \
               ["pt0", "pt1", "pt2", "pt3"]
        assert r.find("hp:sz", ns) is not None
        assert r.find("hp:pos", ns) is not None
        assert r.find("hp:outMargin", ns) is not None
