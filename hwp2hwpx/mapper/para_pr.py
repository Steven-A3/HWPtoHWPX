"""Map HWP paragraph shapes to OWPML paraPr."""
from ..owpml.model import ParaPr

_LS_TYPE = {"ratio": "PERCENT", "fixed": "FIXED",
            "atleast": "AT_LEAST", "at-least": "AT_LEAST"}


def _half(v):
    """Halve toward zero, preserving sign (HWP stores margins doubled)."""
    return -((-v) // 2) if v < 0 else v // 2


def map_para_shapes(shapes):
    out = []
    for s in shapes:
        out.append(ParaPr(
            id=s.index,
            align=s.align,
            heading_type="NONE",
            heading_level=s.level,
            intent=_half(s.indent),
            margin_left=_half(s.margin_left),
            margin_right=_half(s.margin_right),
            margin_prev=_half(s.margin_top),
            margin_next=_half(s.margin_bottom),
            line_spacing=s.line_spacing,
            line_spacing_type=_LS_TYPE.get((s.line_spacing_type or "ratio").lower(),
                                           "PERCENT"),
            border_fill_id=s.border_fill_id if s.border_fill_id >= 1 else 1,
            tab_pr_id=0,
        ))
    return out
