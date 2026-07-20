import tempfile

import pytest

from tests.samplepaths import hwp as _hwp, hwpx as _hwpx
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts


def _out(n):
    hwp = _hwp(n)
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    return unzip_parts(out)


def test_container_rdf_present_and_matches():
    o = _out("2013")
    assert "META-INF/container.rdf" in o
    rdf = o["META-INF/container.rdf"].decode("utf-8")
    assert "#HeaderFile" in rdf and "#SectionFile" in rdf and "#Document" in rdf
    assert rdf.count("#SectionFile") == 1


def test_container_xml_has_rdf_rootfile():
    o = _out("2013")
    cx = o["META-INF/container.xml"].decode("utf-8")
    assert 'full-path="META-INF/container.rdf" media-type="application/rdf+xml"' in cx


def test_container_rdf_all_samples():
    for n in ("3.", "4.", "2013"):
        assert "META-INF/container.rdf" in _out(n)


def test_container_rdf_byte_equals_reference():
    for n in ("3.", "4.", "2013"):
        hwp = _hwp(n)
        ref = _hwpx(n)
        out = tempfile.mktemp(suffix=".hwpx")
        convert(hwp, out)
        got = unzip_parts(out)["META-INF/container.rdf"]
        want = unzip_parts(ref)["META-INF/container.rdf"]
        assert got == want, "container.rdf mismatch for sample %s" % n


def test_container_xml_byte_equals_reference():
    for n in ("3.", "4.", "2013"):
        hwp = _hwp(n)
        ref = _hwpx(n)
        out = tempfile.mktemp(suffix=".hwpx")
        convert(hwp, out)
        got = unzip_parts(out)["META-INF/container.xml"]
        want = unzip_parts(ref)["META-INF/container.xml"]
        assert got == want, "container.xml mismatch for sample %s" % n


@pytest.mark.sample_free
def test_container_rdf_multi_section_unit():
    from hwp2hwpx.owpml.package_parts import container_rdf

    rdf = container_rdf(2).decode("utf-8")
    assert 'rdf:about="Contents/section0.xml"' in rdf
    assert 'rdf:about="Contents/section1.xml"' in rdf
    assert rdf.count("#SectionFile") == 2
    assert rdf.count("#Document") == 1
