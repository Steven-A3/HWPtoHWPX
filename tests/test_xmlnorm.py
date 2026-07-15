from hwp2hwpx.fidelity.xmlnorm import canonical, unzip_parts


def test_canonical_ignores_attr_order_and_ws():
    a = b'<r><a x="1"  y="2">  t </a></r>'
    b = b'<r>\n  <a y="2" x="1">  t </a>\n</r>'
    assert canonical(a) == canonical(b)


def test_canonical_detects_real_difference():
    a = b'<r><a x="1"/></r>'
    b = b'<r><a x="2"/></r>'
    assert canonical(a) != canonical(b)


def test_unzip_parts_reads_sample(tmp_path):
    parts = unzip_parts("samples/3.과업지시서_070.hwpx")
    assert "Contents/section0.xml" in parts
    assert parts["mimetype"] == b"application/hwp+zip"
