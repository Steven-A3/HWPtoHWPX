import zipfile
from hwp2hwpx.convert import convert
from hwp2hwpx.hwpmodel.model import HwpControl
from hwp2hwpx.hwpmodel.reader import read_document, hwp5_xml
from tests.samplepaths import S3

SAMPLE_HWP = S3


def _section(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def _dfs(paras):
    for p in paras:
        yield p
        for run in p.runs:
            if getattr(run, "table", None) is not None:
                for row in run.table.table_rows:
                    for cell in row.cells:
                        yield from _dfs(cell.paragraphs)


def _fwspace_splits(doc):
    """(text_before, text_after) for each fwSpace control in doc with
    non-trivial text on both sides, in document order. Derived from the
    source rather than hardcoded: samples/ is git-ignored, so no document
    text may be committed."""
    out = []
    for p in _dfs(doc.sections[0].paragraphs):
        for run in p.runs:
            c = run.contents
            for i, item in enumerate(c):
                if isinstance(item, HwpControl) and item.kind == "fwSpace":
                    before = c[i - 1] if i > 0 and isinstance(c[i - 1], str) else ""
                    after = c[i + 1] if i + 1 < len(c) and isinstance(c[i + 1], str) else ""
                    # both sides present and not just a single bullet/space glyph
                    if before and after and max(len(before), len(after)) >= 4:
                        out.append((before, after))
    return out


def test_inline_controls_present(tmp_path):
    sec = _section(tmp_path)
    assert sec.count("<hp:fwSpace") == 30
    assert sec.count("<hp:lineBreak") == 11


def test_run_and_t_counts_converge_to_hancom(tmp_path):
    sec = _section(tmp_path)
    # Hancom: 869 runs / 690 <hp:t>. Merging must bring us close, well below
    # the old 1603 / 1429.
    runs = sec.count("<hp:run")
    ts = sec.count("<hp:t>") + sec.count("<hp:t ")
    assert runs < 1000
    assert ts < 800


def test_previously_dropped_text_present(tmp_path):
    # a fwSpace control sits between two text spans in the source, splitting
    # them; regression coverage for a past bug where the run-merging pass
    # silently dropped the text on one side of such a split. Checked for
    # every non-trivial fwSpace split in the sample, not just one memorized
    # instance.
    doc = read_document(hwp5_xml(SAMPLE_HWP))
    splits = _fwspace_splits(doc)
    assert len(splits) >= 5  # sanity: sample still has plenty of these splits
    sec = _section(tmp_path)
    for before, after in splits:
        assert before in sec
        assert after in sec
