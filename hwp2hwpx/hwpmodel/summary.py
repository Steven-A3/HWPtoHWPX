"""Read HWP summary info (title/author/dates/...) via pyhwp's in-process API.

The body-XML HwpSummaryInfo element is an opaque PropertySetStream; HwpSource
decodes it through pyhwp's OLE property-set accessor instead of parsing that
stream ourselves.
"""
from .source import _as_source
from .model import HwpSummaryInfo


def read_summary_info(source):
    return HwpSummaryInfo(**_as_source(source).summary())
