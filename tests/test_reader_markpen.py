import glob
import pytest
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
    spans = [s for buckets in secs for lst in buckets.values() for s in lst]
    assert len(spans) == 5
    assert all(s.color == "#FFFFFF" for s in spans)


def test_sample3_has_no_markpen():
    secs = extract_markpens(S3)
    assert all(len(buckets) == 0 for buckets in secs)


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


def _dfs(paras):
    for p in paras:
        yield p
        for run in p.runs:
            if getattr(run, "table", None) is not None:
                for row in run.table.table_rows:
                    for cell in row.cells:
                        yield from _dfs(cell.paragraphs)
