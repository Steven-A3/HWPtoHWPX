import glob
from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing, hwp5_xml


def _con_gso(root):
    for el in root.iter():
        if isinstance(el.tag, str) and etree.QName(el).localname == "GShapeObjectControl":
            comp = el.find("ShapeComponent")
            if comp is not None and (comp.get("chid0") == "$con" or comp.get("chid") == "$con"):
                return el
    return None


def test_reader_parses_container_children():
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
    d = _parse_drawing(_con_gso(root))
    assert d.kind == "container"
    kinds = sorted(c.kind for c in d.children)
    assert kinds == ["pic", "rect", "rect"]   # 1 pic + 2 rects
    pic = [c for c in d.children if c.kind == "pic"][0]
    assert pic.picture.bindata_id == 2   # the JPEG, previously dropped


from hwp2hwpx.owpml.model import Container, Pic, Rect
from hwp2hwpx.mapper.drawing import map_drawing


def test_mapper_maps_container_recursively():
    root = etree.fromstring(hwp5_xml(glob.glob("samples/2013*.hwp")[0]))
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
    hwp = glob.glob("samples/2013*.hwp")[0]
    ref = glob.glob("samples/2013*.hwpx")[0]
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
    hwp = glob.glob("samples/2013*.hwp")[0]
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
