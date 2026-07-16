"""Assemble an OWPML document into a .hwpx ZIP package."""
import zipfile
from .. import constants
from . import package_parts
from .header_writer import header_xml
from .section_writer import section_xml


def write_package(parts, out_path):
    """Write `parts` (name->bytes) to a .hwpx ZIP.

    The `mimetype` entry is always written first and STORED (uncompressed),
    as Hancom requires. A caller-supplied "mimetype" value overrides the default.
    """
    mimetype = parts.get("mimetype", constants.MIMETYPE.encode("ascii"))
    if isinstance(mimetype, str):
        mimetype = mimetype.encode("ascii")
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), mimetype, compress_type=zipfile.ZIP_STORED)
        for name, data in parts.items():
            if name == "mimetype":
                continue
            z.writestr(name, data)


def write_hwpx(doc, out_path):
    parts = {
        "version.xml": package_parts.version_xml(),
        "settings.xml": package_parts.settings_xml(),
        "Contents/header.xml": header_xml(doc.header, sec_cnt=len(doc.sections)),
        "Contents/content.hpf": package_parts.content_hpf(
            doc.metadata, len(doc.sections), getattr(doc, "bin_items", [])),
        "META-INF/container.xml": package_parts.container_xml(),
        "META-INF/manifest.xml": package_parts.manifest_xml(),
        "Preview/PrvText.txt": package_parts.prv_text(doc.sections),
    }
    for i, section in enumerate(doc.sections):
        parts["Contents/section%d.xml" % i] = section_xml(section)
    for item in getattr(doc, "bin_items", []):
        parts["BinData/%s" % item.filename] = item.data
    write_package(parts, out_path)
