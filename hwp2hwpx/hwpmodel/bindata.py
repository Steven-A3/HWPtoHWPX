"""Extract embedded image binaries from an HWP file for the HWPX package.

The image bytes live in the HWP OLE2 storage as BinData/BIN000N.<ext>.
`hwp5proc cat` returns them already decompressed (byte-identical to what
Hancom embeds), so no transcoding is needed here.
"""
import subprocess
from ..owpml.model import BinItem
from .reader import _hwp5proc

_MEDIA = {"bmp": "image/bmp", "png": "image/png", "jpg": "image/jpeg",
          "jpeg": "image/jpeg", "gif": "image/gif", "wmf": "image/x-wmf",
          "tiff": "image/tiff", "tif": "image/tiff"}


def _iter_all_paragraphs(paragraphs):
    for para in paragraphs:
        yield para
        for run in para.runs:
            tbl = getattr(run, "table", None)
            if tbl is not None:
                for row in tbl.table_rows:
                    for cell in row.cells:
                        for p in _iter_all_paragraphs(cell.paragraphs):
                            yield p


def _collect_pic_bindata_ids(hwp_doc):
    ids = []
    for sec in hwp_doc.sections:
        for para in _iter_all_paragraphs(sec.paragraphs):
            for run in para.runs:
                d = getattr(run, "drawing", None)
                if (d is not None and d.kind == "pic" and d.picture is not None
                        and d.picture.bindata_id not in ids):
                    ids.append(d.picture.bindata_id)
    return ids


def _stream_num(base):
    """Stream number of a 'BINxxxx.ext' name. pyhwp names BinData streams
    BIN%04X (hex), while `PictureInfo bindata-id` is decimal — so parse the
    stream number as hex to make the two agree for ids >= 10 (e.g. BIN000A
    corresponds to bindata-id 10, not the ValueError that int('000A') raises)."""
    return int(base[3:].split(".", 1)[0], 16)   # 'BIN000A.bmp' -> 10


def _list_bindata_streams(hwp_path):
    """{id_int: 'BinData/BIN000N.ext'} from `hwp5proc ls`."""
    out = subprocess.run([_hwp5proc(), "ls", hwp_path],
                         capture_output=True).stdout.decode(errors="replace")
    streams = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("BinData/BIN"):
            base = line.rsplit("/", 1)[-1]        # BIN0001.bmp
            try:
                streams[_stream_num(base)] = line
            except ValueError:
                pass
    return streams


def extract_bin_items(hwp_path, hwp_doc):
    ids = _collect_pic_bindata_ids(hwp_doc)
    if not ids:
        return []
    streams = _list_bindata_streams(hwp_path)
    items = []
    for bid in ids:
        stream = streams.get(bid)
        if stream is None:
            continue   # referenced stream missing: skip (pic still refs image{bid})
        ext = stream.rsplit(".", 1)[-1].lower() if "." in stream else "bin"
        data = subprocess.run([_hwp5proc(), "cat", hwp_path, stream],
                              capture_output=True).stdout
        items.append(BinItem(
            id="image%d" % bid,
            filename="image%d.%s" % (bid, ext),
            media_type=_MEDIA.get(ext, "application/octet-stream"),
            data=data,
        ))
    return items
