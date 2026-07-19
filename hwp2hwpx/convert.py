"""Top-level HWP -> HWPX conversion."""
import os
from .hwpmodel.reader import (
    hwp5_xml, hwp5_char_shapes, hwp5_char_shape_border_fills, read_document,
)
from .hwpmodel.bindata import extract_bin_items, extract_preview_image
from .hwpmodel.rangetags import attach_range_tags
from .hwpmodel.summary import read_summary_info
from .hwpmodel.source import HwpSource
from .mapper.body import map_document
from .owpml.writer import write_hwpx


def convert(hwp_path, out_path):
    src = HwpSource(hwp_path)
    xml = hwp5_xml(src)
    hwp_doc = read_document(
        xml, hwp5_char_shapes(src),
        char_border_fills=hwp5_char_shape_border_fills(src),
    )
    attach_range_tags(src, hwp_doc)
    hwp_doc.summary_info = read_summary_info(src)
    title = os.path.splitext(os.path.basename(hwp_path))[0]
    items, bin_index = extract_bin_items(src, hwp_doc)
    owpml_doc = map_document(hwp_doc, title=title, bin_index=bin_index)
    owpml_doc.bin_items = items
    owpml_doc.prv_image = extract_preview_image(src)
    write_hwpx(owpml_doc, out_path)
