import glob
from hwp2hwpx.hwpmodel import rangetags
from hwp2hwpx.hwpmodel.model import HwpRangeTag
from hwp2hwpx.hwpmodel.reader import read_document, hwp5_xml
from hwp2hwpx.hwpmodel.rangetags import extract_markpens, attach_range_tags

S3 = glob.glob("samples/3.*.hwp")[0]
S4 = glob.glob("samples/4.*.hwp")[0]


def _para_text(p):
    out = []
    for r in p.runs:
        for c in r.contents:
            if isinstance(c, str):
                out.append(c)
    return "".join(out)


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
    highlighted = [p for p in _dfs(doc.sections[0].paragraphs) if p.markpens]
    texts = [_para_text(p) for p in highlighted]
    assert any(t.startswith("2. 위 사업의 입찰") for t in texts)
    assert any(t.startswith("3. 또한 계약 체결과 이행") for t in texts)
    # total attached spans == 5
    assert sum(len(p.markpens) for p in highlighted) == 5


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
