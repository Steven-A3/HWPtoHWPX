from hwp2hwpx.hwpmodel.model import (
    HwpSectionDef, HwpPageDef, HwpNoteShape, HwpPageBorder, HwpColumnsDef,
    HwpPageNum, HwpSection, HwpDocInfo, HwpDocument,
)
from hwp2hwpx.mapper.section import map_section_def
from hwp2hwpx.mapper.body import map_document


def _full_sd():
    return HwpSectionDef(
        column_spacing=1134, default_tab_stops=8000, text_direction=0,
        numbering_shape_id=0, hide_blank_line=1,
        page=HwpPageDef(width=59528, height=84188, orientation="portrait",
                        bookbinding="left", left_offset=6000, right_offset=5528,
                        top_offset=4536, bottom_offset=4252,
                        header_offset=1964, footer_offset=1436),
        footnote=HwpNoteShape(stroke_type="solid", line_width="0.12mm",
                              splitter_length=-1, notes_spacing=284,
                              splitter_margin_top=852, splitter_margin_bottom=568,
                              suffix=")", starting_number=1),
        endnote=HwpNoteShape(stroke_type="none", line_width="0.12mm",
                             splitter_length=0, starting_number=1, suffix=")"),
        page_borders=[HwpPageBorder(borderfill_id=1, margin_left=1417,
                                    margin_right=1417, margin_top=1417,
                                    margin_bottom=1417) for _ in range(3)],
        columns=HwpColumnsDef(count=1, kind="normal", direction="l2r"),
        page_num=HwpPageNum(position="bottom_center", shape=0, dash="-"),
    )


def test_maps_scalar_and_enum_fields():
    sp = map_section_def(_full_sd())
    assert sp.text_direction == "HORIZONTAL"
    assert sp.space_columns == 1134 and sp.tab_stop == 8000
    assert sp.page_pr.landscape == "WIDELY"
    assert sp.page_pr.width == 59528
    assert sp.page_pr.margin.left == 6000 and sp.page_pr.margin.header == 1964
    assert sp.page_pr.gutter_type == "LEFT_ONLY"
    assert sp.visibility.hide_first_empty_line == 1
    assert sp.col_pr.type == "NEWSPAPER" and sp.col_pr.layout == "LEFT"
    assert sp.page_num.pos == "BOTTOM_CENTER" and sp.page_num.side_char == "-"


def test_maps_footnote_and_endnote_and_note_width_space():
    sp = map_section_def(_full_sd())
    assert sp.foot_note_pr.note_line.type == "SOLID"
    assert sp.foot_note_pr.note_line.width == "0.12 mm"  # space inserted
    assert sp.foot_note_pr.note_line.length == -1
    assert sp.foot_note_pr.note_spacing.between_notes == 284
    assert sp.foot_note_pr.placement.place == "EACH_COLUMN"
    assert sp.end_note_pr.note_line.type == "NONE"
    assert sp.end_note_pr.placement.place == "END_OF_DOCUMENT"


def test_three_page_border_fills_typed_by_index():
    sp = map_section_def(_full_sd())
    assert [b.type for b in sp.page_border_fills] == ["BOTH", "EVEN", "ODD"]
    assert sp.page_border_fills[0].offset.left == 1417
    assert sp.page_border_fills[0].text_border == "PAPER"


def test_absence_paths_emit_nothing():
    sd = HwpSectionDef()  # no page, no notes, no borders, no columns, no page_num
    sp = map_section_def(sd)
    assert sp.page_pr is None
    assert sp.foot_note_pr is None and sp.end_note_pr is None
    assert sp.page_border_fills == []
    assert sp.col_pr is None and sp.page_num is None


def test_columns_count_two():
    sd = HwpSectionDef(columns=HwpColumnsDef(count=2))
    assert map_section_def(sd).col_pr.col_count == 2


def test_none_maps_to_none():
    assert map_section_def(None) is None


def test_map_document_attaches_sec_pr_per_section():
    doc = HwpDocument(
        docinfo=HwpDocInfo(),
        sections=[HwpSection(paragraphs=[], sec_def=HwpSectionDef(column_spacing=11)),
                  HwpSection(paragraphs=[], sec_def=HwpSectionDef(column_spacing=22))],
    )
    out = map_document(doc)
    assert out.sections[0].sec_pr.space_columns == 11
    assert out.sections[1].sec_pr.space_columns == 22
