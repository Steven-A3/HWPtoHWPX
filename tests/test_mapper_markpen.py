from hwp2hwpx.owpml.model import Run, Text, Control, MarkpenBegin, MarkpenEnd
from hwp2hwpx.hwpmodel.model import HwpRangeTag
from hwp2hwpx.mapper.markpen import apply_markpens


def _render(runs):
    """Flatten runs to a debug string: text, <B color>, <E>, <ctrl kind>."""
    out = []
    for r in runs:
        seg = []
        for it in r.texts:
            if isinstance(it, Text):
                seg.append(it.content)
            elif isinstance(it, MarkpenBegin):
                seg.append("<B %s>" % it.color)
            elif isinstance(it, MarkpenEnd):
                seg.append("<E>")
            elif isinstance(it, Control):
                seg.append("<c %s>" % it.kind)
        out.append("".join(seg))
    return out


def test_no_markpens_is_noop():
    runs = [Run(char_pr_id=1, texts=[Text("abcdef")])]
    apply_markpens(runs, [])
    assert _render(runs) == ["abcdef"]


def test_split_inside_single_text():
    # highlight chars [2:5] of "abcdef" -> ab <B> cde <E> f
    runs = [Run(char_pr_id=1, texts=[Text("abcdef")])]
    apply_markpens(runs, [HwpRangeTag(2, 5, "#FFFFFF")])
    assert _render(runs) == ["ab<B #FFFFFF>cde<E>f"]


def test_boundary_begin_leads_next_run_end_trails_prev_run():
    # two runs "abc"|"def"; span [3:5] -> begin at the run boundary (offset 3)
    # must lead run 2; end at offset 5 trails inside run 2.
    runs = [Run(char_pr_id=1, texts=[Text("abc")]),
            Run(char_pr_id=2, texts=[Text("def")])]
    apply_markpens(runs, [HwpRangeTag(3, 5, "#FFFFFF")])
    assert _render(runs) == ["abc", "<B #FFFFFF>de<E>f"]


def test_end_at_run_boundary_trails_preceding_run():
    # span [1:3] over runs "abc"|"def"; end at offset 3 (boundary) trails run 1.
    runs = [Run(char_pr_id=1, texts=[Text("abc")]),
            Run(char_pr_id=2, texts=[Text("def")])]
    apply_markpens(runs, [HwpRangeTag(1, 3, "#FFFFFF")])
    assert _render(runs) == ["a<B #FFFFFF>bc<E>", "def"]


def test_size_one_control_counts_as_width_one():
    # "ab" <fwSpace> "cd"; fwSpace is a genuinely width-1 control (the reader
    # never flags paragraphs containing it as markpen_unsafe), so offset 3 is
    # the start of "cd". Span [3:5] therefore highlights the whole "cd":
    # begin leads it, end trails.
    runs = [Run(char_pr_id=1, texts=[Text("ab"), Control("fwSpace"), Text("cd")])]
    apply_markpens(runs, [HwpRangeTag(3, 5, "#FFFFFF")])
    assert _render(runs) == ["ab<c fwSpace><B #FFFFFF>cd<E>"]


def test_skips_paragraph_with_table_or_drawing_run():
    runs = [Run(char_pr_id=1, texts=[Text("abcdef")]),
            Run(char_pr_id=2, texts=[], table=object())]
    apply_markpens(runs, [HwpRangeTag(2, 5, "#FFFFFF")])
    assert _render(runs)[0] == "abcdef"  # unchanged: non-text run present
