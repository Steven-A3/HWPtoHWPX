"""Top-level HWP -> HWPX conversion."""
import os
from .hwpmodel.reader import hwp5_xml, read_document
from .hwpmodel.bindata import extract_bin_items
from .hwpmodel.rangetags import attach_range_tags
from .hwpmodel.summary import read_summary_info
from .mapper.body import map_document
from .owpml.writer import write_hwpx


def convert(hwp_path, out_path):
    xml = hwp5_xml(hwp_path)
    hwp_doc = read_document(xml)
    attach_range_tags(hwp_path, hwp_doc)
    hwp_doc.summary_info = read_summary_info(hwp_path)
    title = os.path.splitext(os.path.basename(hwp_path))[0]
    items, bin_index = extract_bin_items(hwp_path, hwp_doc)
    owpml_doc = map_document(hwp_doc, title=title, bin_index=bin_index)
    owpml_doc.bin_items = items
    write_hwpx(owpml_doc, out_path)
