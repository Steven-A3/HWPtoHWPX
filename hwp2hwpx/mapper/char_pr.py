"""Map HWP character shapes to OWPML charPr."""
from ..owpml.model import CharPr

# HWP language key -> OWPML language key.
_LANG_MAP = {
    "ko": "hangul", "en": "latin", "cn": "hanja", "jp": "japanese",
    "other": "other", "symbol": "symbol", "user": "user",
}


def _translate(d, default):
    """HWP-keyed per-language dict -> OWPML-keyed dict."""
    return {owpml: d.get(hwp, default) for hwp, owpml in _LANG_MAP.items()}


def _shade_color(v):
    """HWP shade-color #ffffff (or empty) -> OWPML 'none'; else passthrough."""
    if not v or v.lower() in ("#ffffff", "none"):
        return "none"
    return v


def map_char_shapes(shapes):
    out = []
    for cs in shapes:
        out.append(CharPr(
            id=cs.index,
            height=cs.base_size,
            text_color=cs.text_color,
            font_ref_id=cs.font_id,
            bold=cs.bold,
            italic=cs.italic,
            font_ref=_translate(cs.font_ref, 0),
            ratio=_translate(cs.ratio, 100),
            spacing=_translate(cs.spacing, 0),
            rel_sz=_translate(cs.rel_sz, 100),
            offset=_translate(cs.offset, 0),
            shade_color=_shade_color(cs.shade_color),
            border_fill_id=1,
            underline_type=cs.underline_type,
            underline_shape=cs.underline_shape,
            underline_color=cs.underline_color,
            strikeout_shape=cs.strikeout_shape,
            strikeout_color=cs.strikeout_color,
            outline_type=cs.outline_type,
            shadow_type=cs.shadow_type,
            shadow_color=cs.shadow_color,
            shadow_offset_x=cs.shadow_offset_x,
            shadow_offset_y=cs.shadow_offset_y,
            subscript=cs.subscript,
            superscript=cs.superscript,
        ))
    return out
