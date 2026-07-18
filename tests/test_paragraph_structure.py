import glob, tempfile
import pytest
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from tests.fidelity_struct import _para_sig, _top_paras
from lxml import etree

# Task 3 tightened 2013 downward: table paragraphs now split into an object run
# + a break run (both matching Hancom), #361's four object runs collapse into
# one, and object/ctrl-only paragraphs gain the break <t/> anchor.
# Achieved after Task 3 (was (7, 4)). 2013's residual t=1 is one structurally
# out-of-scope case: an extended control inlined between two text spans, which
# the ctrls/ctrls_after model cannot place mid-run. run miss is 0 on every
# sample; samples 3 & 4 are exact.
SAMPLES = {"3.": (0, 0), "4.": (0, 0), "2013": (0, 1)}  # (run_miss, t_miss)


def _top_para_sigs(pre, idx):
    """(our_sig, their_sig) child-kind signatures for top-level paragraph idx."""
    hwp = glob.glob("samples/" + pre + "*.hwp")[0]
    ref = glob.glob("samples/" + pre + "*.hwpx")[0]
    out = tempfile.mktemp(suffix=".hwpx"); convert(hwp, out)
    ours = _top_paras(etree.fromstring(unzip_parts(out)["Contents/section0.xml"]))
    theirs = _top_paras(etree.fromstring(unzip_parts(ref)["Contents/section0.xml"]))
    our_seqs = [seq for _, seq in _para_sig(ours[idx])]
    their_seqs = [seq for _, seq in _para_sig(theirs[idx])]
    return our_seqs, their_seqs


@pytest.mark.parametrize("pre,idx", [
    ("2013", 192),   # table-only -> [tbl][<t/>] (break cs differs)
    ("2013", 361),   # 3 rects + pic, one shared char shape -> one run
    ("4.", 336),     # tbl + line -> [tbl,line][<t/>]
    ("4.", 337),     # 2 tbl + 5 line + text -> [objs,text][<t/>]
])
def test_representative_paragraph_matches_hancom(pre, idx):
    ours, theirs = _top_para_sigs(pre, idx)
    assert ours == theirs

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
