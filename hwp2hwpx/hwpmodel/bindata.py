"""Extract embedded image binaries from an HWP file for the HWPX package.

The image bytes live in the HWP OLE2 storage as BinData/BIN000N.<ext>.
`hwp5proc cat` returns them already decompressed (byte-identical to what
Hancom embeds), so no transcoding is needed here.
"""
import subprocess
from ..owpml.model import BinItem
from .reader import _hwp5proc

# Hancom spells the .jpg media type "image/jpg" (non-standard, but that's
# what content.hpf ships) -- matched here for fidelity, not RFC compliance.
# ".jpeg"-extension files keep the standard "image/jpeg".
_MEDIA = {"bmp": "image/bmp", "png": "image/png", "jpg": "image/jpg",
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


def _collect_drawing_bindata_ids(d, ids):
    """A pic's bindata id, plus (recursively) any pic nested inside a $con
    container -- a container's ShapeComponent children are never their own
    top-level run.drawing, so this walk is the only way to reach them.

    KNOWN LIMITATION: a pic nested inside a Rect's text box
    (`d.rect.draw_text.paragraphs`, i.e. a picture placed in a drawn
    rectangle's caption/text area) is NOT reached -- this walk only
    recurses `d.children`, not into `draw_text.paragraphs`. The mapper
    (`drawing._map_rect`) does map that nested paragraph's drawing via
    `map_paragraph`, so if such a pic exists, it produces a dangling
    `binaryItemIDRef` (no embedded file) and its bindata-id is missing
    from `id_to_index`, so `_map_pic`'s fallback-to-raw-id can collide
    with a renumbered index of an unrelated image. No current sample
    triggers this; fixing it (recursing into draw_text paragraphs here)
    is out of scope until a sample exercises the path."""
    if d is None:
        return
    if d.kind == "pic" and d.picture is not None and d.picture.bindata_id not in ids:
        ids.append(d.picture.bindata_id)
    for child in d.children:
        _collect_drawing_bindata_ids(child, ids)


def _collect_pic_bindata_ids(hwp_doc):
    ids = []
    for sec in hwp_doc.sections:
        for para in _iter_all_paragraphs(sec.paragraphs):
            for run in para.runs:
                _collect_drawing_bindata_ids(getattr(run, "drawing", None), ids)
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
    """Returns (items, id_to_index): items named image{index} by document
    order of first reference (matching Hancom's naming), and the
    bindata-id -> sequential-index map so the mapper can resolve
    binaryItemIDRef the same way."""
    ids = _collect_pic_bindata_ids(hwp_doc)
    if not ids:
        return [], {}
    id_to_index = {bid: i for i, bid in enumerate(ids, 1)}
    streams = _list_bindata_streams(hwp_path)
    items = []
    for bid in ids:
        stream = streams.get(bid)
        if stream is None:
            continue   # referenced stream missing: skip (pic still refs image{index})
        idx = id_to_index[bid]
        ext = stream.rsplit(".", 1)[-1].lower() if "." in stream else "bin"
        data = subprocess.run([_hwp5proc(), "cat", hwp_path, stream],
                              capture_output=True).stdout
        items.append(BinItem(
            id="image%d" % idx,
            filename="image%d.%s" % (idx, ext),
            media_type=_MEDIA.get(ext, "application/octet-stream"),
            data=data,
        ))
    return items, id_to_index
