import glob
import subprocess

from lxml import etree

from hwp2hwpx.hwpmodel.source import HwpSource, _as_source
from hwp2hwpx.hwpmodel.reader import _hwp5proc

SAMPLES = ["samples/3.", "samples/4.", "samples/★131008", "samples/20131106"]


def _hwp(pre):
    return glob.glob(pre + "*.hwp")[0]


def _tree_key(root):
    # order-independent (tag, sorted-attrs, text) list, excluding PropertySetStream
    out = []
    def rec(el):
        if el.tag == "PropertySetStream":
            return
        out.append((el.tag, tuple(sorted(el.attrib.items())), (el.text or "").strip()))
        for c in el:
            rec(c)
    rec(root)
    return out


import pytest


@pytest.mark.parametrize("pre", SAMPLES)
def test_xml_tree_equivalent_to_cli(pre):
    hwp = _hwp(pre)
    api = HwpSource(hwp).xml()
    cli = subprocess.check_output([_hwp5proc(), "xml", hwp])
    assert _tree_key(etree.fromstring(api)) == _tree_key(etree.fromstring(cli))


@pytest.mark.parametrize("pre", SAMPLES)
def test_stream_bytes_equal_cli_cat(pre):
    hwp = _hwp(pre)
    src = HwpSource(hwp)
    ls = subprocess.run([_hwp5proc(), "ls", hwp], capture_output=True, text=True).stdout.split()
    targets = [s for s in ls if s.startswith("BinData/")] + ["PrvImage"]
    for name in targets:
        cli = subprocess.run([_hwp5proc(), "cat", hwp, name], capture_output=True).stdout
        assert src.stream_bytes(name) == cli, name


def test_stream_bytes_missing_returns_none():
    assert HwpSource(_hwp("samples/3.")).stream_bytes("BinData/BIN9999.bmp") is None


# `read_summary_info` is itself implemented in terms of HwpSource.summary()
# now, so comparing HwpSource(hwp).summary() against it would be a tautology
# (a value compared to itself). This independently re-derives the pre-refactor
# oracle -- `hwp5proc summaryinfo`'s `Key: value` text output, parsed the same
# way the pre-refactor summary.py did -- to keep the gate genuine.
_SUMMARY_KEYS = {"Title": "title", "Author": "creator", "Subject": "subject",
                 "Comments": "description", "Last saved by": "last_saved_by",
                 "Created at": "created_date", "Last saved at": "modified_date",
                 "Date": "date", "Keywords": "keyword"}
_SUMMARY_TS_FIELDS = ("created_date", "modified_date")


def _fmt_ts_from_cli(v):
    v = v.split(".", 1)[0].strip()  # drop fractional seconds
    return v.replace(" ", "T") + "Z" if v else ""


def _summary_via_subprocess(hwp):
    out = subprocess.run([_hwp5proc(), "summaryinfo", hwp],
                         capture_output=True).stdout.decode("utf-8", "replace")
    fields = {attr: "" for attr in _SUMMARY_KEYS.values()}
    for line in out.splitlines():
        if ": " not in line:
            continue
        key, val = line.split(": ", 1)
        attr = _SUMMARY_KEYS.get(key.strip())
        if attr is None:
            continue
        val = val.strip()
        fields[attr] = _fmt_ts_from_cli(val) if attr in _SUMMARY_TS_FIELDS else val
    return fields


@pytest.mark.parametrize("pre", SAMPLES)
def test_summary_matches_subprocess(pre):
    hwp = _hwp(pre)
    assert HwpSource(hwp).summary() == _summary_via_subprocess(hwp)


def test_section_models_type_is_class_name():
    src = HwpSource(_hwp("samples/3."))
    names = {m["type"].__name__ for m in src.section_models(src.section_names()[0])}
    assert "Paragraph" in names and "ParaCharShape" in names


def test_memoized_parse_runs_once(monkeypatch):
    src = HwpSource(_hwp("samples/3."))
    calls = {"xml": 0}
    real = src.hwp5file.xmlevents
    def counting(*a, **k):
        calls["xml"] += 1
        return real(*a, **k)
    monkeypatch.setattr(src.hwp5file, "xmlevents", counting)
    src.xml(); src.xml(); src.xml()
    assert calls["xml"] == 1


def test_as_source_passthrough():
    src = HwpSource(_hwp("samples/3."))
    assert _as_source(src) is src
    assert isinstance(_as_source(_hwp("samples/3.")), HwpSource)


def test_summary_tolerates_absent_ole_properties():
    # HwpSummaryInfo exposes its fields as properties over an OLE property set:
    # an absent property raises KeyError from inside the getter, and a missing
    # property set raises TypeError. Neither is caught by getattr's default.
    class _Boom:
        @property
        def title(self):
            raise KeyError("PIDSI_TITLE")

        @property
        def createdTime(self):
            raise TypeError("propertySet is None")

    class _Fake:
        summaryinfo = _Boom()

    src = HwpSource("unused")
    src._file = _Fake()
    summary = src.summary()
    assert summary["title"] == ""
    assert summary["created_date"] == ""
    assert summary["keyword"] == ""


def test_summary_tolerates_missing_summary_info_stream():
    # A document lacking the \x05HwpSummaryInformation stream entirely raises
    # out of the `summaryinfo` cached_property itself -- before any `_field`
    # guard runs. read_summary_info's pre-refactor behavior was to fall back
    # to defaults here, not propagate the error.
    class _Fake:
        @property
        def summaryinfo(self):
            raise KeyError("\x05HwpSummaryInformation")

    src = HwpSource("unused")
    src._file = _Fake()
    assert src.summary() == {
        "title": "", "creator": "", "subject": "", "description": "",
        "last_saved_by": "", "created_date": "", "modified_date": "",
        "date": "", "keyword": "",
    }


def test_summary_coerces_non_string_field():
    # A vendor-authored file can put a non-string value (e.g. an int) in a
    # text-typed slot like keywords; _strip used to assume str and raise.
    class _Info:
        title = None
        author = None
        subject = None
        comments = None
        lastSavedBy = None
        createdTime = None
        lastSavedTime = None
        dateString = None
        keywords = 123

    class _Fake:
        summaryinfo = _Info()

    src = HwpSource("unused")
    src._file = _Fake()
    assert src.summary()["keyword"] == "123"


def test_section_names_filters_and_orders_numerically():
    # No sample has more than one section, so this can only be exercised with
    # a stub: OLE directory order need not match numeric order, and BodyText
    # can hold non-Section children (both silently corrupt reader.py's
    # positional char-shape-map zip if section_names doesn't filter+sort).
    class _Fake:
        bodytext = ["Section2", "Preview", "Section10", "Section0", "BinData"]

    src = HwpSource("unused")
    src._file = _Fake()
    assert src.section_names() == ["Section0", "Section2", "Section10"]


def test_section_names_memoized():
    calls = {"n": 0}

    class _Iterable:
        def __iter__(self):
            calls["n"] += 1
            return iter(["Section1", "Section0"])

    class _Fake:
        bodytext = _Iterable()

    src = HwpSource("unused")
    src._file = _Fake()
    assert src.section_names() == ["Section0", "Section1"]
    assert src.section_names() == ["Section0", "Section1"]
    assert calls["n"] == 1
