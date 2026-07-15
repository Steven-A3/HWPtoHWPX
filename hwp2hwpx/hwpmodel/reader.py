"""Read a .hwp file into an in-memory model, via pyhwp's hwp5proc XML dump."""
import subprocess


def hwp5_xml(hwp_path):
    """Return pyhwp's full XML dump of the parsed HWP record tree."""
    return subprocess.check_output(["hwp5proc", "xml", hwp_path])
