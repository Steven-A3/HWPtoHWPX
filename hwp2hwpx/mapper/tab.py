"""Map HWP tab definitions to OWPML tab definitions."""
from ..owpml.model import TabDef, TabItem

_TYPE = {"left": "LEFT", "right": "RIGHT", "center": "CENTER", "decimal": "DECIMAL"}
_LEADER = {0: "NONE", 1: "DOT", 2: "DASH", 3: "DASH", 4: "DASHDOT"}


def map_tab_defs(tab_defs):
    out = []
    for td in tab_defs:
        items = [TabItem(
            pos=t.pos,
            type=_TYPE.get((t.kind or "left").lower(), "LEFT"),
            leader=_LEADER.get(t.fill_type, "NONE"),
        ) for t in td.tabs]
        out.append(TabDef(
            id=td.index,
            auto_tab_left=td.auto_tab_left,
            auto_tab_right=td.auto_tab_right,
            tabs=items,
        ))
    return out
