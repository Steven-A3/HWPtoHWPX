"""Read HWP paragraph range-tag records (markpen highlighter) via pyhwp's
binmodel API and attach them to parsed paragraphs.

`hwp5proc xml` (the reader's main source) omits range tags entirely, so this is
the one reader path that reads the binary model directly. Only kind==2 tags
(the markpen highlighter) are kept; `data` is the RGB color. Range tags are
keyed by depth-first paragraph index, which matches the order the binmodel emits
`Paragraph` records (level 0 section paragraphs, level>=2 table-cell paragraphs)
and the order `read_document`/`parse_paragraph` build the parsed tree."""
from .model import HwpRangeTag

_MARKPEN_KIND = 2


def _dfs_paragraphs(paragraphs):
    """Parsed paragraphs in binmodel DFS order: a paragraph, then the cell
    paragraphs of each table it contains, recursively."""
    for para in paragraphs:
        yield para
        for run in para.runs:
            # a run may hold several tables (grouped by one char shape); walk
            # them in contents order to match the binmodel's paragraph stream.
            for table in getattr(run, "tables", []):
                for row in table.table_rows:
                    for cell in row.cells:
                        yield from _dfs_paragraphs(cell.paragraphs)


def extract_markpens(hwp_path):
    """One (buckets, binmodel_para_count) pair per bodytext section, where
    buckets is {dfs_para_index: [HwpRangeTag, ...]} and binmodel_para_count is
    the total count of binmodel `Paragraph` records seen in that section (used
    by attach_range_tags for a per-section count-equality guard). kind==2 only.
    Returns [] on any read failure (fail-safe)."""
    try:
        from hwp5.xmlmodel import Hwp5File
        f = Hwp5File(hwp_path)
    except Exception:
        return []
    out = []
    try:
        for sec_name in f.bodytext:
            stream = f.bodytext[sec_name]
            buckets = {}
            para_idx = -1
            for model in stream.models():
                name = model["type"].__name__
                if name == "Paragraph":
                    para_idx += 1
                elif name == "ParaRangeTag":
                    spans = []
                    for rt in model["content"]["range_tags"]:
                        tag = rt["tag"]
                        if tag.kind == _MARKPEN_KIND:
                            spans.append(HwpRangeTag(
                                start=rt["start"], end=rt["end"],
                                color="#%06X" % tag.data))
                    if spans:
                        buckets.setdefault(para_idx, []).extend(spans)
            out.append((buckets, para_idx + 1))
    except Exception:
        return []
    return out


def attach_range_tags(hwp_path, hwp_doc):
    """Attach kind==2 range tags to hwp_doc paragraphs by DFS index. Fail-safe:
    on any error, or a per-section paragraph-count mismatch between the
    binmodel `Paragraph` record count and the parsed-tree DFS paragraph count,
    that section's paragraphs keep empty `markpens` rather than risk
    mis-assignment (e.g. from binmodel-only nested paragraphs emitted by
    header/footer/footnote/endnote/textbox controls)."""
    sections_buckets = extract_markpens(hwp_path)
    if not sections_buckets:
        return
    for sec, (buckets, bin_para_count) in zip(hwp_doc.sections, sections_buckets):
        flat = list(_dfs_paragraphs(sec.paragraphs))
        if not buckets:
            continue
        if bin_para_count != len(flat):
            continue  # count mismatch -> skip this section, fail-safe
        for idx, spans in buckets.items():
            if idx < 0:
                continue  # defensive: a range tag before the first Paragraph record
            if getattr(flat[idx], "markpen_unsafe", False):
                continue  # fail-safe: char-offset basis unreproducible by the mapper
            flat[idx].markpens = list(spans)
