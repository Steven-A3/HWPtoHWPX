import glob
import subprocess

from lxml import etree

from hwp2hwpx.hwpmodel.source import HwpSource, _as_source
from hwp2hwpx.hwpmodel.reader import _hwp5proc
from hwp2hwpx.hwpmodel.summary import read_summary_info

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


@pytest.mark.parametrize("pre", SAMPLES)
def test_summary_matches_subprocess(pre):
    hwp = _hwp(pre)
    assert HwpSource(hwp).summary() == vars(read_summary_info(hwp))


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
