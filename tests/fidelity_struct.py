"""Structural paragraph differ + score-floor helper for fidelity gates.

Not a test module itself (no ``test_`` functions) — imported by the gate
tests to compare our converted HWPX output against Hancom's reference on a
per-paragraph, structural basis (run / <t> emptiness / object-sequence
shape), and to pull the per-tag ``missing`` counts used for the score-floor
assertion.
"""
import tempfile
from typing import List, Optional

from lxml import etree

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

ln = lambda e: etree.QName(e).localname


def _para_sig(p):
    """Per direct-child run: (charPrIDRef, [child-kinds]); text -> 't' (nonempty) / 't0' (empty)."""
    runs = []
    for r in p:
        if ln(r) != 'run':
            continue
        seq = []
        for c in r:
            l = ln(c)
            if l == 't':
                empty = not (c.text or '').strip() and len(c) == 0
                seq.append('t0' if empty else 't')
            else:
                seq.append(l)
        runs.append((r.get('charPrIDRef'), seq))
    return runs


def _top_paras(root):
    return [e for e in root if ln(e) == 'p']  # direct <hp:p> children of the section root


def _all_paras(root):
    # every <hp:p> in document order, including ones nested in table cells /
    # drawing text-boxes (root.iter() is a document-order preorder walk)
    return [e for e in root.iter() if ln(e) == 'p']


def _paragraph_divergences(our_section_xml: bytes, their_section_xml: bytes, paras_fn) -> List[dict]:
    our_root = etree.fromstring(our_section_xml)
    their_root = etree.fromstring(their_section_xml)
    our_paras = paras_fn(our_root)
    their_paras = paras_fn(their_root)

    divergences = []
    for i in range(max(len(our_paras), len(their_paras))):
        our_p = our_paras[i] if i < len(our_paras) else None
        their_p = their_paras[i] if i < len(their_paras) else None

        our_sig = _para_sig(our_p) if our_p is not None else None
        their_sig = _para_sig(their_p) if their_p is not None else None

        our_seqs = [seq for _, seq in our_sig] if our_sig is not None else None
        their_seqs = [seq for _, seq in their_sig] if their_sig is not None else None

        if our_seqs != their_seqs:
            divergences.append({
                "index": i,
                "ours": our_sig,
                "theirs": their_sig,
            })
    return divergences


def paragraph_divergences(our_section_xml: bytes, their_section_xml: bytes) -> List[dict]:
    """Compare top-level paragraphs by index; return the ones whose run/child-kind
    structure differs (charPrIDRef value is score-invisible and ignored)."""
    return _paragraph_divergences(our_section_xml, their_section_xml, _top_paras)


def all_paragraph_divergences(our_section_xml: bytes, their_section_xml: bytes) -> List[dict]:
    """Like paragraph_divergences, but over every <hp:p> in document order —
    including ones nested inside table cells and drawing text-boxes, not just
    the section root's direct children."""
    return _paragraph_divergences(our_section_xml, their_section_xml, _all_paras)


def section_scores(hwp_path: str, ref_path: str) -> Optional[dict]:
    """Convert hwp_path, then return score_part(...)["missing"] for section0
    against ref_path's reference section0."""
    out_path = tempfile.mktemp(suffix=".hwpx")
    convert(hwp_path, out_path)
    ours = unzip_parts(out_path)
    theirs = unzip_parts(ref_path)
    part = "Contents/section0.xml"
    if part not in ours or part not in theirs:
        return None
    return score_part(ours[part], theirs[part])["missing"]
