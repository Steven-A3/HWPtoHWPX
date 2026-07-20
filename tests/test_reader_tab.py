from hwp2hwpx.hwpmodel.reader import read_document
from hwp2hwpx.hwpmodel.model import HwpControl
from tests.samplepaths import S4

SAMPLE2 = S4


def _all_controls():
    from hwp2hwpx.hwpmodel.reader import hwp5_xml
    doc = read_document(hwp5_xml(SAMPLE2))
    kinds = set()

    def walk(paras):
        for p in paras:
            for r in p.runs:
                for item in r.contents:
                    if isinstance(item, HwpControl):
                        kinds.add(item.kind)
                if r.table is not None:
                    for row in r.table.table_rows:
                        for cell in row.cells:
                            walk(cell.paragraphs)
    for sec in doc.sections:
        walk(sec.paragraphs)
    return kinds


def test_tab_control_parsed():
    assert "tab" in _all_controls()
