import glob, tempfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

SAMPLES = {"3.": (0.0, 0.0), "4.": (0.0, 0.0), "2013": (7, 4)}  # (run_miss, t_miss) current

def _section_missing(hwp, ref):
    out = tempfile.mktemp(suffix=".hwpx"); convert(hwp, out)
    s = score_part(unzip_parts(out)["Contents/section0.xml"],
                   unzip_parts(ref)["Contents/section0.xml"])
    return s["missing"]

def test_score_floor_baseline():
    """Score-floor gate: section0 per-tag missing must not exceed current
    baseline on any sample. Task 3 tightens 2013's numbers downward."""
    for pre, (run_max, t_max) in SAMPLES.items():
        hwp = glob.glob("samples/" + pre + "*.hwp")[0]
        ref = glob.glob("samples/" + pre + "*.hwpx")[0]
        miss = _section_missing(hwp, ref)
        assert miss.get("run", 0) <= run_max, (pre, "run", miss.get("run"))
        assert miss.get("t", 0) <= t_max, (pre, "t", miss.get("t"))
