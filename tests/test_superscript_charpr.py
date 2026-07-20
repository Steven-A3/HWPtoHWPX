"""Superscript charPr: charshapeflags bit 15 -> <hh:supscript/> (mirror of the
subscript milestone, which uses bit 16). Emitted before <hh:subscript>."""
import pytest
from lxml import etree

from hwp2hwpx.constants import NS
from hwp2hwpx.hwpmodel.reader import read_docinfo, hwp5_xml
from hwp2hwpx.hwpmodel.model import HwpCharShape
from hwp2hwpx.owpml.model import CharPr, Header
from hwp2hwpx.mapper.char_pr import map_char_shapes
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.samplepaths import hwp as _hwp, hwpx as _hwpx

S2013 = _hwp("2013")
S2013_REF = _hwpx("2013")


# ---- reader ---------------------------------------------------------------

def test_reader_sets_superscript_from_flag_bit15():
    di = read_docinfo(hwp5_xml(S2013))
    # verified: charshapes 159/182/225/226/259/281 carry bit 15.
    assert di.char_shapes[159].superscript is True
    assert di.char_shapes[281].superscript is True
    assert di.char_shapes[0].superscript is False


def test_reader_superscript_and_subscript_independent():
    di = read_docinfo(hwp5_xml(S2013))
    # the bit-15 charshapes are superscript, not subscript.
    assert di.char_shapes[159].subscript is False


# ---- mapper ---------------------------------------------------------------

@pytest.mark.sample_free
def test_mapper_passes_superscript_through():
    cps = map_char_shapes([HwpCharShape(index=0, base_size=1000, superscript=True),
                           HwpCharShape(index=1, base_size=1000)])
    assert cps[0].superscript is True and cps[1].superscript is False


# ---- writer ---------------------------------------------------------------

@pytest.mark.sample_free
def test_writer_emits_supscript():
    header = Header(char_prs=[CharPr(id=0, superscript=True)])
    ce = etree.fromstring(header_xml(header)).find(".//{%s}charPr" % NS["hh"])
    assert ce.find("{%s}supscript" % NS["hh"]) is not None


@pytest.mark.sample_free
def test_writer_no_supscript_when_false():
    header = Header(char_prs=[CharPr(id=0, superscript=False)])
    ce = etree.fromstring(header_xml(header)).find(".//{%s}charPr" % NS["hh"])
    assert ce.find("{%s}supscript" % NS["hh"]) is None


@pytest.mark.sample_free
def test_writer_supscript_precedes_subscript():
    # OWPML schema order: supscript before subscript when both are present.
    header = Header(char_prs=[CharPr(id=0, superscript=True, subscript=True)])
    ce = etree.fromstring(header_xml(header)).find(".//{%s}charPr" % NS["hh"])
    kids = [etree.QName(c).localname for c in ce]
    assert kids.index("supscript") < kids.index("subscript")


# ---- end-to-end -----------------------------------------------------------

def _header_score(hwp, ref, tmp_path):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return score_part(unzip_parts(str(out))["Contents/header.xml"],
                      unzip_parts(ref)["Contents/header.xml"])


def test_sample2013_superscript_gap_closed(tmp_path):
    s = _header_score(S2013, S2013_REF, tmp_path)
    assert s["missing"].get("supscript", 0) == 0


def test_sample2013_supscript_placement_byte_exact(tmp_path):
    # The supscript element sits directly after <hh:shadow/>, byte-identical to
    # Hancom (charPr 159 tail; earlier chars differ only by the substFont
    # non-goal, so compare from shadow onward).
    out = tmp_path / "o.hwpx"
    convert(S2013, str(out))
    import re
    ox = unzip_parts(str(out))["Contents/header.xml"].decode("utf-8")
    tx = unzip_parts(S2013_REF)["Contents/header.xml"].decode("utf-8")
    oc = re.findall(r"<hh:charPr\b[^>]*>.*?</hh:charPr>", ox, re.S)[159]
    tc = re.findall(r"<hh:charPr\b[^>]*>.*?</hh:charPr>", tx, re.S)[159]
    assert oc[oc.find("<hh:shadow"):] == tc[tc.find("<hh:shadow"):]


def test_samples_3_4_have_no_superscript(tmp_path):
    for prefix in ("3.", "4."):
        hwp = _hwp(prefix)
        di = read_docinfo(hwp5_xml(hwp))
        assert all(not cs.superscript for cs in di.char_shapes)
