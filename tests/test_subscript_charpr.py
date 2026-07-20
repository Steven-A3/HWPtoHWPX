from lxml import etree
from hwp2hwpx.constants import NS
from hwp2hwpx.hwpmodel.reader import read_docinfo, hwp5_xml
from hwp2hwpx.hwpmodel.model import HwpCharShape
from hwp2hwpx.owpml.model import CharPr, Header
from hwp2hwpx.mapper.char_pr import map_char_shapes
from hwp2hwpx.owpml.header_writer import header_xml
from tests.samplepaths import hwp as _hwp


def test_reader_sets_subscript_from_flag_bit16():
    di = read_docinfo(hwp5_xml(_hwp("3.")))
    assert di.char_shapes[58].subscript is True
    assert di.char_shapes[59].subscript is True
    assert di.char_shapes[0].subscript is False


def test_mapper_passes_subscript_through():
    cps = map_char_shapes([HwpCharShape(index=0, base_size=1000, subscript=True),
                           HwpCharShape(index=1, base_size=1000)])
    assert cps[0].subscript is True and cps[1].subscript is False


def test_writer_emits_subscript_as_last_child():
    header = Header(char_prs=[CharPr(id=0, subscript=True)])
    xml = header_xml(header)
    root = etree.fromstring(xml)
    ce = root.find(".//{%s}charPr" % NS["hh"])
    kids = [etree.QName(c).localname for c in ce]
    assert kids[-1] == "subscript"
    assert ce.find("{%s}subscript" % NS["hh"]) is not None


def test_writer_no_subscript_when_false():
    header = Header(char_prs=[CharPr(id=0, subscript=False)])
    xml = header_xml(header)
    root = etree.fromstring(xml)
    ce = root.find(".//{%s}charPr" % NS["hh"])
    assert ce.find("{%s}subscript" % NS["hh"]) is None
