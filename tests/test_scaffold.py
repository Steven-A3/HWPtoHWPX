from hwp2hwpx import constants
from hwp2hwpx.cli import main


def test_namespaces_present():
    assert constants.NS["hp"].endswith("/2011/paragraph")
    assert constants.MIMETYPE == "application/hwp+zip"


def test_cli_parses_args():
    assert main(["in.hwp", "-o", "out.hwpx"]) == 0
