import os
import tempfile

import pytest

from hwp2hwpx.owpml.writer import write_package

# An int is neither bytes nor str, so zipfile.writestr rejects it -- a cheap way
# to fail *during* the zip write, which is the moment atomicity has to cover.
BAD_PARTS = {"Contents/section0.xml": 12345}
GOOD_PARTS = {"Contents/section0.xml": b"<hello/>"}


def test_failed_write_leaves_previous_content_intact(tmp_path):
    out = tmp_path / "out.hwpx"
    out.write_bytes(b"previous document")
    with pytest.raises(Exception):
        write_package(BAD_PARTS, str(out))
    assert out.read_bytes() == b"previous document"


def test_failed_write_creates_no_output(tmp_path):
    out = tmp_path / "out.hwpx"
    with pytest.raises(Exception):
        write_package(BAD_PARTS, str(out))
    assert not out.exists()


def test_failed_write_leaves_no_temp_file_behind(tmp_path):
    out = tmp_path / "out.hwpx"
    with pytest.raises(Exception):
        write_package(BAD_PARTS, str(out))
    assert os.listdir(str(tmp_path)) == []


def test_successful_write_leaves_only_the_output(tmp_path):
    out = tmp_path / "out.hwpx"
    write_package(GOOD_PARTS, str(out))
    assert os.listdir(str(tmp_path)) == ["out.hwpx"]


def test_output_has_the_mode_a_normal_create_would_give_it(tmp_path):
    # tempfile.mkstemp creates 0600; os.replace would carry that onto the
    # output, silently making every converted document owner-only. Compare
    # against a file created normally in the same directory rather than a
    # hardcoded bit, so the test holds under any umask.
    reference = tmp_path / "reference"
    reference.write_bytes(b"")
    out = tmp_path / "out.hwpx"
    write_package(GOOD_PARTS, str(out))
    assert os.stat(str(out)).st_mode == os.stat(str(reference)).st_mode


def test_temp_file_is_built_in_the_destination_directory(tmp_path, monkeypatch):
    # The load-bearing property behind atomicity: os.replace is only atomic
    # within a single filesystem, so the temp file has to live in the same
    # directory as the destination -- one built elsewhere (e.g. the system
    # temp dir) could land on a different filesystem and raise EXDEV instead
    # of replacing in place. Spy on mkstemp rather than inspecting the
    # finished output, since the temp file is gone (renamed to out_path) by
    # the time write_package returns successfully.
    real_mkstemp = tempfile.mkstemp
    seen_dirs = []

    def spy_mkstemp(*args, **kwargs):
        seen_dirs.append(kwargs.get("dir"))
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(tempfile, "mkstemp", spy_mkstemp)
    out = tmp_path / "out.hwpx"
    write_package(GOOD_PARTS, str(out))
    assert seen_dirs == [str(tmp_path)]
