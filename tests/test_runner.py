import os

import pytest

from hwp2hwpx.runner import (
    Job, Result, UsageError, default_output, plan_jobs, run_jobs,
)


def test_default_output_swaps_the_extension():
    assert default_output("/docs/report.hwp") == "/docs/report.hwpx"


def test_default_output_places_the_file_beside_its_input():
    assert os.path.dirname(default_output("/a/b/c.hwp")) == "/a/b"


def test_plan_uses_beside_input_naming_when_no_destination_given():
    jobs = plan_jobs(["/docs/a.hwp", "/docs/b.hwp"])
    assert [j.output for j in jobs] == ["/docs/a.hwpx", "/docs/b.hwpx"]
    assert all(j.action == "convert" for j in jobs)


def test_plan_puts_outputs_in_outdir_keeping_only_the_basename():
    jobs = plan_jobs(["/docs/deep/a.hwp"], outdir="/out")
    assert jobs[0].output == os.path.join("/out", "a.hwpx")


def test_plan_honors_o_for_a_single_input():
    jobs = plan_jobs(["/docs/a.hwp"], out_file="/tmp/named.hwpx")
    assert jobs == [Job("/docs/a.hwp", "/tmp/named.hwpx", "convert")]


def test_plan_rejects_o_with_several_inputs():
    with pytest.raises(UsageError):
        plan_jobs(["/docs/a.hwp", "/docs/b.hwp"], out_file="/tmp/named.hwpx")


def test_plan_rejects_o_together_with_outdir():
    with pytest.raises(UsageError):
        plan_jobs(["/docs/a.hwp"], out_file="/tmp/named.hwpx", outdir="/out")


def test_plan_rejects_force_without_an_explicit_destination():
    # The V1 gate: --force plus beside-input naming would mass-overwrite a
    # folder in place, destroying reference .hwpx exports stored next to their
    # sources. Overwriting must require naming the destination.
    with pytest.raises(UsageError):
        plan_jobs(["/docs/a.hwp"], force=True)


def test_plan_allows_force_with_an_explicit_destination():
    jobs = plan_jobs(["/docs/a.hwp"], outdir="/out", force=True)
    assert jobs[0].action == "convert"


def test_plan_skips_an_existing_output(tmp_path):
    src = tmp_path / "a.hwp"
    src.write_bytes(b"x")
    (tmp_path / "a.hwpx").write_bytes(b"already here")
    jobs = plan_jobs([str(src)])
    assert jobs[0].action == "skip"


def test_plan_marks_an_existing_output_for_overwrite_under_force(tmp_path):
    src = tmp_path / "a.hwp"
    src.write_bytes(b"x")
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.hwpx").write_bytes(b"already here")
    jobs = plan_jobs([str(src)], outdir=str(out), force=True)
    assert jobs[0].action == "overwrite"


def test_plan_creates_nothing_on_disk(tmp_path):
    plan_jobs([str(tmp_path / "a.hwp")], outdir=str(tmp_path / "nope"))
    assert not (tmp_path / "nope").exists()


def test_run_skips_without_converting(monkeypatch):
    import hwp2hwpx.runner as runner
    calls = []
    monkeypatch.setattr(runner, "convert", lambda i, o: calls.append(i))
    results = run_jobs([Job("a.hwp", "a.hwpx", "skip")])
    assert calls == []
    assert results == [Result("a.hwp", "a.hwpx", "skip", True, None, None)]


def test_run_isolates_a_failure_and_keeps_going(monkeypatch):
    import hwp2hwpx.runner as runner

    def flaky(inp, out):
        if inp == "bad.hwp":
            raise ValueError("broken record")

    monkeypatch.setattr(runner, "convert", flaky)
    results = run_jobs([
        Job("bad.hwp", "bad.hwpx", "convert"),
        Job("good.hwp", "good.hwpx", "convert"),
    ])
    assert [r.ok for r in results] == [False, True]
    assert results[0].error == "broken record"
    assert results[0].error_type == "ValueError"
    assert results[1].error is None


def test_run_reports_each_result_as_it_completes(monkeypatch):
    import hwp2hwpx.runner as runner
    monkeypatch.setattr(runner, "convert", lambda i, o: None)
    seen = []
    run_jobs([Job("a.hwp", "a.hwpx", "convert")], on_result=seen.append)
    assert [r.input for r in seen] == ["a.hwp"]


def test_run_treats_a_missing_input_as_a_per_file_failure():
    # Not a usage error: one typo in a 500-path list must not abort the run.
    results = run_jobs([Job("does-not-exist.hwp", "x.hwpx", "convert")])
    assert results[0].ok is False
