"""Assemble an OWPML document into a .hwpx ZIP package."""
import os
import tempfile
import zipfile
from .. import constants
from . import package_parts
from .header_writer import header_xml
from .section_writer import section_xml


def _umask_file_mode():
    # tempfile.mkstemp creates 0600. Replacing the destination with it would
    # make every converted document owner-only, so restore the mode a normal
    # create would have produced. Reading the umask requires setting it.
    umask = os.umask(0o022)
    os.umask(umask)
    return 0o666 & ~umask


def write_package(parts, out_path):
    """Write `parts` (name->bytes) to a .hwpx ZIP.

    The `mimetype` entry is always written first and STORED (uncompressed),
    as Hancom requires. A caller-supplied "mimetype" value overrides the default.

    The package is built at a temporary path in the destination directory and
    moved into place with os.replace, which is atomic within a filesystem. An
    interrupted write therefore never leaves a truncated .hwpx where a complete
    one is expected -- batch mode skips outputs that already exist, so a corpse
    left at the destination would be treated as a finished conversion forever.
    """
    mimetype = parts.get("mimetype", constants.MIMETYPE.encode("ascii"))
    if isinstance(mimetype, str):
        mimetype = mimetype.encode("ascii")
    out_dir = os.path.dirname(os.path.abspath(out_path))
    fd, tmp_path = tempfile.mkstemp(dir=out_dir, prefix=".hwp2hwpx-", suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(zipfile.ZipInfo("mimetype"), mimetype,
                       compress_type=zipfile.ZIP_STORED)
            for name, data in parts.items():
                if name == "mimetype":
                    continue
                z.writestr(name, data)
        os.chmod(tmp_path, _umask_file_mode())
        os.replace(tmp_path, out_path)
    except BaseException:
        # BaseException, not Exception: KeyboardInterrupt mid-batch is exactly
        # the case that must not strand a temp file next to the output.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_hwpx(doc, out_path):
    parts = {
        "version.xml": package_parts.version_xml(),
        "settings.xml": package_parts.settings_xml(),
        "Contents/header.xml": header_xml(doc.header, sec_cnt=len(doc.sections)),
        "Contents/content.hpf": package_parts.content_hpf(
            doc.metadata, len(doc.sections), getattr(doc, "bin_items", [])),
        "META-INF/container.xml": package_parts.container_xml(),
        "META-INF/container.rdf": package_parts.container_rdf(len(doc.sections)),
        "META-INF/manifest.xml": package_parts.manifest_xml(),
        "Preview/PrvText.txt": package_parts.prv_text(doc.sections),
    }
    if doc.prv_image is not None:
        parts["Preview/PrvImage.png"] = doc.prv_image
    for i, section in enumerate(doc.sections):
        parts["Contents/section%d.xml" % i] = section_xml(section)
    for item in getattr(doc, "bin_items", []):
        parts["BinData/%s" % item.filename] = item.data
    write_package(parts, out_path)
