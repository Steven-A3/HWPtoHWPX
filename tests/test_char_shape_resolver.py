from tests.samplepaths import hwp as _hwp

from hwp2hwpx.hwpmodel.reader import hwp5_char_shapes, _item_width, _resolve_item_char_shapes

S2013 = _hwp("2013")


def test_char_shapes_first_para_is_secpr_shape():
    arrs = hwp5_char_shapes(S2013)
    # para 0 (secPr): single position-0 segment, charshape 155
    assert arrs[0] == [(0, 155)]


def test_char_shapes_table_para_192_positions():
    # 192nd top-level para is a table-only paragraph: table at pos 0 (cs 46),
    # paragraph-break at pos 8 (cs 141). hwp5_char_shapes returns ALL paras
    # (incl. nested) in document order, so index != top-level index; assert the
    # array shape exists among returned arrays.
    arrs = hwp5_char_shapes(S2013)
    assert [(0, 46), (8, 141)] in arrs


def test_item_widths():
    assert _item_width("Text", "abc") == 3
    assert _item_width("Text", " ") == 2        # BMP PUA + space
    assert _item_width("Text", "\U00010000") == 2    # supplementary -> 2 UTF-16
    assert _item_width("ControlChar", None) == 1
    assert _item_width("TableControl", None) == 8
    assert _item_width("GShapeObjectControl", None) == 8


def test_resolver_assigns_object_char_shape_from_array():
    # table (pos 0) then paragraph-break (pos 8): table -> 46, break -> 141
    items = [("TableControl", None, None), ("ControlChar", None, "141")]
    arr = [(0, 46), (8, 141)]
    shapes, mism = _resolve_item_char_shapes(items, arr)
    assert shapes == [46, 141]
    assert mism == 0


def test_resolver_consistency_across_samples():
    # Every Text/ControlChar item's array-looked-up cs must equal its xml cs,
    # for top-level paragraphs. 0 mismatches on samples 3 & 4; exactly 7 on
    # 2013 (category-A bullet paras where hwp5proc's own attribution diverges
    # from the raw array).
    #
    # hwp5_char_shapes() and root.findall(".//Paragraph") both walk the same
    # underlying record stream in depth-first pre-order over ALL paragraphs
    # (top-level and nested), so the two sequences line up index-for-index;
    # zip() correlates each XML paragraph with its char-shape array without
    # needing to separately re-derive the nesting structure. We then restrict
    # the mismatch tally to top-level paragraphs only -- full-document (nested)
    # correlation is finalized in Task 3.
    from hwp2hwpx.hwpmodel.reader import hwp5_xml, _para_items
    from lxml import etree

    expected = {"3.": 0, "4.": 0, "2013": 7}
    for pre, exp in expected.items():
        hwp = _hwp(pre)
        root = etree.fromstring(hwp5_xml(hwp))
        all_paras = root.findall(".//Paragraph")
        arrs = hwp5_char_shapes(hwp)
        top_paras = [
            p
            for sec in root.findall(".//SectionDef")
            for col in sec.findall("ColumnSet")
            for p in col.findall("Paragraph")
        ]
        top_ids = set(id(p) for p in top_paras)

        total = 0
        for p, arr in zip(all_paras, arrs):
            if id(p) not in top_ids:
                continue
            items = _para_items(p)
            _, m = _resolve_item_char_shapes(items, arr or [(0, 0)])
            total += m
        assert total == exp, (pre, total)


def test_full_document_correlation_map_and_mismatch():
    # Task 3 correlates EVERY paragraph (top-level and nested cell/textbox) with
    # its char-shape array via _build_char_shape_map. The map must cover all
    # paragraphs, and the document-wide Text/ControlChar mismatch tally stays at
    # the known invariant (0 on samples 3 & 4, 7 on 2013 -- the category-A
    # bullet paragraphs), i.e. nested paragraphs add no new mismatches.
    from hwp2hwpx.hwpmodel.reader import (
        hwp5_xml, _para_items, _build_char_shape_map)
    from lxml import etree

    expected = {"3.": 0, "4.": 0, "2013": 7}
    for pre, exp in expected.items():
        hwp = _hwp(pre)
        root = etree.fromstring(hwp5_xml(hwp))
        cs_map = _build_char_shape_map(root, hwp5_char_shapes(hwp))
        all_paras = root.findall(".//Paragraph")
        assert len(cs_map) == len(all_paras)   # every paragraph correlated
        total = 0
        for p in all_paras:
            arr = cs_map.get(p)
            if not arr:
                continue
            _, m = _resolve_item_char_shapes(_para_items(p), arr)
            total += m
        assert total == exp, (pre, total)
