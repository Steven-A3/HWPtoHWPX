import os
from hwp2hwpx.cli import main

SAMPLE = "samples/3.과업지시서_070.hwp"


def test_cli_converts(tmp_path):
    out = tmp_path / "out.hwpx"
    rc = main([SAMPLE, "-o", str(out)])
    assert rc == 0
    assert os.path.getsize(out) > 0


def test_cli_missing_input_reports_error(tmp_path, capsys):
    out = tmp_path / "out.hwpx"
    rc = main(["does-not-exist.hwp", "-o", str(out)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "does-not-exist.hwp" in err
