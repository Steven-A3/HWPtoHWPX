from hwp2hwpx import constants
from hwp2hwpx.cli import main

SAMPLE = "samples/3.과업지시서_070.hwp"


def test_namespaces_present():
    assert constants.NS["hp"].endswith("/2011/paragraph")
    assert constants.MIMETYPE == "application/hwp+zip"


def test_cli_parses_args(tmp_path):
    out = tmp_path / "out.hwpx"
    assert main([SAMPLE, "-o", str(out)]) == 0
