"""Read HWP summary info (title/author/dates/...) via `hwp5proc summaryinfo`.

The body-XML HwpSummaryInfo element is an opaque PropertySetStream, so we
shell out to pyhwp's subcommand for its already-decoded `Key: value` text
instead of parsing that stream ourselves.
"""
import subprocess
from .reader import _hwp5proc
from .model import HwpSummaryInfo

_KEYS = {"Title": "title", "Author": "creator", "Subject": "subject",
         "Comments": "description", "Last saved by": "last_saved_by",
         "Created at": "created_date", "Last saved at": "modified_date",
         "Date": "date", "Keywords": "keyword"}
_TS = ("created_date", "modified_date")


def _fmt_ts(v):
    v = v.split(".", 1)[0].strip()          # drop fractional seconds
    return v.replace(" ", "T") + "Z" if v else ""


def read_summary_info(hwp_path):
    out = subprocess.run([_hwp5proc(), "summaryinfo", hwp_path],
                         capture_output=True).stdout.decode("utf-8", "replace")
    fields = {}
    for line in out.splitlines():
        if ": " not in line:
            continue
        key, val = line.split(": ", 1)
        attr = _KEYS.get(key.strip())
        if attr is None:
            continue
        val = val.strip()
        fields[attr] = _fmt_ts(val) if attr in _TS else val
    return HwpSummaryInfo(**fields)
