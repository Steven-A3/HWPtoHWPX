"""Single-parse, memoizing access to an HWP file via pyhwp's in-process API.

Replaces per-call `hwp5proc` subprocesses: one HwpSource opens the file once and
serves XML, models, streams, and summary from cached in-memory results.
"""
import io
from typing import Optional

from hwp5.xmlmodel import Hwp5File


def _strip(v):
    # OLE property values are normally str, but a vendor-authored file can put
    # a non-string type (e.g. an int) in a text-typed slot like keywords;
    # .strip() on that raises AttributeError outside the _field guard.
    if isinstance(v, str):
        return v.strip()
    return str(v).strip() if v else ""


def _field(si, name):
    # HwpSummaryInfo exposes these as properties over an OLE property set, so an
    # absent property raises KeyError (or TypeError when the whole set is
    # missing) from inside the getter -- getattr's default only covers
    # AttributeError. Degrade to absent, like the text-dump path did.
    if si is None:
        return None
    try:
        return getattr(si, name)
    except (AttributeError, KeyError, TypeError):
        return None


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
        self._section_names = None
        self._section_models = {}
        self._streams = {}
        self._summary = None

    @property
    def hwp5file(self):
        if self._file is None:
            self._file = Hwp5File(self._path)
        return self._file

    def close(self):
        """Release the OLE storage handle, if one was opened.

        Idempotent, and safe to call when the file was never opened.
        `Hwp5File` holds a reference cycle through its wrapper chain (each
        wrapper holds `self.wrapped`), so plain refcounting does not reclaim
        the underlying file descriptor when a caller simply drops the
        `HwpSource` -- callers that open many files in one process (e.g. CLI
        batch mode) must close explicitly or descriptors accumulate."""
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

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
        if self._section_names is None:
            # `self.hwp5file.bodytext` is raw OLE directory order, unfiltered
            # (BodyText can hold non-Section children) -- match the XML dump's
            # order instead (hwp5.xmlmodel.Sections.events() walks
            # Sections.section_indexes(), the same filter+numeric-sort), so a
            # section index derived from parsed XML lines up with the section
            # this returns at the same position.
            names = []
            for name in self.hwp5file.bodytext:
                if not name.startswith("Section"):
                    continue
                try:
                    idx = int(name[len("Section"):])
                except ValueError:
                    continue
                names.append((idx, name))
            names.sort(key=lambda pair: pair[0])
            self._section_names = [name for _, name in names]
        return self._section_names

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
            # A document with no \x05HwpSummaryInformation stream at all
            # raises out of the `summaryinfo` cached_property itself, before
            # any `_field` guard runs -- degrade to absent like _field does.
            try:
                si = self.hwp5file.summaryinfo
            except Exception:
                si = None
            created = _field(si, "createdTime")
            saved = _field(si, "lastSavedTime")
            self._summary = {
                "title": _strip(_field(si, "title")),
                "creator": _strip(_field(si, "author")),
                "subject": _strip(_field(si, "subject")),
                "description": _strip(_field(si, "comments")),
                "last_saved_by": _strip(_field(si, "lastSavedBy")),
                "created_date": _fmt_ts(created.datetime if created is not None else None),
                "modified_date": _fmt_ts(saved.datetime if saved is not None else None),
                "date": _strip(_field(si, "dateString")),
                "keyword": _strip(_field(si, "keywords")),
            }
        return self._summary


def _as_source(x):
    return x if isinstance(x, HwpSource) else HwpSource(x)
