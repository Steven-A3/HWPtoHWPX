"""Map HWP document-level settings to OWPML header elements."""
from ..owpml.model import BeginNum, CompatDocument

_TARGET_PROGRAM = {0: "HWP201X"}   # observed; default HWP201X


def map_begin_num(dp):
    if dp is None:
        return BeginNum()
    return BeginNum(page=dp.page_start, footnote=dp.footnote_start,
                    endnote=dp.endnote_start, pic=dp.pic_start,
                    tbl=dp.tbl_start, equation=dp.equation_start)


def map_compat(c):
    if c is None:
        return CompatDocument()
    return CompatDocument(
        target_program=_TARGET_PROGRAM.get(c.target, "HWP201X"))
