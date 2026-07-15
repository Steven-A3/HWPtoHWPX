"""Map HWP border/fill definitions to OWPML borderFills."""
from ..owpml.model import Border, BorderFill


def _norm_width(w):
    w = (w or "0.1mm").strip()
    if w.endswith("mm") and not w.endswith(" mm"):
        w = w[:-2].rstrip() + " mm"
    return w


def map_border_fills(hwp_bfs):
    out = []
    for bf in hwp_bfs:
        borders = [Border(
            kind=b.kind,
            type=(b.stroke_type or "none").upper(),
            width=_norm_width(b.width),
            color=b.color or "#000000",
        ) for b in bf.borders]
        out.append(BorderFill(id=bf.index, borders=borders, fill_color=bf.fill_color))
    return out
