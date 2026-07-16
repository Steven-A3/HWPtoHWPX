import zipfile
import re
from hwp2hwpx.convert import convert

SAMPLE_HWP = "samples/3.과업지시서_070.hwp"


def _section(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE_HWP, str(out))
    with zipfile.ZipFile(str(out)) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


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
    sec = _section(tmp_path)
    # a fwSpace splits this phrase; both sides must survive
    assert "납부해야 함" in sec
    assert "별표2 참조" in sec
