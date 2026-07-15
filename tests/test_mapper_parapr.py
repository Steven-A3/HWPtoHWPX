from hwp2hwpx.mapper.para_pr import map_para_shapes
from hwp2hwpx.hwpmodel.model import HwpParaShape


def test_map_para_shape_align():
    out = map_para_shapes([HwpParaShape(index=0, align="CENTER"),
                           HwpParaShape(index=1, align="JUSTIFY")])
    assert [p.id for p in out] == [0, 1]
    assert [p.align for p in out] == ["CENTER", "JUSTIFY"]
