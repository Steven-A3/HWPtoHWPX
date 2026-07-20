"""Numbering subsystem: the IdMappings/Numbering record becomes an
<hh:numberings> block in refList (between tabProperties and bullets/
paraProperties). Source has up to 7 levels; OWPML pads to 10 paraHeads."""
import re

import pytest

from hwp2hwpx.hwpmodel.model import HwpNumbering, HwpNumberingLevel
from hwp2hwpx.hwpmodel.reader import _parse_numberings, read_docinfo, hwp5_xml
from hwp2hwpx.owpml.model import ParaNumbering, NumHead
from hwp2hwpx.mapper.numbering import map_numberings, _num_format
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.samplepaths import hwp as _hwp, hwpx as _hwpx

S2013 = _hwp("2013")
S2013_REF = _hwpx("2013")
S3 = _hwp("3.")
S3_REF = _hwpx("3.")
S4 = _hwp("4.")
S4_REF = _hwpx("4.")

from lxml import etree


def _id_mappings(inner):
    return etree.fromstring("<IdMappings>" + inner + "</IdMappings>")


# ---- reader ---------------------------------------------------------------

@pytest.mark.sample_free
def test_reader_parses_numbering_levels():
    idm = _id_mappings(
        '<Numbering starting-number="0"><Array name="levels">'
        '<NumberingLevel align="left" auto-indent="1" auto-width="1" '
        'charshape-id="-1" flags="0000000C" numbering-format="^1." '
        'space="50" width-correction="0"/>'
        '<NumberingLevel align="left" auto-indent="1" auto-width="1" '
        'charshape-id="-1" flags="0000010C" numbering-format="^2." '
        'space="50" width-correction="0"/>'
        '</Array></Numbering>')
    out = _parse_numberings(idm)
    assert len(out) == 1
    assert out[0].start == 0
    assert len(out[0].levels) == 2
    assert out[0].levels[0] == HwpNumberingLevel(
        align="left", auto_width=1, auto_indent=1, text_offset=50,
        width_adjust=0, char_shape_id=-1, flags=0x0C, text="^1.")


@pytest.mark.sample_free
def test_reader_no_numbering_yields_empty():
    assert _parse_numberings(_id_mappings("")) == []


def test_sample2013_docinfo_has_numbering_with_7_levels():
    di = read_docinfo(hwp5_xml(S2013))
    assert len(di.numberings) == 1
    assert len(di.numberings[0].levels) == 7
    assert di.numberings[0].levels[0].text == "^1."


def test_samples_3_4_have_no_numbering():
    assert read_docinfo(hwp5_xml(S3)).numberings == []
    assert read_docinfo(hwp5_xml(S4)).numberings == []


# ---- mapper ---------------------------------------------------------------

@pytest.mark.sample_free
def test_num_format_decode_verified_values():
    # (flags >> 5) & 0x1F, verified against the sample.
    assert _num_format(0x0C) == "DIGIT"
    assert _num_format(0x10C) == "HANGUL_SYLLABLE"
    assert _num_format(0x2C) == "CIRCLED_DIGIT"


@pytest.mark.sample_free
def test_mapper_pads_to_ten_levels_with_defaults():
    src = [HwpNumbering(start=0, levels=[
        HwpNumberingLevel(align="left", auto_width=1, auto_indent=1,
                          text_offset=50, width_adjust=0, char_shape_id=-1,
                          flags=0x0C, text="^1.")])]
    out = map_numberings(src)
    assert len(out) == 1
    assert out[0].id == 1 and out[0].start == 0
    assert len(out[0].heads) == 10
    # real level 1
    assert out[0].heads[0] == NumHead(
        level=1, align="LEFT", use_inst_width=1, auto_indent=1, width_adjust=0,
        text_offset=50, num_format="DIGIT", char_pr_id=4294967295,
        checkable=0, text="^1.")
    # synthetic padding level 8
    assert out[0].heads[7] == NumHead(
        level=8, align="LEFT", use_inst_width=0, auto_indent=0, width_adjust=0,
        text_offset=0, num_format="DIGIT", char_pr_id=0, checkable=0, text="")


# ---- writer / end-to-end --------------------------------------------------

def _header(hwp, tmp_path):
    out = tmp_path / "o.hwpx"
    convert(hwp, str(out))
    return unzip_parts(str(out))["Contents/header.xml"].decode("utf-8")


def test_writer_numbering_matches_hancom_except_l7_checkable(tmp_path):
    # The whole <hh:numberings> block is byte-identical to Hancom's EXCEPT
    # level 7's checkable="1" -- that bit is not separable from numFormat in the
    # exposed source flags, so we keep the semantically-correct checkable="0"
    # (a single score-neutral attribute; documented residual). Everything else
    # -- 10 paraHeads, numFormat decode, ^N text, level-8..10 padding -- matches.
    ours = re.search(r"<hh:numberings.*?</hh:numberings>",
                     _header(S2013, tmp_path), re.S).group(0)
    theirs = re.search(r"<hh:numberings.*?</hh:numberings>",
                       unzip_parts(S2013_REF)["Contents/header.xml"].decode("utf-8"),
                       re.S).group(0)
    assert ours == theirs.replace('level="7" align="LEFT" useInstWidth="1" '
                                  'autoIndent="1" widthAdjust="0" '
                                  'textOffsetType="PERCENT" textOffset="50" '
                                  'numFormat="CIRCLED_DIGIT" '
                                  'charPrIDRef="4294967295" checkable="1"',
                                  'level="7" align="LEFT" useInstWidth="1" '
                                  'autoIndent="1" widthAdjust="0" '
                                  'textOffsetType="PERCENT" textOffset="50" '
                                  'numFormat="CIRCLED_DIGIT" '
                                  'charPrIDRef="4294967295" checkable="0"')


def test_writer_numbering_slot_and_counts(tmp_path):
    xml = _header(S2013, tmp_path)
    order = [m.group(1) for m in re.finditer(
        r"<hh:(tabProperties|numberings|bullets|paraProperties)\b", xml)]
    assert order == ["tabProperties", "numberings", "paraProperties"]
    block = re.search(r"<hh:numberings.*?</hh:numberings>", xml, re.S).group(0)
    assert 'itemCnt="1"' in re.match(r"<hh:numberings[^>]*>", block).group(0)
    assert block.count("<hh:paraHead") == 10
    assert '<hh:numbering id="1" start="0">' in block
    # DIGIT/HANGUL_SYLLABLE alternation from the decode, and a padding level
    assert 'numFormat="HANGUL_SYLLABLE"' in block
    assert ('level="8" align="LEFT" useInstWidth="0" autoIndent="0" '
            'widthAdjust="0" textOffsetType="PERCENT" textOffset="0" '
            'numFormat="DIGIT" charPrIDRef="0" checkable="0"/>') in block


def test_sample2013_numbering_gap_closed(tmp_path):
    out = tmp_path / "o.hwpx"
    convert(S2013, str(out))
    s = score_part(unzip_parts(str(out))["Contents/header.xml"],
                   unzip_parts(S2013_REF)["Contents/header.xml"])
    for tag in ("numberings", "numbering", "paraHead"):
        assert s["missing"].get(tag, 0) == 0


def test_writer_omits_numberings_when_none(tmp_path):
    assert "<hh:numberings" not in _header(S3, tmp_path)
    assert "<hh:numberings" not in _header(S4, tmp_path)


def test_samples_3_4_header_unaffected(tmp_path):
    for hwp, ref in ((S3, S3_REF), (S4, S4_REF)):
        out = tmp_path / "o.hwpx"
        convert(hwp, str(out))
        s = score_part(unzip_parts(str(out))["Contents/header.xml"],
                       unzip_parts(ref)["Contents/header.xml"])
        assert {k: v for k, v in s["missing"].items() if v and k != "substFont"} == {}
