from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from hwp2hwpx.hwpmodel.reader import read_document, hwp5_xml
from hwp2hwpx.hwpmodel.rangetags import attach_range_tags
from tests.samplepaths import hwp as _hwp, hwpx as _hwpx

S3 = _hwp("3.")
S4 = _hwp("4.")
S4_REF = _hwpx("4.")


def _dfs(paras):
    for p in paras:
        yield p
        for run in p.runs:
            if getattr(run, "table", None) is not None:
                for row in run.table.table_rows:
                    for cell in row.cells:
                        yield from _dfs(cell.paragraphs)


def _run_bounds(p):
    """[(char_offset_start, char_offset_end, run), ...] per HwpRun, using the
    same width convention apply_markpens uses (a str item contributes its
    length, anything else contributes 1)."""
    offset = 0
    bounds = []
    for run in p.runs:
        start = offset
        for item in run.contents:
            offset += len(item) if isinstance(item, str) else 1
        bounds.append((start, offset, run))
    return bounds


def _slice_contents(contents, lo, hi):
    """Reconstruct the substring of one HwpRun's contents falling in [lo, hi)
    of that run's own local offset -- mirrors apply_markpens's text-splitting
    logic so the result matches what it would wrap in markers."""
    offset = 0
    out = []
    for item in contents:
        if isinstance(item, str):
            width = len(item)
            a, b = max(lo, offset), min(hi, offset + width)
            if a < b:
                out.append(item[a - offset:b - offset])
            offset += width
        else:
            offset += 1
    return "".join(out)


def test_markpen_markers_leave_section_miss_list(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    assert missing.get("markpenBegin", 0) == 0
    assert missing.get("markpenEnd", 0) == 0


def test_markpen_exact_serialization_of_known_run(tmp_path):
    # Every markpen span whose HWP range-tag offsets fall entirely inside one
    # HwpRun must serialize as an unbroken <hp:markpenBegin>...<hp:markpenEnd/>
    # around exactly that run's text at that offset -- derived from the source
    # document rather than a memorized sentence, so this also verifies against
    # sample drift. (A span that instead crosses a run boundary, e.g. because
    # unrelated text sits between two identically-styled halves, closes and
    # reopens per run; that case is covered by the whole-document fidelity
    # checks below, not by this exact-match assertion.)
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    xml = unzip_parts(str(out))["Contents/section0.xml"].decode("utf-8")

    doc = read_document(hwp5_xml(S4))
    attach_range_tags(S4, doc)
    checked = 0
    for p in _dfs(doc.sections[0].paragraphs):
        if not p.markpens:
            continue
        bounds = _run_bounds(p)
        for span in p.markpens:
            hit = next(((s, e, r) for s, e, r in bounds
                        if s <= span.start and span.end <= e), None)
            if hit is None:
                continue
            run_start, _, run = hit
            text = _slice_contents(run.contents, span.start - run_start, span.end - run_start)
            pattern = '<hp:markpenBegin color="%s"/>%s<hp:markpenEnd/>' % (span.color, text)
            assert pattern in xml
            checked += 1
    # sample 4 has 5 markpen spans total; 4 land inside a single run and are
    # checked exactly above, 1 crosses a run boundary (see comment).
    assert checked == 4


def test_section_match_rises_sample4(tmp_path):
    out = tmp_path / "s4.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    assert score_part(ours, theirs)["match"] > 0.992


def test_sample3_section_unchanged(tmp_path):
    # Sample 3 has no markpen. Baseline refreshed for Task 3's faithful run
    # segmentation: para 0 now merges the pageNum ctrl into the table run
    # (matching Hancom -> section0 has zero structural paragraph divergences),
    # len 497233, sha256 4c059a6cc8be2bc2.
    out = tmp_path / "s3.hwpx"
    convert(S3, str(out))
    body = unzip_parts(str(out))["Contents/section0.xml"]
    import hashlib
    assert len(body) == 497233
    assert hashlib.sha256(body).hexdigest().startswith("4c059a6cc8be2bc2")
