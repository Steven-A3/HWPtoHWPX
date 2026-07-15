import zipfile
from hwp2hwpx.owpml.writer import write_package
from hwp2hwpx.constants import MIMETYPE


def test_mimetype_first_and_stored(tmp_path):
    out = tmp_path / "out.hwpx"
    write_package({"version.xml": b"<x/>"}, str(out))
    with zipfile.ZipFile(out) as z:
        infos = z.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert z.read("mimetype").decode() == MIMETYPE
        assert z.read("version.xml") == b"<x/>"
