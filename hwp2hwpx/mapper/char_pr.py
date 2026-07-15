"""Map HWP character shapes to OWPML charPr."""
from ..owpml.model import CharPr


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
        ))
    return out
