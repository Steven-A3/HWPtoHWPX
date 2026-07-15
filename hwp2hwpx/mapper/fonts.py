"""Map HWP fonts to OWPML fontfaces."""
from ..owpml.model import Font


def map_fonts(hwp_fonts):
    return {"HANGUL": [Font(id=f.index, face=f.name) for f in hwp_fonts]}
