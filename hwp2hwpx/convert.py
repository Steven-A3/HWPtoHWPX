"""Top-level HWP -> HWPX conversion."""
import os
from .hwpmodel.reader import hwp5_xml, read_document
from .hwpmodel.bindata import extract_bin_items
from .hwpmodel.rangetags import attach_range_tags
from .mapper.body import map_document
from .owpml.writer import write_hwpx


def convert(hwp_path, out_path):
    xml = hwp5_xml(hwp_path)
    hwp_doc = read_document(xml)
    attach_range_tags(hwp_path, hwp_doc)
    title = os.path.splitext(os.path.basename(hwp_path))[0]
    owpml_doc = map_document(hwp_doc, title=title)
    owpml_doc.bin_items = extract_bin_items(hwp_path, hwp_doc)
    write_hwpx(owpml_doc, out_path)
