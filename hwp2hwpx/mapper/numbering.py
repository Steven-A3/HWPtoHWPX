"""Map HWP paragraph-numbering definitions to OWPML numbering definitions.

HWP stores up to 7 numbering levels; OWPML requires 10 <hh:paraHead> per
numbering, so Hancom pads levels 8-10 with fixed defaults -- we reproduce that.
"""
from ..owpml.model import ParaNumbering, NumHead

_ALIGN = {"left": "LEFT", "center": "CENTER", "right": "RIGHT"}
_NO_CHAR_PR = 4294967295
_OWPML_LEVELS = 10

# HWP number-shape enum -> OWPML numFormat. The format is packed into the
# level flags at bits [5..9]: (flags >> 5) & 0x1F. Values 0/1/8 are verified
# against the sample (DIGIT/CIRCLED_DIGIT/HANGUL_SYLLABLE); the rest follow the
# HWP 5.0 enum order. Unknown values fall back to DIGIT.
_NUM_FORMAT = {
    0: "DIGIT", 1: "CIRCLED_DIGIT", 2: "ROMAN_CAPITAL", 3: "ROMAN_SMALL",
    4: "LATIN_CAPITAL", 5: "LATIN_SMALL", 6: "CIRCLED_LATIN_CAPITAL",
    7: "CIRCLED_LATIN_SMALL", 8: "HANGUL_SYLLABLE",
    9: "CIRCLED_HANGUL_SYLLABLE", 10: "HANGUL_JAMO",
}


def _num_format(flags):
    return _NUM_FORMAT.get((flags >> 5) & 0x1F, "DIGIT")


def _padding_head(level):
    # Hancom's synthetic levels 8-10: no text, no instance width, DIGIT.
    return NumHead(level=level, align="LEFT", use_inst_width=0, auto_indent=0,
                   width_adjust=0, text_offset=0, num_format="DIGIT",
                   char_pr_id=0, checkable=0, text="")


def map_numberings(numberings):
    out = []
    for i, nm in enumerate(numberings):
        heads = []
        for j, lv in enumerate(nm.levels):
            heads.append(NumHead(
                level=j + 1,
                align=_ALIGN.get((lv.align or "left").lower(), "LEFT"),
                use_inst_width=lv.auto_width,
                auto_indent=lv.auto_indent,
                width_adjust=lv.width_adjust,
                text_offset=lv.text_offset,
                num_format=_num_format(lv.flags),
                char_pr_id=_NO_CHAR_PR if lv.char_shape_id < 0 else lv.char_shape_id,
                checkable=0,
                text=lv.text,
            ))
        for level in range(len(heads) + 1, _OWPML_LEVELS + 1):
            heads.append(_padding_head(level))
        out.append(ParaNumbering(id=i + 1, start=nm.start, heads=heads))
    return out
