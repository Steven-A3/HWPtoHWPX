import glob
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]
S4_REF = glob.glob("samples/4.*.hwpx")[0]


def test_markpen_markers_leave_section_miss_list(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    assert missing.get("markpenBegin", 0) == 0
    assert missing.get("markpenEnd", 0) == 0


def test_markpen_exact_serialization_of_known_run(tmp_path):
    # The highlighted run for "계약체결 ... 준공" must serialize exactly as Hancom does.
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    xml = unzip_parts(str(out))["Contents/section0.xml"].decode("utf-8")
    assert ('<hp:markpenBegin color="#FFFFFF"/>계약체결 및 이행 등의 과정(준공'
            '<hp:markpenEnd/>') in xml


def test_section_match_rises_sample4(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    assert score_part(ours, theirs)["match"] > 0.992


def test_sample3_section_unchanged(tmp_path):
    # Sample 3 has no markpen. Baseline refreshed for the inline-object empty-<hp:t>
    # milestone (adds 33 inline-table anchor <hp:t>): sha256 022bef521a01b5c1,
    # len 496827. Still guards that markpen itself makes no further change.
    out = tmp_path / "s3.hwpx"
    convert(S3, str(out))
    body = unzip_parts(str(out))["Contents/section0.xml"]
    import hashlib
    assert len(body) == 496827
    assert hashlib.sha256(body).hexdigest().startswith("022bef521a01b5c1")
