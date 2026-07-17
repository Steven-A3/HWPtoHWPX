"""Inject markpen (text-highlighter) markers into a paragraph's OWPML runs.

HWP stores highlighting as range-tag spans over paragraph character offsets
(kind=2). This walks the already-mapped OWPML runs, tracks a cumulative char
offset (a Text contributes its code-unit length, a Control contributes 1), and
inserts MarkpenBegin/MarkpenEnd markers at the span endpoints. At an item
boundary a begin leads the following item and an end trails the preceding one;
strictly inside a Text the string is split. Paragraphs containing a table or
drawing run are skipped (their runs have no text and no reliable char width)."""
from collections import defaultdict
from ..owpml.model import Text, MarkpenBegin, MarkpenEnd


def _has_non_text_run(runs):
    return any(getattr(r, "table", None) is not None
               or getattr(r, "drawing", None) is not None for r in runs)


def apply_markpens(runs, markpens):
    if not markpens or _has_non_text_run(runs):
        return runs
    begins = defaultdict(list)   # offset -> [color, ...]
    ends = defaultdict(int)      # offset -> count
    for mp in markpens:
        begins[mp.start].append(mp.color)
        ends[mp.end] += 1

    offset = 0
    for r in runs:
        new_texts = []
        for it in r.texts:
            width = len(it.content) if isinstance(it, Text) else 1
            # begins at the item-start gap lead this item
            for color in begins.pop(offset, []):
                new_texts.append(MarkpenBegin(color=color))
            if isinstance(it, Text):
                s = it.content
                prev = 0
                for k in range(1, width):        # strictly-internal gaps
                    g = offset + k
                    if g in ends or g in begins:
                        if k > prev:
                            new_texts.append(Text(s[prev:k]))
                        prev = k
                        for _ in range(ends.pop(g, 0)):
                            new_texts.append(MarkpenEnd())
                        for color in begins.pop(g, []):
                            new_texts.append(MarkpenBegin(color=color))
                if width > prev:
                    new_texts.append(Text(s[prev:]))
            else:
                new_texts.append(it)
            offset += width
            # ends at the item-end gap trail this item
            for _ in range(ends.pop(offset, 0)):
                new_texts.append(MarkpenEnd())
        r.texts = new_texts
    return runs
