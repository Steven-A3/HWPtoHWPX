import re
import tempfile

from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.xmlnorm import unzip_parts
from hwp2hwpx.fidelity.diff import score_part
from tests.samplepaths import hwp as _hwp, hwpx as _hwpx

# The expected creator/title/date below are NOT memorised constants: they are
# read from the private source document at test time via read_summary_info,
# so this file carries no PII of its own even though the assertions still
# exercise real (non-empty, source-derived) values. See docs/superpowers or
# git history for why: a memorised name+title pair was found hardcoded here
# during a pre-publication privacy sweep and replaced with this derivation.


def test_summary_info_parsed():
    from hwp2hwpx.hwpmodel.summary import read_summary_info
    si = read_summary_info(_hwp("2013"))
    # Regression value: proves summary info is actually parsed out of the
    # source (non-empty fields), without memorising *what* those values are.
    assert si.creator, "creator field parsed as empty"
    assert si.title, "title field parsed as empty"
    # The created_date timestamp is kept as an exact-value assertion (unlike
    # creator/title): a "YYYY-MM-DDThh:mm:ssZ" save timestamp does not, on
    # its own, identify a person or a document's contents.
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", si.created_date)


def test_content_hpf_meta_blocks_present():
    from hwp2hwpx.hwpmodel.summary import read_summary_info
    hwp = _hwp("2013")
    ref = _hwpx("2013")
    si = read_summary_info(hwp)
    out = tempfile.mktemp(suffix=".hwpx")
    convert(hwp, out)
    o = unzip_parts(out)["Contents/content.hpf"]
    t = unzip_parts(ref)["Contents/content.hpf"]
    assert score_part(o, t)["missing"].get("meta", 0) == 0
    xml = o.decode("utf-8")
    # Ties output to input: whatever the source document's real creator is,
    # that exact value must reach the emitted content.hpf meta block.
    assert si.creator, "creator field parsed as empty"
    assert ('<opf:meta name="creator" content="text">%s</opf:meta>'
            % si.creator) in xml
    assert '<opf:meta name="keyword" content="text"/>' in xml
