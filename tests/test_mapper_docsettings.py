from hwp2hwpx.hwpmodel.model import (
    HwpDocProperties, HwpCompatDocument, HwpDocInfo, HwpDocument,
)
from hwp2hwpx.mapper.docsettings import map_begin_num, map_compat
from hwp2hwpx.mapper.body import map_document


def test_map_begin_num_passthrough():
    bn = map_begin_num(HwpDocProperties(page_start=2, footnote_start=3,
                                        endnote_start=4, pic_start=5,
                                        tbl_start=6, equation_start=7))
    assert (bn.page, bn.footnote, bn.endnote, bn.pic, bn.tbl, bn.equation) == \
        (2, 3, 4, 5, 6, 7)


def test_map_begin_num_none_defaults():
    bn = map_begin_num(None)
    assert bn.page == 1 and bn.equation == 1


def test_map_compat_target_map():
    assert map_compat(HwpCompatDocument(target=0)).target_program == "HWP201X"
    assert map_compat(HwpCompatDocument(target=99)).target_program == "HWP201X"
    assert map_compat(None).target_program == "HWP201X"


def test_map_document_attaches_docsettings():
    doc = HwpDocument(docinfo=HwpDocInfo(
        doc_properties=HwpDocProperties(page_start=9),
        compat=HwpCompatDocument(target=0)), sections=[])
    header = map_document(doc).header
    assert header.begin_num.page == 9
    assert header.compat.target_program == "HWP201X"
