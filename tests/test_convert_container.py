import pytest
from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing, hwp5_xml
from tests.samplepaths import hwp as _hwp, hwpx as _hwpx


def _con_gso(root):
    for el in root.iter():
        if isinstance(el.tag, str) and etree.QName(el).localname == "GShapeObjectControl":
            comp = el.find("ShapeComponent")
            if comp is not None and (comp.get("chid0") == "$con" or comp.get("chid") == "$con"):
                return el
    return None


def test_reader_parses_container_children():
    root = etree.fromstring(hwp5_xml(_hwp("2013")))
    d = _parse_drawing(_con_gso(root))
    assert d.kind == "container"
    kinds = sorted(c.kind for c in d.children)
    assert kinds == ["pic", "rect", "rect"]   # 1 pic + 2 rects
    pic = [c for c in d.children if c.kind == "pic"][0]
    assert pic.picture.bindata_id == 2   # the JPEG, previously dropped


from hwp2hwpx.owpml.model import Container, Pic, Rect
from hwp2hwpx.mapper.drawing import map_drawing


def test_mapper_maps_container_recursively():
    root = etree.fromstring(hwp5_xml(_hwp("2013")))
    m = map_drawing(_parse_drawing(_con_gso(root)))
    assert isinstance(m, Container)
    assert m.group_level == 0
    child_types = sorted(type(c).__name__ for c in m.children)
    assert child_types == ["Pic", "Rect", "Rect"]
    for c in m.children:
        assert c.group_level == 1
    # corrected ground truth: the container itself IS top-level and carries
    # placement (sz/pos/outMargin); its children (nested) do not.
    assert m.sz is not None and m.pos is not None and m.out_margin is not None
    for c in m.children:
        assert c.sz is None and c.pos is None and c.out_margin is None


import tempfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def test_end_to_end_container_and_shapes_present():
    hwp = _hwp("2013")
    ref = _hwpx("2013")
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    o = unzip_parts(out)["Contents/section0.xml"]
    t = unzip_parts(ref)["Contents/section0.xml"]
    miss = score_part(o, t)["missing"]
    assert miss.get("container", 0) == 0
    assert miss.get("rect", 0) == 0
    assert miss.get("pic", 0) == 0
    assert miss.get("drawText", 0) == 0
    xml = o.decode("utf-8")
    assert '<hp:container ' in xml and 'groupLevel="1"' in xml


def test_end_to_end_container_shape_counts_and_nesting():
    """Corrected ground truth: 1 container, 5 rects total (3 top-level from
    Task 1 + 2 nested), 3 pics total (2 top-level + 1 nested JPEG), 2
    drawTexts (only the nested text rects). The container carries trailing
    sz/pos/outMargin; its nested children (groupLevel=1) do not."""
    hwp = _hwp("2013")
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    o = unzip_parts(out)["Contents/section0.xml"]
    root = etree.fromstring(o)
    ns = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
          "hc": "http://www.hancom.co.kr/hwpml/2011/core"}
    containers = root.findall(".//hp:container", ns)
    assert len(containers) == 1
    cont = containers[0]
    assert cont.get("groupLevel") == "0"
    assert cont.find("hp:sz", ns) is not None
    assert cont.find("hp:pos", ns) is not None
    assert cont.find("hp:outMargin", ns) is not None
    nested_rects = cont.findall("hp:rect", ns)
    nested_pics = cont.findall("hp:pic", ns)
    assert len(nested_rects) == 2
    assert len(nested_pics) == 1
    for r in nested_rects:
        assert r.get("groupLevel") == "1"
        assert r.find("hp:sz", ns) is None
        assert r.find("hp:drawText", ns) is not None
    for p in nested_pics:
        assert p.get("groupLevel") == "1"
        assert p.find("hp:sz", ns) is None
        assert p.find("hp:shapeComment", ns) is None
    assert len(root.findall(".//hp:rect", ns)) == 5
    assert len(root.findall(".//hp:pic", ns)) == 3


# Synthetic $con container with a $lin (line) child: no current sample (3/4/
# 2013) nests a line in a container, but the code path must not crash if one
# ever does. _write_line has no None-guard on sz/pos/out_margin the way
# _write_pic and _write_rect do (they're suppressed for nested shapes via
# _map_shape), so a nested line is dropped at the mapping stage instead of
# being wired into _write_line -- a graceful, recoverable fidelity miss
# rather than an AttributeError that aborts the whole conversion.
_CON_WITH_LINE_CHILD_XML = '''
<GShapeObjectControl chid="gso " instance-id="5" z-order="1" flow="block" text-side="both"
  x="0" y="0" width="1000" height="1000" hrelto="paper" vrelto="paper" halign="left" valign="top"
  inline="0" margin-left="0" margin-right="0" margin-top="0" margin-bottom="0"
  width-relto="absolute" height-relto="absolute">
  <ShapeComponent chid="$con" chid0="$con" width="1000" height="1000"
    initial-width="1000" initial-height="1000">
    <ShapeComponent angle="0" chid="$lin" chid0="$lin" flip="0" height="100"
      initial-height="100" initial-width="100" width="0" x-in-group="0" y-in-group="0">
      <Coord attribute-name="rotation_center" x="0" y="50"/>
      <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
      <BorderLine attribute-name="line" color="#000000" width="200" stroke="solid"
        line-end="flat" arrow-start="none" arrow-end="none" arrow-start-fill="1"
        arrow-end-fill="1" arrow-start-size="smallest" arrow-end-size="smallest"/>
      <ShapeLine attr="0">
        <Coord attribute-name="p0" x="0" y="0"/>
        <Coord attribute-name="p1" x="100" y="100"/>
      </ShapeLine>
    </ShapeComponent>
    <ShapeComponent chid="$rec" chid0="$rec" width="1000" height="1000"
      initial-width="1000" initial-height="1000" x-in-group="0" y-in-group="0">
      <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
      <BorderLine attribute-name="border" color="#ff0000" width="0"/>
      <ShapeRectangle round="0">
        <Coord attribute-name="p0" x="0" y="0"/>
        <Coord attribute-name="p1" x="1000" y="0"/>
        <Coord attribute-name="p2" x="1000" y="1000"/>
        <Coord attribute-name="p3" x="0" y="1000"/>
      </ShapeRectangle>
    </ShapeComponent>
  </ShapeComponent>
</GShapeObjectControl>'''


@pytest.mark.sample_free
def test_nested_line_child_dropped_not_crashed():
    from hwp2hwpx.owpml.section_writer import _write_run
    from hwp2hwpx.owpml.model import Run
    from hwp2hwpx.constants import NS

    d = _parse_drawing(etree.fromstring(_CON_WITH_LINE_CHILD_XML))
    assert d.kind == "container"
    assert sorted(c.kind for c in d.children) == ["line", "rect"]

    m = map_drawing(d)
    assert isinstance(m, Container)
    # the line child is dropped (a recoverable fidelity miss); the rect
    # sibling still maps and the container is otherwise intact.
    assert [type(c).__name__ for c in m.children] == ["Rect"]

    p_el = etree.Element("{%s}p" % NS["hp"], nsmap={"hp": NS["hp"], "hc": NS["hc"]})
    _write_run(p_el, Run(char_pr_id=0, texts=[m]), state=None)   # must not raise
    xml = etree.tostring(p_el, encoding="unicode")
    assert "<hp:container " in xml
    assert "<hp:rect " in xml
    assert "<hp:line " not in xml
