"""Map HWP border/fill definitions to OWPML borderFills."""
from ..owpml.model import Border, BorderFill, Gradation

# HWP gradation kind -> OWPML numFormat. "circular" maps to RADIAL (verified
# against the sample); others follow the OWPML enum.
_GRAD_TYPE = {"linear": "LINEAR", "circular": "RADIAL", "conical": "CONICAL",
              "square": "SQUARE"}


def _norm_width(w):
    w = (w or "0.1mm").strip()
    if w.endswith("mm") and not w.endswith(" mm"):
        w = w[:-2].rstrip() + " mm"
    return w


def _map_gradation(g):
    if g is None:
        return None
    return Gradation(
        type=_GRAD_TYPE.get((g.type or "linear").lower(), "LINEAR"),
        angle=g.angle,
        center_x=g.center_x,
        center_y=g.center_y,
        step=g.step,
        colors=[(c or "#000000").upper() for c in g.colors],
    )


def map_border_fills(hwp_bfs):
    out = []
    for bf in hwp_bfs:
        borders = [Border(
            kind=b.kind,
            type=(b.stroke_type or "none").upper(),
            width=_norm_width(b.width),
            color=b.color or "#000000",
        ) for b in bf.borders]
        out.append(BorderFill(id=bf.index + 1, borders=borders,
                              fill_color=bf.fill_color,
                              gradation=_map_gradation(bf.gradation)))
    return out
