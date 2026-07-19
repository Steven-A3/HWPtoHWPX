import glob
import json
import os

import pytest

from hwp2hwpx.cli import main


def _sample():
    # samples/ is private and git-ignored; locate by prefix, never by filename.
    return glob.glob("samples/3.*.hwp")[0]


def test_converts_a_single_file_with_explicit_output(tmp_path):
    out = tmp_path / "out.hwpx"
    assert main([_sample(), "-o", str(out)]) == 0
    assert os.path.getsize(str(out)) > 0


def test_converts_into_an_outdir_that_does_not_exist_yet(tmp_path):
    outdir = tmp_path / "made-on-demand"
    assert main([_sample(), "--outdir", str(outdir)]) == 0
    assert len(os.listdir(str(outdir))) == 1


def test_missing_input_is_a_per_file_failure_not_a_usage_error(tmp_path):
    out = tmp_path / "out.hwpx"
    assert main(["does-not-exist.hwp", "-o", str(out)]) == 1


def test_failure_message_names_the_input(tmp_path, capsys):
    main(["does-not-exist.hwp", "-o", str(tmp_path / "out.hwpx")])
    assert "does-not-exist.hwp" in capsys.readouterr().err


def test_quiet_suppresses_the_failure_message_but_not_the_exit_code(tmp_path, capsys):
    rc = main(["-q", "does-not-exist.hwp", "-o", str(tmp_path / "out.hwpx")])
    assert rc == 1
    assert capsys.readouterr().err == ""


def test_success_is_silent(tmp_path, capsys):
    main([_sample(), "-o", str(tmp_path / "out.hwpx")])
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_skipping_an_existing_output_exits_zero(tmp_path):
    out = tmp_path / "out.hwpx"
    out.write_bytes(b"already here")
    assert main([_sample(), "-o", str(out)]) == 0
    assert out.read_bytes() == b"already here"


def test_force_overwrites_an_existing_output(tmp_path):
    out = tmp_path / "out.hwpx"
    out.write_bytes(b"already here")
    assert main([_sample(), "-o", str(out), "--force"]) == 0
    assert out.read_bytes() != b"already here"


def test_force_without_an_explicit_destination_is_a_usage_error(tmp_path):
    # The V1 gate.
    with pytest.raises(SystemExit) as exc:
        main([_sample(), "--force"])
    assert exc.value.code == 2


def test_o_with_several_inputs_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([_sample(), _sample(), "-o", "out.hwpx"])
    assert exc.value.code == 2


def test_json_flag_does_not_swallow_a_positional_input(tmp_path):
    # The V3 gate: with an optional-valued --json, argparse binds the first
    # positional to the flag and silently drops it from the run.
    report = tmp_path / "report.json"
    rc = main(["--json", str(report), "does-not-exist-1.hwp",
               "does-not-exist-2.hwp", "--outdir", str(tmp_path)])
    assert rc == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert [f["input"] for f in data["files"]] == [
        "does-not-exist-1.hwp", "does-not-exist-2.hwp"]


def test_json_report_records_counts_and_per_file_status(tmp_path):
    report = tmp_path / "report.json"
    rc = main([_sample(), "does-not-exist.hwp", "--outdir", str(tmp_path),
               "--json", str(report)])
    assert rc == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["counts"] == {"converted": 1, "overwritten": 0,
                              "skipped": 0, "failed": 1}
    assert {f["ok"] for f in data["files"]} == {True, False}


def test_json_to_stdout(tmp_path, capsys):
    main([_sample(), "--outdir", str(tmp_path), "--json", "-"])
    assert json.loads(capsys.readouterr().out)["counts"]["converted"] == 1


def test_verbose_reports_each_file_and_a_summary(tmp_path, capsys):
    main(["-v", _sample(), "--outdir", str(tmp_path)])
    err = capsys.readouterr().err
    assert "converted 1" in err


def test_version_prints_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() != ""
