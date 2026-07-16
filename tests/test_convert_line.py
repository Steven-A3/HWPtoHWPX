# tests/test_convert_line.py
import zipfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S4 = "samples/4.제안요청서_070.hwp"
S4_REF = "samples/4.제안요청서_070.hwpx"
S3 = "samples/3.과업지시서_070.hwp"
S3_REF = "samples/3.과업지시서_070.hwpx"


def _section0(hwp, tmp_path, name):
    out = tmp_path / name
    convert(hwp, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def test_sample4_emits_six_lines(tmp_path):
    sec = _section0(S4, tmp_path, "s4.hwpx")
    assert sec.count("<hp:line ") == 6


def test_sample4_line_container_tags_shrink_in_miss_list(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    # line + its container tags must no longer be fully missing (>=6 each before)
    for tag in ("line", "lineShape", "startPt", "endPt"):
        assert missing.get(tag, 0) == 0, "%s still missing x%d" % (tag, missing.get(tag, 0))
    # common-container tags shared with the 3 pictures drop from x9 to <=3
    for tag in ("curSz", "flip", "rotationInfo", "renderingInfo"):
        assert missing.get(tag, 0) <= 3


def test_sample4_section0_match_rose(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    # baseline before this milestone was 0.9677; lines lift it further
    assert score_part(ours, theirs)["match"] > 0.975


def test_sample3_unchanged_no_line(tmp_path):
    sec = _section0(S3, tmp_path, "s3.hwpx")
    assert sec.count("<hp:line ") == 0
    # no part of the drawing subtree may leak into a drawing-free document
    for tag in ("<hp:orgSz", "<hp:curSz", "<hp:rotationInfo", "<hp:renderingInfo",
                "<hp:lineShape", "<hc:startPt", "<hc:endPt"):
        assert sec.count(tag) == 0, "%s leaked into sample 3" % tag
