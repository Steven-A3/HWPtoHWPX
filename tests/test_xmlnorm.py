import pytest

from hwp2hwpx.fidelity.xmlnorm import canonical, unzip_parts
from tests.samplepaths import S3_REF


@pytest.mark.sample_free
def test_canonical_ignores_attr_order_and_ws():
    a = b'<r><a x="1"  y="2">  t </a></r>'
    b = b'<r>\n  <a y="2" x="1">  t </a>\n</r>'
    assert canonical(a) == canonical(b)


@pytest.mark.sample_free
def test_canonical_detects_real_difference():
    a = b'<r><a x="1"/></r>'
    b = b'<r><a x="2"/></r>'
    assert canonical(a) != canonical(b)


def test_unzip_parts_reads_sample(tmp_path):
    parts = unzip_parts(S3_REF)
    assert "Contents/section0.xml" in parts
    assert parts["mimetype"] == b"application/hwp+zip"
