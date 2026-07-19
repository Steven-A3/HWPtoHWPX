"""Extract embedded image binaries from an HWP file for the HWPX package.

The image bytes live in the HWP OLE2 storage as BinData/BIN000N.<ext>, already
decompressed (byte-identical to what Hancom embeds), so no transcoding is
needed here.
"""
from ..owpml.model import BinItem
from .source import _as_source

# Hancom spells the .jpg media type "image/jpg" (non-standard, but that's
# what content.hpf ships) -- matched here for fidelity, not RFC compliance.
# ".jpeg"-extension files keep the standard "image/jpeg".
_MEDIA = {"bmp": "image/bmp", "png": "image/png", "jpg": "image/jpg",
          "jpeg": "image/jpeg", "gif": "image/gif", "wmf": "image/x-wmf",
          "tiff": "image/tiff", "tif": "image/tiff"}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _iter_all_paragraphs(paragraphs):
    for para in paragraphs:
        yield para
        for run in para.runs:
            for tbl in getattr(run, "tables", []):
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
                for d in getattr(run, "drawings", []):
                    _collect_drawing_bindata_ids(d, ids)
    return ids


def _stream_num(base):
    """Stream number of a 'BINxxxx.ext' name. pyhwp names BinData streams
    BIN%04X (hex), while `PictureInfo bindata-id` is decimal — so parse the
    stream number as hex to make the two agree for ids >= 10 (e.g. BIN000A
    corresponds to bindata-id 10, not the ValueError that int('000A') raises)."""
    return int(base[3:].split(".", 1)[0], 16)   # 'BIN000A.bmp' -> 10


def _bindata_dir(src):
    """Top-level storage/stream names in the HWP file (a document with no
    BinData folder yields a set without 'BinData')."""
    return set(iter(src.hwp5file))


def _list_bindata_streams(source):
    """{id_int: 'BinData/BIN000N.ext'}."""
    src = _as_source(source)
    streams = {}
    for name in src.hwp5file["BinData"] if "BinData" in _bindata_dir(src) else []:
        base = name  # e.g. "BIN0001.bmp"
        if base.startswith("BIN"):
            try:
                streams[_stream_num(base)] = "BinData/" + base
            except ValueError:
                pass
    return streams


def extract_bin_items(source, hwp_doc):
    """Returns (items, id_to_index): items named image{index} by document
    order of first reference (matching Hancom's naming), and the
    bindata-id -> sequential-index map so the mapper can resolve
    binaryItemIDRef the same way."""
    src = _as_source(source)
    ids = _collect_pic_bindata_ids(hwp_doc)
    if not ids:
        return [], {}
    id_to_index = {bid: i for i, bid in enumerate(ids, 1)}
    streams = _list_bindata_streams(src)
    items = []
    for bid in ids:
        stream = streams.get(bid)
        if stream is None:
            continue   # referenced stream missing: skip (pic still refs image{index})
        idx = id_to_index[bid]
        ext = stream.rsplit(".", 1)[-1].lower() if "." in stream else "bin"
        data = src.stream_bytes(stream)
        if data is None:
            continue   # unreadable stream: skip (pic still refs image{index})
        items.append(BinItem(
            id="image%d" % idx,
            filename="image%d.%s" % (idx, ext),
            media_type=_MEDIA.get(ext, "application/octet-stream"),
            data=data,
        ))
    return items, id_to_index


def _preview_png_or_none(data):
    """Return `data` iff it is a PNG (by signature), else None."""
    return data if data.startswith(_PNG_SIGNATURE) else None


def extract_preview_image(source):
    """Return the source HWP's PrvImage stream bytes iff they are a PNG, else
    None.

    Hancom re-renders the preview at export, so this is a best-effort *usable*
    thumbnail, not a byte-match of Hancom's output. Non-PNG sources (GIF/BMP)
    are skipped because an honest transcode to .png would need an imaging
    dependency the project deliberately avoids.
    """
    data = _as_source(source).stream_bytes("PrvImage")
    if data is None:
        return None
    return _preview_png_or_none(data)
