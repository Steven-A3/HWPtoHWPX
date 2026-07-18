"""Gradation fills: a source BorderFill with gradation="1"/FillGradation maps to
<hc:fillBrush><hc:gradation>...<hc:color/>...</hc:gradation></hc:fillBrush>.
Scoped to gradation only; the borderFill-id offset (#68) is a known residual."""
import glob
import re
from lxml import etree

from hwp2hwpx.hwpmodel.model import HwpBorderFill, HwpGradation
from hwp2hwpx.hwpmodel.reader import _parse_border_fills, read_docinfo, hwp5_xml
from hwp2hwpx.owpml.model import BorderFill, Gradation
from hwp2hwpx.mapper.border_fill import map_border_fills, _map_gradation
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S2013 = glob.glob("samples/2013*.hwp")[0]
S2013_REF = glob.glob("samples/2013*.hwpx")[0]
S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]


def _id_mappings(inner):
    return etree.fromstring("<IdMappings>" + inner + "</IdMappings>")


# ---- reader ---------------------------------------------------------------

def test_reader_parses_gradation():
    idm = _id_mappings(
        '<BorderFill gradation="1"><FillGradation attribute-name="fill_gradation" '
        'blur="50" gradation-type="linear" shear="0" type="01">'
        '<Coord32 attribute-name="center" x="0" y="0"/>'
        '<colors alpha="0" hex="#ffffff"/><colors alpha="0" hex="#bbbbbb"/>'
        '</FillGradation></BorderFill>')
    bf = _parse_border_fills(idm)[0]
    assert bf.gradation == HwpGradation(
        type="linear", angle=0, center_x=0, center_y=0, step=50,
        colors=["#ffffff", "#bbbbbb"])


def test_reader_no_gradation_is_none():
    bf = _parse_border_fills(_id_mappings("<BorderFill/>"))[0]
    assert bf.gradation is None


def test_sample2013_has_two_gradations():
    di = read_docinfo(hwp5_xml(S2013))
    grads = [bf for bf in di.border_fills if bf.gradation is not None]
    assert len(grads) == 2
    assert grads[0].gradation.type == "linear"
    assert grads[1].gradation.type == "circular"


def test_samples_3_4_have_no_gradation():
    for hwp in (S3, S4):
        di = read_docinfo(hwp5_xml(hwp))
        assert all(bf.gradation is None for bf in di.border_fills)


# ---- mapper ---------------------------------------------------------------

def test_mapper_maps_gradation_type_and_uppercases_colors():
    out = _map_gradation(HwpGradation(type="circular", angle=0, center_x=0,
                                      center_y=0, step=50,
                                      colors=["#0080c0", "#3cbfff"]))
    assert out == Gradation(type="RADIAL", angle=0, center_x=0, center_y=0,
                            step=50, step_center=50, alpha=0,
                            colors=["#0080C0", "#3CBFFF"])


def test_mapper_linear_maps_to_linear():
    out = _map_gradation(HwpGradation(type="linear", colors=["#ffffff"]))
    assert out.type == "LINEAR"


# ---- writer / end-to-end --------------------------------------------------

def _header(hwp, tmp_path):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return unzip_parts(str(out))["Contents/header.xml"].decode("utf-8")


def _gradations(xml):
    def qn(e):
        return etree.QName(e).localname
    return [re.sub(r'\sxmlns[^=]*="[^"]*"', "", etree.tostring(e, encoding="unicode"))
            for e in etree.fromstring(xml.encode("utf-8")).iter()
            if qn(e) == "gradation"]


def test_writer_gradation_byte_exact(tmp_path):
    ours = _gradations(_header(S2013, tmp_path))
    theirs = _gradations(
        unzip_parts(S2013_REF)["Contents/header.xml"].decode("utf-8"))
    assert len(ours) == 2
    assert ours == theirs


def test_sample2013_gradation_and_color_gaps_closed(tmp_path):
    out = tmp_path / "o.hwpx"
    convert(S2013, str(out))
    s = score_part(unzip_parts(str(out))["Contents/header.xml"],
                   unzip_parts(S2013_REF)["Contents/header.xml"])
    assert s["missing"].get("gradation", 0) == 0
    assert s["missing"].get("color", 0) == 0


def test_samples_3_4_header_unaffected(tmp_path):
    for prefix in ("samples/3.", "samples/4."):
        hwp = glob.glob(prefix + "*.hwp")[0]
        ref = glob.glob(prefix + "*.hwpx")[0]
        out = tmp_path / "o.hwpx"
        convert(hwp, str(out))
        s = score_part(unzip_parts(str(out))["Contents/header.xml"],
                       unzip_parts(ref)["Contents/header.xml"])
        assert {k: v for k, v in s["missing"].items() if v and k != "substFont"} == {}
