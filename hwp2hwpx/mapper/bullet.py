"""Map HWP bullet definitions to OWPML bullet definitions."""
from ..owpml.model import Bullet

_ALIGN = {"left": "LEFT", "center": "CENTER", "right": "RIGHT"}

# HWP stores "no char shape" as -1; OWPML spells the same sentinel as the
# unsigned 32-bit equivalent.
_NO_CHAR_PR = 4294967295


def map_bullets(bullets):
    out = []
    for i, b in enumerate(bullets):
        out.append(Bullet(
            id=i + 1,
            char=b.char,
            align=_ALIGN.get((b.align or "left").lower(), "LEFT"),
            auto_indent=b.auto_indent,
            width_adjust=b.width_adjust,
            text_offset=b.text_offset,
            char_pr_id=_NO_CHAR_PR if b.char_shape_id < 0 else b.char_shape_id,
        ))
    return out
