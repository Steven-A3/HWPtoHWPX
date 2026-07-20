from hwp2hwpx.hwpmodel.reader import hwp5_xml
from lxml import etree
from tests.samplepaths import S3

SAMPLE = S3


def test_dump_is_wellformed_xml():
    xml = hwp5_xml(SAMPLE)
    root = etree.fromstring(xml)
    # pyhwp wraps the document tree in a root element; it must parse and be non-empty.
    assert len(root) > 0
