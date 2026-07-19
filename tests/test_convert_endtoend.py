import zipfile
from lxml import etree
from hwp2hwpx.convert import convert
from hwp2hwpx.constants import NS
from tests.samplepaths import S3

SAMPLE = S3


def test_convert_produces_valid_hwpx(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE, str(out))
    with zipfile.ZipFile(out) as z:
        assert z.namelist()[0] == "mimetype"
        # section text is non-empty and well-formed
        sec = z.read("Contents/section0.xml")
        root = etree.fromstring(sec)
        text = "".join(t.text or "" for t in root.iter(
            "{http://www.hancom.co.kr/hwpml/2011/paragraph}t"))
        assert text.strip() != ""


def test_convert_no_dangling_refs_in_output(tmp_path):
    """Cross-layer correctness: no <hp:p> is run-less, and every
    styleIDRef used in section0.xml resolves to a style id that
    header.xml actually emits (no dangling references)."""
    out = tmp_path / "out.hwpx"
    convert(SAMPLE, str(out))
    hp = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
    hh = "{%s}" % NS["hh"]
    with zipfile.ZipFile(out) as z:
        header_root = etree.fromstring(z.read("Contents/header.xml"))
        emitted_style_ids = {s.get("id") for s in header_root.iter(hh + "style")}

        root = etree.fromstring(z.read("Contents/section0.xml"))
        paras = list(root.iter(hp + "p"))
        assert paras, "expected at least one <hp:p>"
        runless = [p for p in paras if len(list(p.iter(hp + "run"))) == 0]
        assert runless == []
        style_refs = {p.get("styleIDRef") for p in paras}
        assert style_refs, "expected at least one styleIDRef"
        assert style_refs <= emitted_style_ids
