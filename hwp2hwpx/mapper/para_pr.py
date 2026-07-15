"""Map HWP paragraph shapes to OWPML paraPr."""
from ..owpml.model import ParaPr


def map_para_shapes(shapes):
    return [ParaPr(id=s.index, align=s.align) for s in shapes]
