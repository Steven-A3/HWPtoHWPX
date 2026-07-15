"""Structural diff + per-element fidelity scoring between our HWPX and Hancom's."""
from collections import Counter
from lxml import etree
from .xmlnorm import unzip_parts


def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def element_counts(xml_bytes):
    root = etree.fromstring(xml_bytes)
    counts = Counter()
    for el in root.iter():
        counts[_local(el.tag)] += 1
    # Do not count the root itself as content.
    counts[_local(root.tag)] -= 1
    if counts[_local(root.tag)] <= 0:
        del counts[_local(root.tag)]
    return dict(counts)


def score_part(ours, theirs):
    oc = element_counts(ours)
    tc = element_counts(theirs)
    total = sum(tc.values())
    matched = sum(min(oc.get(k, 0), v) for k, v in tc.items())
    missing = {k: v - oc.get(k, 0) for k, v in tc.items() if v - oc.get(k, 0) > 0}
    match = (matched / total) if total else 1.0
    return {"match": match, "our_counts": oc, "their_counts": tc, "missing": missing}


def report(our_hwpx, their_hwpx):
    ours = unzip_parts(our_hwpx)
    theirs = unzip_parts(their_hwpx)
    lines = []
    for part in ("Contents/header.xml", "Contents/section0.xml"):
        if part not in ours or part not in theirs:
            lines.append("%s: MISSING (ours=%s theirs=%s)"
                         % (part, part in ours, part in theirs))
            continue
        s = score_part(ours[part], theirs[part])
        lines.append("%s: match=%.1f%%" % (part, s["match"] * 100))
        top = sorted(s["missing"].items(), key=lambda kv: -kv[1])[:8]
        for tag, n in top:
            lines.append("    missing %-16s x%d" % (tag, n))
    return "\n".join(lines)
