"""Map HWP fonts to OWPML fontfaces."""
from ..owpml.model import Font

# charPr/fontRef sets all 7 OWPML language attributes (hangul/latin/hanja/
# japanese/other/symbol/user). header_writer emits one <hh:fontface lang=...>
# bucket per key here, so every language must have a bucket or its fontRef
# dangles. We don't yet distinguish per-language fonts, so every bucket gets
# the same font list.
_LANGS = ["HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER"]


def map_fonts(hwp_fonts):
    fonts = [Font(id=f.index, face=f.name) for f in hwp_fonts]
    return {lang: list(fonts) for lang in _LANGS}
