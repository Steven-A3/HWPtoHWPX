"""Map HWP styles to OWPML styles."""
from ..owpml.model import Style


def _type(kind):
    return "CHAR" if (kind or "").lower().startswith("char") else "PARA"


def map_styles(styles):
    out = []
    for s in styles:
        out.append(Style(
            id=s.index,
            type=_type(s.kind),
            name=s.local_name,
            eng_name=s.eng_name,
            para_pr_id=s.para_shape_id,
            char_pr_id=s.char_shape_id,
            next_style_id=s.next_style_id,
            lang_id=s.lang_id,
            lock_form="0",
        ))
    return out
