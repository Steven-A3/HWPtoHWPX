"""Single-parse, memoizing access to an HWP file via pyhwp's in-process API.

Replaces per-call `hwp5proc` subprocesses: one HwpSource opens the file once and
serves XML, models, streams, and summary from cached in-memory results.
"""
import io
from typing import Optional

from hwp5.xmlmodel import Hwp5File


def _strip(v):
    return (v or "").strip()


def _fmt_ts(dt):
    # match read_summary_info: "YYYY-MM-DDThh:mm:ssZ", empty when absent
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class HwpSource:
    def __init__(self, hwp_path):
        self._path = hwp_path
        self._file = None
        self._xml = None
        self._docinfo_models = None
        self._section_models = {}
        self._streams = {}
        self._summary = None

    @property
    def hwp5file(self):
        if self._file is None:
            self._file = Hwp5File(self._path)
        return self._file

    def xml(self):
        if self._xml is None:
            buf = io.BytesIO()
            self.hwp5file.xmlevents().dump(buf)
            self._xml = buf.getvalue()
        return self._xml

    def docinfo_models(self):
        if self._docinfo_models is None:
            self._docinfo_models = list(self.hwp5file.docinfo.models())
        return self._docinfo_models

    def section_names(self):
        return list(self.hwp5file.bodytext)

    def section_models(self, name):
        if name not in self._section_models:
            self._section_models[name] = list(self.hwp5file.bodytext[name].models())
        return self._section_models[name]

    def stream_bytes(self, path) -> Optional[bytes]:
        if path not in self._streams:
            self._streams[path] = self._read_stream(path)
        return self._streams[path]

    def _read_stream(self, path):
        node = self.hwp5file
        try:
            for part in path.split("/"):
                node = node[part]
            return node.open().read()
        except Exception:  # missing/unreadable stream -> caller skips
            return None

    def summary(self):
        if self._summary is None:
            si = self.hwp5file.summaryinfo
            created = getattr(si, "createdTime", None)
            saved = getattr(si, "lastSavedTime", None)
            self._summary = {
                "title": _strip(getattr(si, "title", "")),
                "creator": _strip(getattr(si, "author", "")),
                "subject": _strip(getattr(si, "subject", "")),
                "description": _strip(getattr(si, "comments", "")),
                "last_saved_by": _strip(getattr(si, "lastSavedBy", "")),
                "created_date": _fmt_ts(created.datetime if created is not None else None),
                "modified_date": _fmt_ts(saved.datetime if saved is not None else None),
                "date": _strip(getattr(si, "dateString", "")),
                "keyword": _strip(getattr(si, "keywords", "")),
            }
        return self._summary


def _as_source(x):
    return x if isinstance(x, HwpSource) else HwpSource(x)
