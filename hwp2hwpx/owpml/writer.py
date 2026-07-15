"""Assemble an OWPML document into a .hwpx ZIP package."""
import zipfile
from .. import constants


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
