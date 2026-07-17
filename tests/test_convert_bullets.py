"""Bullets milestone: the IdMappings/Bullet record becomes an <hh:bullets>
block in refList, between <hh:tabProperties> and <hh:paraProperties>."""
import glob
import re
from lxml import etree

from hwp2hwpx.hwpmodel.model import HwpBullet
from hwp2hwpx.hwpmodel.reader import _parse_bullets, read_docinfo, hwp5_xml
from hwp2hwpx.owpml.model import Bullet
from hwp2hwpx.mapper.bullet import map_bullets
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S3 = glob.glob("samples/3.*.hwp")[0]
S3_REF = glob.glob("samples/3.*.hwpx")[0]
S4 = glob.glob("samples/4.*.hwp")[0]
S4_REF = glob.glob("samples/4.*.hwpx")[0]

# The exact block Hancom writes for sample 3's single bullet definition.
HANCOM_BULLETS = (
    '<hh:bullets itemCnt="1"><hh:bullet id="1" char="-" useImage="0">'
    '<hh:paraHead level="0" align="LEFT" useInstWidth="0" autoIndent="1" '
    'widthAdjust="0" textOffsetType="PERCENT" textOffset="50" '
    'numFormat="DIGIT" charPrIDRef="4294967295" checkable="0"/>'
    '</hh:bullet></hh:bullets>'
)


# ---- reader ---------------------------------------------------------------

def _id_mappings(inner):
    return etree.fromstring("<IdMappings>" + inner + "</IdMappings>")


def test_reader_parses_bullet_record():
    idm = _id_mappings('<Bullet align="left" auto-indent="1" char="-" '
                       'charshape-id="-1" flags="00000008" space="50" width="0"/>')
    assert _parse_bullets(idm) == [HwpBullet(
        char="-", align="left", auto_indent=1, text_offset=50,
        width_adjust=0, char_shape_id=-1)]


def test_reader_no_bullet_record_yields_empty_list():
    assert _parse_bullets(_id_mappings("")) == []


def test_sample3_docinfo_has_one_bullet():
    di = read_docinfo(hwp5_xml(S3))
    assert di.bullets == [HwpBullet(
        char="-", align="left", auto_indent=1, text_offset=50,
        width_adjust=0, char_shape_id=-1)]


def test_sample4_docinfo_has_no_bullets():
    assert read_docinfo(hwp5_xml(S4)).bullets == []


# ---- mapper ---------------------------------------------------------------

def test_mapper_maps_bullet_with_sentinel_char_pr():
    # charshape-id -1 ("none") becomes OWPML's unsigned-32-bit spelling.
    out = map_bullets([HwpBullet(char="-", align="left", auto_indent=1,
                                 text_offset=50, width_adjust=0,
                                 char_shape_id=-1)])
    assert out == [Bullet(id=1, char="-", use_image=0, align="LEFT",
                          auto_indent=1, width_adjust=0, text_offset=50,
                          char_pr_id=4294967295)]


def test_mapper_ids_are_one_based_and_align_maps():
    out = map_bullets([HwpBullet(align="left"), HwpBullet(align="center")])
    assert [b.id for b in out] == [1, 2]
    assert [b.align for b in out] == ["LEFT", "CENTER"]


def test_mapper_keeps_real_char_shape_id():
    assert map_bullets([HwpBullet(char_shape_id=7)])[0].char_pr_id == 7


# ---- writer ---------------------------------------------------------------

def _header_xml(tmp_path, hwp):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return unzip_parts(str(out))["Contents/header.xml"].decode("utf-8")


def test_writer_emits_hancom_exact_bullets_block(tmp_path):
    assert HANCOM_BULLETS in _header_xml(tmp_path, S3)


def test_writer_places_bullets_between_tabs_and_paras(tmp_path):
    xml = _header_xml(tmp_path, S3)
    order = [m.group(1) for m in re.finditer(
        r"<hh:(tabProperties|bullets|paraProperties)\b", xml)]
    assert order == ["tabProperties", "bullets", "paraProperties"]


def test_writer_omits_bullets_when_none(tmp_path):
    # Hancom writes no container at all for a document without bullets.
    assert "<hh:bullets" not in _header_xml(tmp_path, S4)


# ---- end-to-end fidelity --------------------------------------------------

def _header_score(hwp, ref, tmp_path):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return score_part(unzip_parts(str(out))["Contents/header.xml"],
                      unzip_parts(ref)["Contents/header.xml"])


def test_sample3_header_bullet_gap_closed(tmp_path):
    s = _header_score(S3, S3_REF, tmp_path)
    assert s["missing"].get("bullets", 0) == 0
    assert s["missing"].get("bullet", 0) == 0
    assert s["missing"].get("paraHead", 0) == 0
    # substFont is the documented non-goal; nothing else may remain.
    assert {k: v for k, v in s["missing"].items() if v} == {"substFont": 3}


def test_sample4_header_unaffected(tmp_path):
    s = _header_score(S4, S4_REF, tmp_path)
    assert {k: v for k, v in s["missing"].items() if v} == {"substFont": 29}
