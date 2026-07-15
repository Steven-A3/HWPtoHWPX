"""Normalize XML and unzip HWPX parts for fidelity comparison."""
import zipfile
from lxml import etree


def unzip_parts(hwpx_path):
    parts = {}
    with zipfile.ZipFile(hwpx_path) as z:
        for name in z.namelist():
            parts[name] = z.read(name)
    return parts


def canonical(xml_bytes):
    parser = etree.XMLParser(remove_blank_text=True, remove_comments=True)
    root = etree.fromstring(xml_bytes, parser)
    _sort_attrs(root)
    for el in root.iter():
        if el.text and not el.text.strip():
            el.text = None
        if el.tail and not el.tail.strip():
            el.tail = None
    return etree.tostring(root, encoding="unicode")


def _sort_attrs(el):
    for child in el.iter():
        attrs = sorted(child.attrib.items())
        for k in list(child.attrib):
            del child.attrib[k]
        for k, v in attrs:
            child.set(k, v)
