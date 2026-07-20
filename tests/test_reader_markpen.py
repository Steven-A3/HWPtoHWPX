import glob
from hwp2hwpx.hwpmodel import rangetags
from hwp2hwpx.hwpmodel.model import HwpRangeTag
from hwp2hwpx.hwpmodel.reader import read_document, hwp5_xml
from hwp2hwpx.hwpmodel.rangetags import extract_markpens, attach_range_tags

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]


def test_sample4_yields_five_white_markpen_spans():
    secs = extract_markpens(S4)
    spans = [s for buckets, _ in secs for lst in buckets.values() for s in lst]
    assert len(spans) == 5
    assert all(s.color == "#FFFFFF" for s in spans)


def test_sample3_has_no_markpen():
    secs = extract_markpens(S3)
    assert all(len(buckets) == 0 for buckets, _ in secs)


def test_attach_lands_on_correct_paragraphs():
    doc = read_document(hwp5_xml(S4))
    attach_range_tags(S4, doc)
    flat = list(_dfs(doc.sections[0].paragraphs))
    highlighted_idx = [i for i, p in enumerate(flat) if p.markpens]
    # dfs paragraph indices, not sample text (samples/ is git-ignored and no
    # document text may be committed) -- pins the same two paragraphs the
    # original text-prefix assertions targeted, so an off-by-one or wrong-
    # section indexing bug in attach_range_tags still fails this.
    assert highlighted_idx == [420, 421]
    assert sum(len(p.markpens) for p in flat) == 5


def test_attach_is_fail_safe_when_binmodel_unavailable(tmp_path):
    doc = read_document(hwp5_xml(S4))
    # a non-HWP path must not raise and must leave markpens empty
    attach_range_tags(str(tmp_path / "nope.hwp"), doc)
    assert all(not p.markpens for p in _dfs(doc.sections[0].paragraphs))


def test_attach_skips_section_on_paragraph_count_mismatch(monkeypatch):
    doc = read_document(hwp5_xml(S4))
    flat = list(_dfs(doc.sections[0].paragraphs))
    # A bucket at a perfectly valid low index (max(buckets) < len(flat), so
    # the old bounds-only guard would let this through), but the reported
    # binmodel paragraph count disagrees with the parsed-tree DFS count --
    # simulating binmodel-only nested paragraphs (header/footer/footnote/
    # endnote/textbox controls) that the xml-based parser skips.
    fake_buckets = {0: [HwpRangeTag(start=0, end=1, color="#FFFFFF")]}
    monkeypatch.setattr(
        rangetags, "extract_markpens",
        lambda path: [(fake_buckets, len(flat) + 1)],
    )
    attach_range_tags(S4, doc)
    assert all(not p.markpens for p in flat)


def _dfs(paras):
    for p in paras:
        yield p
        for run in p.runs:
            if getattr(run, "table", None) is not None:
                for row in run.table.table_rows:
                    for cell in row.cells:
                        yield from _dfs(cell.paragraphs)
