# Drawing Objects — Slice B (pictures + binary BinData) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `<hp:pic>` (one per HWP picture) with its embedded image extracted byte-identically from the HWP and declared in `content.hpf`. On sample 4: `hp:pic`==3, three `BinData/imageN.bmp` byte-identical to Hancom's. Sample 3 (no drawings) unchanged.

**Architecture:** Reuses Slice A's GSO container (via a shared mapper helper). New: reader `$pic` parsing, `extract_bin_items` (via `hwp5proc cat`), `Pic`/`BinItem` models, `_write_pic`, and `content.hpf`/ZIP binary emission. `Run.drawing` becomes polymorphic (`Line`|`Pic`); the writer dispatches by `isinstance`.

**Tech Stack:** Python 3.9+, lxml, pyhwp (`hwp5proc xml`/`ls`/`cat`), pytest.

## Global Constraints

- **Python 3.9 floor:** NO `X | None`; forward-ref-string defaults, `field(default_factory=...)`.
- **Run tests with `.venv/bin/python -m pytest`** — plain `python`/`python3` lacks `hwp5proc`.
- **Correctness gate:** count-based for the pic subtree (`hp:pic`==3, `img`/`imgRect`/`pt0-3`/`imgClip`/`imgDim`/`effects`/`shapeComment`/`inMargin` present) PLUS two EXACT checks — each `BinData/imageN.bmp` byte-identical to Hancom's, and `content.hpf` declares each image. Sample 3 unchanged (no `BinData/`, no image `opf:item`).
- **Two namespaces:** `hc:` for `transMatrix`/`scaMatrix`/`rotMatrix`/`img`/`pt0..pt3`; `hp:` for the rest.
- **Reuse Slice A container mapping** via a shared helper (DRY) — do not duplicate the offset/orgSz/curSz/flip/rotationInfo/renderingInfo/sz/pos/outMargin logic.
- Samples at `samples/4.…hwp[x]`, `samples/3.…hwp[x]` (present locally). Reader/mapper/writer unit tests use synthetic inputs; sample-dependent checks live in the e2e task.

### Verified mappings

- `PictureInfo bindata-id="N"` → stream `BinData/BIN000N.<ext>` → `BinData/imageN.<ext>`, `hc:img binaryItemIDRef="imageN"`.
- `hwp5proc cat <hwp> BinData/BIN000N.bmp` → byte-identical bytes (no decompression).
- media-type by extension: bmp→image/bmp, png→image/png, jpg/jpeg→image/jpeg, gif→image/gif, wmf→image/x-wmf, default application/octet-stream.
- pic container differs from line only by `rotationInfo rotateimage="1"` (line: 0) and element attr `reverse="0"` (line: `isReverseHV="0"`).
- `img effect`: PictureInfo `effect=0` → `"REAL_PIC"` (default REAL_PIC).

---

### Task 1: Models — HwpPicture, Pic, BinItem

**Files:**
- Modify: `hwp2hwpx/hwpmodel/model.py`, `hwp2hwpx/owpml/model.py`
- Test: `tests/test_model_picture.py`

**Interfaces:**
- Produces: `HwpPicture`; `HwpDrawing.picture`. OWPML `Pic` + `Img`/`ImgRect`/`ImgClip`/`InMargin`/`ImgDim`/`ShapeComment`; `BinItem`; `OwpmlDocument.bin_items`. (`Pt`, `Offset`, container dataclasses already exist from Slice A.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_picture.py
from hwp2hwpx.hwpmodel.model import HwpPicture, HwpDrawing
from hwp2hwpx.owpml.model import (
    Pic, Img, ImgRect, ImgClip, InMargin, ImgDim, ShapeComment, BinItem,
    OwpmlDocument, Header, Metadata,
)


def test_hwp_picture_defaults():
    p = HwpPicture()
    assert p.bindata_id == 0
    assert p.img_rect == [(0, 0), (0, 0), (0, 0), (0, 0)]
    assert p.img_clip == (0, 0, 0, 0)
    assert HwpDrawing(kind="pic", picture=p).picture.bindata_id == 0


def test_owpml_pic_and_binitem_defaults():
    assert Img().effect == "REAL_PIC"
    assert Pic(id=5).text_wrap == "TOP_AND_BOTTOM"
    assert Pic().img is None and Pic().shape_comment is None
    b = BinItem(id="image1", filename="image1.bmp", media_type="image/bmp", data=b"BM")
    assert b.data == b"BM"


def test_owpml_document_has_bin_items():
    d = OwpmlDocument(header=Header(), sections=[], metadata=Metadata())
    assert d.bin_items == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_model_picture.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add HWP-side dataclasses**

Add to `hwp2hwpx/hwpmodel/model.py` (after `HwpLineShape`; `field` already imported):

```python
@dataclass
class HwpPicture:
    instance_id: int = 0
    bindata_id: int = 0
    img_rect: list = field(default_factory=lambda: [(0, 0), (0, 0), (0, 0), (0, 0)])
    img_clip: tuple = (0, 0, 0, 0)   # left, right, top, bottom
    brightness: int = 0
    contrast: int = 0
    effect: int = 0
    dim_width: int = 0
    dim_height: int = 0
```

Modify `HwpDrawing` to add `picture` (keep all existing fields including `line`):

```python
    component: "HwpShapeComponent" = None
    line: "HwpLineShape" = None
    picture: "HwpPicture" = None
```

- [ ] **Step 4: Add OWPML-side dataclasses**

Add to `hwp2hwpx/owpml/model.py` (after `Line`; `Pt` already exists):

```python
@dataclass
class Img:
    bin_item_id: str = "image0"
    bright: int = 0
    contrast: int = 0
    effect: str = "REAL_PIC"
    alpha: int = 0


@dataclass
class ImgRect:
    pt0: "Pt" = None
    pt1: "Pt" = None
    pt2: "Pt" = None
    pt3: "Pt" = None


@dataclass
class ImgClip:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class InMargin:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


@dataclass
class ImgDim:
    dim_width: int = 0
    dim_height: int = 0


@dataclass
class ShapeComment:
    text: str = ""


@dataclass
class Pic:
    id: int = 0
    z_order: int = 0
    text_wrap: str = "TOP_AND_BOTTOM"
    text_flow: str = "BOTH_SIDES"
    instid: int = 0
    reverse: int = 0
    offset: "Offset" = None
    org_sz: "OrgSz" = None
    cur_sz: "CurSz" = None
    flip: "Flip" = None
    rotation_info: "RotationInfo" = None
    rendering_info: "RenderingInfo" = None
    img: "Img" = None
    img_rect: "ImgRect" = None
    img_clip: "ImgClip" = None
    in_margin: "InMargin" = None
    img_dim: "ImgDim" = None
    sz: "ShapeSz" = None
    pos: "ShapePos" = None
    out_margin: "ShapeOutMargin" = None
    shape_comment: "ShapeComment" = None


@dataclass
class BinItem:
    id: str = ""
    filename: str = ""
    media_type: str = "application/octet-stream"
    data: bytes = b""
```

Modify `OwpmlDocument` to add `bin_items` (keep existing fields):

```python
@dataclass
class OwpmlDocument:
    header: Header
    sections: list
    metadata: Metadata
    bin_items: list = field(default_factory=list)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_model_picture.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/model.py hwp2hwpx/owpml/model.py tests/test_model_picture.py
git commit -m "feat: HwpPicture / Pic / BinItem dataclasses"
```

---

### Task 2: Reader parses `$pic` GShapeObjectControl

**Files:**
- Modify: `hwp2hwpx/hwpmodel/reader.py`
- Test: `tests/test_reader_picture.py`

**Interfaces:**
- Consumes: `HwpPicture` (Task 1), existing `_int`, `_parse_shape_component`.
- Produces: `_parse_picture(comp_el) -> HwpPicture`; `_parse_drawing` now returns a `kind="pic"` `HwpDrawing` for `$pic` components (was `None`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reader_picture.py
from lxml import etree
from hwp2hwpx.hwpmodel.reader import _parse_drawing

PIC_GSO = '''
<GShapeObjectControl chid="gso " flow="block" halign="left" height="65913"
  hrelto="paragraph" inline="1" instance-id="1111203703" margin-left="0"
  margin-right="0" margin-top="0" margin-bottom="0" text-side="both"
  valign="top" vrelto="paragraph" width="46545" width-relto="absolute"
  x="0" y="0" z-order="15">
  <ShapeComponent chid="$pic" chid0="$pic" angle="0" flip="0" width="46545"
    height="65913" initial-width="36480" initial-height="51660">
    <Coord attribute-name="rotation_center" x="23272" y="32956"/>
    <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
    <ShapePicture instance-id="37461880" padding-left="0" padding-right="0"
      padding-top="0" padding-bottom="0" border-transparency="0">
      <ImageRect attribute-name="rect">
        <Coord attribute-name="p0" x="0" y="0"/>
        <Coord attribute-name="p1" x="36480" y="0"/>
        <Coord attribute-name="p2" x="36480" y="51660"/>
        <Coord attribute-name="p3" x="0" y="51660"/>
      </ImageRect>
      <ImageClip attribute-name="clip" left="0" right="36480" top="0" bottom="51660"/>
      <PictureInfo attribute-name="picture" bindata-id="1" brightness="0" contrast="0" effect="0"/>
    </ShapePicture>
  </ShapeComponent>
</GShapeObjectControl>'''


def test_parse_picture_drawing():
    d = _parse_drawing(etree.fromstring(PIC_GSO))
    assert d is not None and d.kind == "pic"
    assert d.instance_id == 1111203703 and d.z_order == 15
    assert d.component.initial_width == 36480
    p = d.picture
    assert p is not None
    assert p.instance_id == 37461880 and p.bindata_id == 1
    assert p.img_rect == [(0, 0), (36480, 0), (36480, 51660), (0, 51660)]
    assert p.img_clip == (0, 36480, 0, 51660)     # left,right,top,bottom
    assert p.brightness == 0 and p.effect == 0
    assert p.dim_width == 36480 and p.dim_height == 51660
    assert d.line is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_reader_picture.py -v`
Expected: FAIL (`_parse_drawing` returns `None` for `$pic`).

- [ ] **Step 3: Add `_parse_picture` and extend `_parse_drawing`**

In `hwp2hwpx/hwpmodel/reader.py`, add `HwpPicture` to the `.model` import. Add `_parse_picture` (place above `_parse_drawing`):

```python
def _parse_picture(comp_el):
    sp = comp_el.find("ShapePicture")
    if sp is None:
        return None
    rect = sp.find("ImageRect")
    pts = [(0, 0), (0, 0), (0, 0), (0, 0)]
    if rect is not None:
        for i in range(4):
            c = rect.find("Coord[@attribute-name='p%d']" % i)
            if c is not None:
                pts[i] = (_int(c.get("x")), _int(c.get("y")))
    clip = sp.find("ImageClip")
    img_clip = ((_int(clip.get("left")), _int(clip.get("right")),
                 _int(clip.get("top")), _int(clip.get("bottom")))
                if clip is not None else (0, 0, 0, 0))
    info = sp.find("PictureInfo")
    return HwpPicture(
        instance_id=_int(sp.get("instance-id")),
        bindata_id=_int(info.get("bindata-id")) if info is not None else 0,
        img_rect=pts,
        img_clip=img_clip,
        brightness=_int(info.get("brightness")) if info is not None else 0,
        contrast=_int(info.get("contrast")) if info is not None else 0,
        effect=_int(info.get("effect")) if info is not None else 0,
        dim_width=_int(comp_el.get("initial-width")),
        dim_height=_int(comp_el.get("initial-height")),
    )
```

Modify `_parse_drawing` so `$lin` and `$pic` both produce a drawing (keep the existing `$lin` path; the GSO-attribute block is shared, so restructure to build `common` once):

```python
def _parse_drawing(gso_el):
    """GShapeObjectControl -> HwpDrawing. Slice A+B: line ($lin) and picture
    ($pic); other kinds return None (skipped)."""
    comp = gso_el.find("ShapeComponent")
    if comp is None:
        return None
    chid0 = (comp.get("chid0") or comp.get("chid") or "").strip()
    if chid0 not in ("$lin", "$pic"):
        return None
    common = dict(
        instance_id=_int(gso_el.get("instance-id")),
        z_order=_int(gso_el.get("z-order")),
        flow=gso_el.get("flow") or "block",
        text_side=gso_el.get("text-side") or "both",
        x=_int(gso_el.get("x")),
        y=_int(gso_el.get("y")),
        width=_int(gso_el.get("width")),
        height=_int(gso_el.get("height")),
        hrelto=gso_el.get("hrelto") or "paper",
        vrelto=gso_el.get("vrelto") or "paper",
        halign=gso_el.get("halign") or "left",
        valign=gso_el.get("valign") or "top",
        inline=_int(gso_el.get("inline")),
        margin_left=_int(gso_el.get("margin-left")),
        margin_right=_int(gso_el.get("margin-right")),
        margin_top=_int(gso_el.get("margin-top")),
        margin_bottom=_int(gso_el.get("margin-bottom")),
        width_relto=gso_el.get("width-relto") or "absolute",
        height_relto=gso_el.get("height-relto") or "absolute",
        component=_parse_shape_component(comp),
    )
    if chid0 == "$lin":
        return HwpDrawing(kind="line", line=_parse_line_shape(comp), **common)
    return HwpDrawing(kind="pic", picture=_parse_picture(comp), **common)
```

(The existing `parse_paragraph` `GShapeObjectControl` branch already appends a run only when `_parse_drawing` is non-None, so pictures now get their own run automatically.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_reader_picture.py tests/test_reader_drawing.py -v`
Expected: PASS (test_reader_picture 1 + test_reader_drawing 3 — the `$lin` path still works).

- [ ] **Step 5: Run reader regression subset**

Run: `.venv/bin/python -m pytest tests/test_reader_body.py tests/test_reader_tables.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/reader.py tests/test_reader_picture.py
git commit -m "feat: reader parses GShapeObjectControl picture drawings"
```

---

### Task 3: Binary extraction (`extract_bin_items`) + convert wiring

**Files:**
- Create: `hwp2hwpx/hwpmodel/bindata.py`
- Modify: `hwp2hwpx/convert.py`
- Test: `tests/test_bindata.py`

**Interfaces:**
- Consumes: `HwpDocument`, `BinItem` (Task 1), reader's `_hwp5proc`.
- Produces: `extract_bin_items(hwp_path, hwp_doc) -> list[BinItem]`; `convert` sets `owpml_doc.bin_items`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bindata.py
import zipfile
from hwp2hwpx.hwpmodel.reader import hwp5_xml, read_document
from hwp2hwpx.hwpmodel.bindata import extract_bin_items

S4 = "samples/4.제안요청서_070.hwp"
S4_REF = "samples/4.제안요청서_070.hwpx"
S3 = "samples/3.과업지시서_070.hwp"


def _doc(hwp):
    return read_document(hwp5_xml(hwp))


def test_extract_three_byte_identical_images():
    items = extract_bin_items(S4, _doc(S4))
    assert len(items) == 3
    assert sorted(i.id for i in items) == ["image1", "image2", "image3"]
    assert all(i.media_type == "image/bmp" for i in items)
    assert all(i.filename.endswith(".bmp") for i in items)
    ref = zipfile.ZipFile(S4_REF)
    for it in items:
        want = ref.read("BinData/%s" % it.filename)
        assert it.data == want, "%s not byte-identical" % it.filename
        assert len(it.data) > 0


def test_no_pictures_no_bin_items():
    assert extract_bin_items(S3, _doc(S3)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_bindata.py -v`
Expected: FAIL (`ModuleNotFoundError: hwp2hwpx.hwpmodel.bindata`).

- [ ] **Step 3: Create `hwp2hwpx/hwpmodel/bindata.py`**

```python
"""Extract embedded image binaries from an HWP file for the HWPX package.

The image bytes live in the HWP OLE2 storage as BinData/BIN000N.<ext>.
`hwp5proc cat` returns them already decompressed (byte-identical to what
Hancom embeds), so no transcoding is needed here.
"""
import subprocess
from ..owpml.model import BinItem
from .reader import _hwp5proc

_MEDIA = {"bmp": "image/bmp", "png": "image/png", "jpg": "image/jpeg",
          "jpeg": "image/jpeg", "gif": "image/gif", "wmf": "image/x-wmf",
          "tiff": "image/tiff", "tif": "image/tiff"}


def _iter_all_paragraphs(paragraphs):
    for para in paragraphs:
        yield para
        for run in para.runs:
            tbl = getattr(run, "table", None)
            if tbl is not None:
                for row in tbl.table_rows:
                    for cell in row.cells:
                        for p in _iter_all_paragraphs(cell.paragraphs):
                            yield p


def _collect_pic_bindata_ids(hwp_doc):
    ids = []
    for sec in hwp_doc.sections:
        for para in _iter_all_paragraphs(sec.paragraphs):
            for run in para.runs:
                d = getattr(run, "drawing", None)
                if (d is not None and d.kind == "pic" and d.picture is not None
                        and d.picture.bindata_id not in ids):
                    ids.append(d.picture.bindata_id)
    return ids


def _list_bindata_streams(hwp_path):
    """{id_int: 'BinData/BIN000N.ext'} from `hwp5proc ls`."""
    out = subprocess.run([_hwp5proc(), "ls", hwp_path],
                         capture_output=True).stdout.decode(errors="replace")
    streams = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("BinData/BIN"):
            base = line.rsplit("/", 1)[-1]        # BIN0001.bmp
            num = base[3:].split(".", 1)[0]        # 0001
            try:
                streams[int(num)] = line
            except ValueError:
                pass
    return streams


def extract_bin_items(hwp_path, hwp_doc):
    ids = _collect_pic_bindata_ids(hwp_doc)
    if not ids:
        return []
    streams = _list_bindata_streams(hwp_path)
    items = []
    for bid in ids:
        stream = streams.get(bid)
        if stream is None:
            continue   # referenced stream missing: skip (pic still refs image{bid})
        ext = stream.rsplit(".", 1)[-1].lower() if "." in stream else "bin"
        data = subprocess.run([_hwp5proc(), "cat", hwp_path, stream],
                              capture_output=True).stdout
        items.append(BinItem(
            id="image%d" % bid,
            filename="image%d.%s" % (bid, ext),
            media_type=_MEDIA.get(ext, "application/octet-stream"),
            data=data,
        ))
    return items
```

- [ ] **Step 4: Wire into `convert`**

Modify `hwp2hwpx/convert.py` so `convert` extracts and attaches bin items:

```python
"""Top-level HWP -> HWPX conversion."""
import os
from .hwpmodel.reader import hwp5_xml, read_document
from .hwpmodel.bindata import extract_bin_items
from .mapper.body import map_document
from .owpml.writer import write_hwpx


def convert(hwp_path, out_path):
    xml = hwp5_xml(hwp_path)
    hwp_doc = read_document(xml)
    title = os.path.splitext(os.path.basename(hwp_path))[0]
    owpml_doc = map_document(hwp_doc, title=title)
    owpml_doc.bin_items = extract_bin_items(hwp_path, hwp_doc)
    write_hwpx(owpml_doc, out_path)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_bindata.py -v`
Expected: PASS (2 tests — three byte-identical images; sample 3 empty).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/bindata.py hwp2hwpx/convert.py tests/test_bindata.py
git commit -m "feat: extract embedded image binaries via hwp5proc cat"
```

---

### Task 4: Mapper — shared container helper + `map` picture

**Files:**
- Modify: `hwp2hwpx/mapper/drawing.py`
- Test: `tests/test_mapper_picture.py`

**Interfaces:**
- Consumes: `HwpDrawing(kind="pic")` (Task 1-2), OWPML `Pic` + children (Task 1).
- Produces: `map_drawing` returns a `Pic` for `kind="pic"`; the container mapping is factored into `_common_container` shared with lines.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mapper_picture.py
from hwp2hwpx.hwpmodel.model import HwpDrawing, HwpShapeComponent, HwpPicture
from hwp2hwpx.mapper.drawing import map_drawing


def _pic_drawing():
    return HwpDrawing(
        kind="pic", instance_id=1111203703, z_order=15, flow="block", inline=1,
        x=0, y=0, width=46545, height=65913, hrelto="paragraph", vrelto="paragraph",
        component=HwpShapeComponent(initial_width=36480, initial_height=51660,
                                    width=46545, height=65913, center_x=23272,
                                    center_y=32956,
                                    scaler_matrix=[1.2759, 0.0, 0.0, 1.2759, 0.0, 0.0]),
        picture=HwpPicture(instance_id=37461880, bindata_id=1,
                           img_rect=[(0, 0), (36480, 0), (36480, 51660), (0, 51660)],
                           img_clip=(0, 36480, 0, 51660), brightness=0, contrast=0,
                           effect=0, dim_width=36480, dim_height=51660),
    )


def test_map_pic_container_and_image():
    pic = map_drawing(_pic_drawing())
    assert pic.__class__.__name__ == "Pic"
    assert pic.id == 1111203703 and pic.z_order == 15 and pic.instid == 37461880
    assert pic.text_wrap == "TOP_AND_BOTTOM"
    assert pic.rotation_info.rotate_image == 1     # pictures: 1 (lines: 0)
    assert pic.org_sz.width == 36480 and pic.cur_sz.width == 46545
    assert pic.pos.horz_rel_to == "PARA" and pic.pos.treat_as_char == 1
    assert pic.img.bin_item_id == "image1" and pic.img.effect == "REAL_PIC"
    assert (pic.img_rect.pt2.x, pic.img_rect.pt2.y) == (36480, 51660)
    assert pic.img_clip.right == 36480 and pic.img_clip.bottom == 51660
    assert pic.img_dim.dim_width == 36480
    assert pic.shape_comment is not None


def test_line_still_maps_and_rotate_image_zero():
    from hwp2hwpx.hwpmodel.model import HwpLineShape
    ln = map_drawing(HwpDrawing(kind="line", component=HwpShapeComponent(),
                                line=HwpLineShape(p0=(0, 0), p1=(1, 1))))
    assert ln.__class__.__name__ == "Line"
    assert ln.rotation_info.rotate_image == 0


def test_none_and_unknown_kind():
    assert map_drawing(None) is None
    assert map_drawing(HwpDrawing(kind="rect", component=HwpShapeComponent())) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mapper_picture.py -v`
Expected: FAIL (`map_drawing` returns `None` for `kind="pic"`).

- [ ] **Step 3: Refactor `map_drawing` with a shared helper and add the pic path**

In `hwp2hwpx/mapper/drawing.py`, extend the imports to add `Pic, Img, ImgRect, ImgClip, InMargin, ImgDim, ShapeComment` (keep the existing `Line`/children imports). Add an effect map next to the others:

```python
_PIC_EFFECT = {0: "REAL_PIC", 1: "GRAY_SCALE", 2: "BLACK_WHITE"}
```

Replace `map_drawing` with a shared-container version (this refactors the existing line mapping — the line output must be identical to before):

```python
def _common_container(hd, comp, rotate_image):
    return dict(
        id=hd.instance_id,
        z_order=hd.z_order,
        text_wrap=_TEXT_WRAP.get(hd.flow, "TOP_AND_BOTTOM"),
        offset=Offset(0, 0),
        org_sz=OrgSz(comp.initial_width, comp.initial_height),
        cur_sz=CurSz(comp.width, comp.height),
        flip=Flip(comp.flip & 1, (comp.flip >> 1) & 1),
        rotation_info=RotationInfo(angle=comp.angle, center_x=comp.center_x,
                                   center_y=comp.center_y, rotate_image=rotate_image),
        rendering_info=RenderingInfo(trans=_matrix(comp.trans_matrix),
                                     sca=_matrix(comp.scaler_matrix),
                                     rot=_matrix(comp.rotator_matrix)),
        sz=ShapeSz(width=hd.width,
                   width_rel_to=_SZ_RELTO.get(hd.width_relto, "ABSOLUTE"),
                   height=hd.height,
                   height_rel_to=_SZ_RELTO.get(hd.height_relto, "ABSOLUTE")),
        pos=ShapePos(treat_as_char=hd.inline,
                     vert_rel_to=_POS_RELTO.get(hd.vrelto, "PAPER"),
                     horz_rel_to=_POS_RELTO.get(hd.hrelto, "PAPER"),
                     vert_align=_VALIGN.get(hd.valign, "TOP"),
                     horz_align=_HALIGN.get(hd.halign, "LEFT"),
                     vert_offset=hd.y, horz_offset=hd.x),
        out_margin=ShapeOutMargin(hd.margin_left, hd.margin_right,
                                  hd.margin_top, hd.margin_bottom),
    )


def _map_line(hd):
    comp, ls = hd.component, hd.line
    return Line(
        **_common_container(hd, comp, 0),
        line_shape=LineShape(
            color=ls.color, width=ls.width,
            style=_STROKE.get(ls.stroke, "SOLID"),
            end_cap=_LINE_END.get(ls.line_end, "FLAT"),
            head_style=_ARROW_STYLE.get(ls.arrow_start, "NORMAL"),
            tail_style=_ARROW_STYLE.get(ls.arrow_end, "NORMAL"),
            head_fill=ls.arrow_start_fill, tail_fill=ls.arrow_end_fill,
            head_sz=_ARROW_SIZE.get(ls.arrow_start_size, "SMALL_SMALL"),
            tail_sz=_ARROW_SIZE.get(ls.arrow_end_size, "SMALL_SMALL")),
        win_brush=WinBrush(), shadow=Shadow(),
        start_pt=Pt(ls.p0[0], ls.p0[1]), end_pt=Pt(ls.p1[0], ls.p1[1]),
    )


def _map_pic(hd):
    comp, pic = hd.component, hd.picture
    r = pic.img_rect
    return Pic(
        **_common_container(hd, comp, 1),
        instid=pic.instance_id,
        img=Img(bin_item_id="image%d" % pic.bindata_id, bright=pic.brightness,
                contrast=pic.contrast, effect=_PIC_EFFECT.get(pic.effect, "REAL_PIC")),
        img_rect=ImgRect(pt0=Pt(*r[0]), pt1=Pt(*r[1]), pt2=Pt(*r[2]), pt3=Pt(*r[3])),
        img_clip=ImgClip(left=pic.img_clip[0], right=pic.img_clip[1],
                         top=pic.img_clip[2], bottom=pic.img_clip[3]),
        in_margin=InMargin(),
        img_dim=ImgDim(pic.dim_width, pic.dim_height),
        shape_comment=ShapeComment(text="그림"),   # Hancom alt-text not stored in HWP
    )


def map_drawing(hd):
    if hd is None or hd.component is None:
        return None
    if hd.kind == "line" and hd.line is not None:
        return _map_line(hd)
    if hd.kind == "pic" and hd.picture is not None:
        return _map_pic(hd)
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_mapper_picture.py tests/test_mapper_drawing.py -v`
Expected: PASS (picture tests + all existing line mapper tests, proving the refactor kept line output identical).

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/drawing.py tests/test_mapper_picture.py
git commit -m "feat: map HWP picture to OWPML Pic (shared container helper)"
```

---

### Task 5: Writer — `_write_pic`, dispatch, `content.hpf` + BinData ZIP entries

**Files:**
- Modify: `hwp2hwpx/owpml/section_writer.py`, `hwp2hwpx/owpml/package_parts.py`, `hwp2hwpx/owpml/writer.py`
- Test: `tests/test_section_writer_pic.py`, `tests/test_package_bindata.py`

**Interfaces:**
- Consumes: OWPML `Pic` + children, `BinItem`, `OwpmlDocument.bin_items`.
- Produces: `_write_pic`; `_write_run` dispatches `Pic`→`_write_pic` else `_write_line`; `content_hpf(metadata, section_count, bin_items=())`; `write_hwpx` writes `BinData/{filename}` entries.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_section_writer_pic.py
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import (
    Section, Para, Run, Pic, Line, Offset, OrgSz, CurSz, Flip, RotationInfo,
    Matrix, RenderingInfo, Img, ImgRect, ImgClip, InMargin, ImgDim, ShapeComment,
    ShapeSz, ShapePos, ShapeOutMargin, Pt, LineShape, WinBrush, Shadow,
)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HC = "http://www.hancom.co.kr/hwpml/2011/core"


def _qp(t):
    return "{%s}%s" % (HP, t)


def _qc(t):
    return "{%s}%s" % (HC, t)


def _pic():
    return Pic(
        id=111, z_order=15, instid=37461880,
        offset=Offset(0, 0), org_sz=OrgSz(36480, 51660), cur_sz=CurSz(46545, 65913),
        flip=Flip(0, 0), rotation_info=RotationInfo(0, 23272, 32956, 1),
        rendering_info=RenderingInfo(trans=Matrix(), sca=Matrix(), rot=Matrix()),
        img=Img(bin_item_id="image1"),
        img_rect=ImgRect(pt0=Pt(0, 0), pt1=Pt(36480, 0), pt2=Pt(36480, 51660), pt3=Pt(0, 51660)),
        img_clip=ImgClip(0, 36480, 0, 51660), in_margin=InMargin(),
        img_dim=ImgDim(36480, 51660),
        sz=ShapeSz(width=46545, height=65913), pos=ShapePos(treat_as_char=1),
        out_margin=ShapeOutMargin(), shape_comment=ShapeComment(text="그림"),
    )


def _root(section):
    return etree.fromstring(section_xml(section).split(b"?>", 1)[1])


def test_pic_child_order_and_namespaces():
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, drawing=_pic())])])
    pic = _root(sec).find(".//" + _qp("pic"))
    assert pic is not None and pic.get("id") == "111" and pic.get("reverse") == "0"
    kids = [etree.QName(c).localname for c in pic]
    assert kids == ["offset", "orgSz", "curSz", "flip", "rotationInfo",
                    "renderingInfo", "img", "imgRect", "imgClip", "inMargin",
                    "imgDim", "effects", "sz", "pos", "outMargin", "shapeComment"]
    assert pic.find(_qc("img")).get("binaryItemIDRef") == "image1"
    ir = pic.find(_qp("imgRect"))
    assert ir.find(_qc("pt2")).get("x") == "36480"
    assert pic.find(_qp("imgClip")).get("right") == "36480"
    assert pic.find(_qp("imgDim")).get("dimwidth") == "36480"
    assert pic.find(_qp("effects")) is not None
    assert pic.find(_qp("shapeComment")).text == "그림"


def test_line_still_emitted_via_dispatch():
    ln = Line(id=9, offset=Offset(0, 0), org_sz=OrgSz(), cur_sz=CurSz(), flip=Flip(),
              rotation_info=RotationInfo(), rendering_info=RenderingInfo(
                  trans=Matrix(), sca=Matrix(), rot=Matrix()),
              line_shape=LineShape(), win_brush=WinBrush(), shadow=Shadow(),
              start_pt=Pt(0, 0), end_pt=Pt(1, 1), sz=ShapeSz(), pos=ShapePos(),
              out_margin=ShapeOutMargin())
    sec = Section(paras=[Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, drawing=ln)])])
    root = _root(sec)
    assert root.find(".//" + _qp("line")) is not None
    assert root.find(".//" + _qp("pic")) is None
```

```python
# tests/test_package_bindata.py
import zipfile
from hwp2hwpx.owpml.writer import write_hwpx
from hwp2hwpx.owpml.package_parts import content_hpf
from hwp2hwpx.owpml.model import (
    OwpmlDocument, Header, Metadata, Section, BinItem,
)


def test_content_hpf_declares_images():
    hpf = content_hpf(Metadata(title="t"), 1, [
        BinItem(id="image1", filename="image1.bmp", media_type="image/bmp", data=b"BM"),
    ]).decode("utf-8")
    assert '<opf:item id="image1" href="BinData/image1.bmp" media-type="image/bmp" isEmbeded="1"/>' in hpf


def test_content_hpf_no_images_when_empty():
    hpf = content_hpf(Metadata(title="t"), 1).decode("utf-8")
    assert "BinData/" not in hpf


def test_write_hwpx_embeds_bindata(tmp_path):
    doc = OwpmlDocument(
        header=Header(), sections=[Section(paras=[])], metadata=Metadata(title="t"),
        bin_items=[BinItem(id="image1", filename="image1.bmp",
                           media_type="image/bmp", data=b"BMdata")])
    out = tmp_path / "o.hwpx"
    write_hwpx(doc, str(out))
    with zipfile.ZipFile(str(out)) as z:
        assert z.read("BinData/image1.bmp") == b"BMdata"
        assert "image1" in z.read("Contents/content.hpf").decode("utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_section_writer_pic.py tests/test_package_bindata.py -v`
Expected: FAIL (no `_write_pic`; `content_hpf` has no `bin_items` param; no BinData entries).

- [ ] **Step 3: Add `_write_pic` and the dispatch**

In `hwp2hwpx/owpml/section_writer.py`, extend the model import to include `Pic` (and `Line` if not already), e.g. `from ..owpml.model import Control, Pic`. Add `_write_pic` (near `_write_line`):

```python
def _write_pic(run_el, p):
    e = etree.SubElement(run_el, _hp("pic"))
    for k, v in (("id", str(p.id)), ("zOrder", str(p.z_order)),
                 ("numberingType", "PICTURE"), ("textWrap", p.text_wrap),
                 ("textFlow", p.text_flow), ("lock", "0"),
                 ("dropcapstyle", "None"), ("href", ""), ("groupLevel", "0"),
                 ("instid", str(p.instid)), ("reverse", str(p.reverse))):
        e.set(k, v)
    off = etree.SubElement(e, _hp("offset"))
    off.set("x", str(p.offset.x)); off.set("y", str(p.offset.y))
    osz = etree.SubElement(e, _hp("orgSz"))
    osz.set("width", str(p.org_sz.width)); osz.set("height", str(p.org_sz.height))
    csz = etree.SubElement(e, _hp("curSz"))
    csz.set("width", str(p.cur_sz.width)); csz.set("height", str(p.cur_sz.height))
    fl = etree.SubElement(e, _hp("flip"))
    fl.set("horizontal", str(p.flip.horizontal)); fl.set("vertical", str(p.flip.vertical))
    ri = p.rotation_info
    r = etree.SubElement(e, _hp("rotationInfo"))
    r.set("angle", str(ri.angle)); r.set("centerX", str(ri.center_x))
    r.set("centerY", str(ri.center_y)); r.set("rotateimage", str(ri.rotate_image))
    rend = etree.SubElement(e, _hp("renderingInfo"))
    for tag, m in (("transMatrix", p.rendering_info.trans),
                   ("scaMatrix", p.rendering_info.sca),
                   ("rotMatrix", p.rendering_info.rot)):
        me = etree.SubElement(rend, _hc(tag))
        for i in range(1, 7):
            me.set("e%d" % i, getattr(m, "e%d" % i))
    im = etree.SubElement(e, _hc("img"))
    im.set("binaryItemIDRef", p.img.bin_item_id); im.set("bright", str(p.img.bright))
    im.set("contrast", str(p.img.contrast)); im.set("effect", p.img.effect)
    im.set("alpha", str(p.img.alpha))
    irc = etree.SubElement(e, _hp("imgRect"))
    for name, pt in (("pt0", p.img_rect.pt0), ("pt1", p.img_rect.pt1),
                     ("pt2", p.img_rect.pt2), ("pt3", p.img_rect.pt3)):
        pe = etree.SubElement(irc, _hc(name))
        pe.set("x", str(pt.x)); pe.set("y", str(pt.y))
    ic = etree.SubElement(e, _hp("imgClip"))
    ic.set("left", str(p.img_clip.left)); ic.set("right", str(p.img_clip.right))
    ic.set("top", str(p.img_clip.top)); ic.set("bottom", str(p.img_clip.bottom))
    inm = etree.SubElement(e, _hp("inMargin"))
    for side in ("left", "right", "top", "bottom"):
        inm.set(side, str(getattr(p.in_margin, side)))
    idim = etree.SubElement(e, _hp("imgDim"))
    idim.set("dimwidth", str(p.img_dim.dim_width))
    idim.set("dimheight", str(p.img_dim.dim_height))
    etree.SubElement(e, _hp("effects"))
    sz = etree.SubElement(e, _hp("sz"))
    sz.set("width", str(p.sz.width)); sz.set("widthRelTo", p.sz.width_rel_to)
    sz.set("height", str(p.sz.height)); sz.set("heightRelTo", p.sz.height_rel_to)
    sz.set("protect", str(p.sz.protect))
    po = p.pos
    pe = etree.SubElement(e, _hp("pos"))
    for k, v in (("treatAsChar", str(po.treat_as_char)),
                 ("affectLSpacing", str(po.affect_lspacing)),
                 ("flowWithText", str(po.flow_with_text)),
                 ("allowOverlap", str(po.allow_overlap)),
                 ("holdAnchorAndSO", str(po.hold_anchor_and_so)),
                 ("vertRelTo", po.vert_rel_to), ("horzRelTo", po.horz_rel_to),
                 ("vertAlign", po.vert_align), ("horzAlign", po.horz_align),
                 ("vertOffset", str(po.vert_offset)), ("horzOffset", str(po.horz_offset))):
        pe.set(k, v)
    om = etree.SubElement(e, _hp("outMargin"))
    for side in ("left", "right", "top", "bottom"):
        om.set(side, str(getattr(p.out_margin, side)))
    sc = etree.SubElement(e, _hp("shapeComment"))
    sc.text = p.shape_comment.text if p.shape_comment is not None else ""
```

In `_write_run`, replace the drawing branch to dispatch by type:

```python
    if getattr(run, "drawing", None) is not None:
        if isinstance(run.drawing, Pic):
            _write_pic(r, run.drawing)
        else:
            _write_line(r, run.drawing)
```

- [ ] **Step 4: Extend `content_hpf` and `write_hwpx`**

In `hwp2hwpx/owpml/package_parts.py`, change `content_hpf` to accept `bin_items` and append image `opf:item`s (place them after the `settings` item, before building `body`):

```python
def content_hpf(metadata, section_count, bin_items=()):
    title = _esc(metadata.title)
    lang = _esc(metadata.language)
    items = [
        '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
    ]
    itemrefs = ['<opf:itemref idref="header" linear="yes"/>']
    for i in range(section_count):
        items.append(
            '<opf:item id="section%d" href="Contents/section%d.xml"'
            ' media-type="application/xml"/>' % (i, i)
        )
        itemrefs.append('<opf:itemref idref="section%d" linear="yes"/>' % i)
    items.append('<opf:item id="settings" href="settings.xml" media-type="application/xml"/>')
    for it in bin_items:
        items.append('<opf:item id="%s" href="BinData/%s" media-type="%s" isEmbeded="1"/>'
                     % (_esc(it.id), _esc(it.filename), _esc(it.media_type)))
    body = (
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/"'
        ' xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/" version="" unique-identifier="" id="">'
        '<opf:metadata>'
        '<opf:title>%s</opf:title>'
        '<opf:language>%s</opf:language>'
        '</opf:metadata>'
        '<opf:manifest>%s</opf:manifest>'
        '<opf:spine>%s</opf:spine>'
        '</opf:package>'
    ) % (title, lang, "".join(items), "".join(itemrefs))
    return _doc(body.encode("utf-8"))
```

In `hwp2hwpx/owpml/writer.py`, pass `bin_items` to `content_hpf` and add `BinData/` ZIP entries in `write_hwpx`:

```python
        "Contents/content.hpf": package_parts.content_hpf(
            doc.metadata, len(doc.sections), getattr(doc, "bin_items", [])),
```

and after the section loop, before `write_package(parts, out_path)`:

```python
    for item in getattr(doc, "bin_items", []):
        parts["BinData/%s" % item.filename] = item.data
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_section_writer_pic.py tests/test_package_bindata.py -v`
Expected: PASS (2 + 3).

- [ ] **Step 6: Run writer/package regression subset**

Run: `.venv/bin/python -m pytest tests/test_section_writer.py tests/test_section_writer_line.py tests/test_writer_endtoend.py -v`
Expected: PASS (line dispatch + existing packaging unaffected).

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py hwp2hwpx/owpml/package_parts.py hwp2hwpx/owpml/writer.py tests/test_section_writer_pic.py tests/test_package_bindata.py
git commit -m "feat: writer emits hp:pic + embeds BinData and declares images in content.hpf"
```

---

### Task 6: End-to-end — sample 4 pictures + sample 3 no-change

**Files:**
- Test: `tests/test_convert_picture.py`

**Interfaces:**
- Consumes: the whole pipeline via `hwp2hwpx.convert.convert`.

- [ ] **Step 1: Write the test**

```python
# tests/test_convert_picture.py
import zipfile
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import score_part
from hwp2hwpx.fidelity.xmlnorm import unzip_parts

S4 = "samples/4.제안요청서_070.hwp"
S4_REF = "samples/4.제안요청서_070.hwpx"
S3 = "samples/3.과업지시서_070.hwp"


def _convert(hwp, tmp_path, name):
    out = tmp_path / name
    convert(hwp, str(out))
    return zipfile.ZipFile(str(out))


def test_sample4_three_pics(tmp_path):
    z = _convert(S4, tmp_path, "s4.hwpx")
    sec = z.read("Contents/section0.xml").decode("utf-8")
    assert sec.count("<hp:pic ") == 3


def test_sample4_images_byte_identical_and_declared(tmp_path):
    z = _convert(S4, tmp_path, "s4.hwpx")
    ref = zipfile.ZipFile(S4_REF)
    names = [n for n in z.namelist() if n.startswith("BinData/")]
    assert len(names) == 3
    for n in names:
        assert z.read(n) == ref.read(n), "%s not byte-identical" % n
    hpf = z.read("Contents/content.hpf").decode("utf-8")
    for i in (1, 2, 3):
        assert 'href="BinData/image%d.bmp"' % i in hpf
        assert 'id="image%d"' % i in hpf


def test_sample4_pic_tags_leave_miss_list(tmp_path):
    out = tmp_path / "s4b.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    missing = score_part(ours, theirs)["missing"]
    for tag in ("pic", "img", "imgRect", "imgClip", "imgDim", "shapeComment"):
        assert missing.get(tag, 0) == 0, "%s still missing x%d" % (tag, missing.get(tag, 0))


def test_sample4_section0_match_rose(tmp_path):
    out = tmp_path / "s4c.hwpx"
    convert(S4, str(out))
    ours = unzip_parts(str(out))["Contents/section0.xml"]
    theirs = unzip_parts(S4_REF)["Contents/section0.xml"]
    # baseline after Slice A (lines) was 0.9824; pictures lift it further
    assert score_part(ours, theirs)["match"] > 0.99


def test_sample3_unchanged_no_pic_no_bindata(tmp_path):
    z = _convert(S3, tmp_path, "s3.hwpx")
    sec = z.read("Contents/section0.xml").decode("utf-8")
    assert sec.count("<hp:pic ") == 0
    assert [n for n in z.namelist() if n.startswith("BinData/")] == []
    assert "BinData/" not in z.read("Contents/content.hpf").decode("utf-8")
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_convert_picture.py -v`
Expected: PASS (5 tests). If `test_sample4_three_pics` != 3, diagnose whether a picture's `ShapeComponent` uses a `chid0` other than `$pic`; do NOT relax the count. If `test_sample4_section0_match_rose` fails, report the actual value (the controller decides the threshold, as done for prior milestones). If sample 3 shows any `BinData/` or `hp:pic`, that's a regression — report it.

- [ ] **Step 3: Confirm sample 3 image-free package is unchanged**

Run:
```bash
.venv/bin/python -c "
import zipfile, tempfile, os
from hwp2hwpx.convert import convert
out = tempfile.mktemp(suffix='.hwpx')
convert('samples/3.과업지시서_070.hwp', out)
z = zipfile.ZipFile(out)
bd = [n for n in z.namelist() if n.startswith('BinData/')]
hpf = z.read('Contents/content.hpf').decode()
os.unlink(out)
print('BinData entries:', bd, '| image in hpf:', 'BinData/' in hpf)
print('CLEAN' if not bd and 'BinData/' not in hpf else 'LEAK')
"
```
Expected: `CLEAN`.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add tests/test_convert_picture.py
git commit -m "test: end-to-end hp:pic + byte-identical images on sample 4"
```

---

## Self-Review

**Spec coverage:** Reader `$pic` parsing (Task 2); models both sides + BinItem (Task 1); binary extraction via `hwp5proc cat` + convert wiring (Task 3); mapper shared container + pic (Task 4); writer `_write_pic` + dispatch + `content.hpf` + BinData ZIP entries (Task 5); e2e count + byte-identical + content.hpf + sample-3 no-change (Task 6). Gate is count-based for the subtree plus the two exact checks (byte-identical images, content.hpf declaration).

**Placeholder scan:** No TBD/TODO; complete code in every step; expected output on every run step.

**Type consistency:** `HwpPicture` fields (`bindata_id`, `img_rect`, `img_clip`, `dim_width`) used identically by reader (Task 2), mapper (Task 4), and bindata (Task 3). OWPML `Pic`/`Img`/`ImgRect`/`ImgClip`/`InMargin`/`ImgDim`/`ShapeComment`/`BinItem` field names used identically by mapper (Task 4) and writer (Task 5). `_common_container` returns a dict spread into both `Line` and `Pic` — shared keys match both dataclasses' field names (`id`, `z_order`, `text_wrap`, `offset`, `org_sz`, `cur_sz`, `flip`, `rotation_info`, `rendering_info`, `sz`, `pos`, `out_margin`); `rotate_image` param differs (line 0, pic 1). `bin_item_id="image%d" % bindata_id` (mapper) matches `id="image%d" % bid` (bindata) matches `href="BinData/image%d.ext"` (content.hpf). `Run.drawing` polymorphic (`Line`|`Pic`); writer dispatches via `isinstance(run.drawing, Pic)`.
