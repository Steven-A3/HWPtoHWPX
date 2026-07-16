# HWP → HWPX Converter — Drawing Objects (Slice B: pictures + binary BinData) Design

**Date:** 2026-07-16
**Status:** Approved (pending spec review)
**Builds on:** milestones 1..11 (through drawing Slice A / lines), all merged to `main`.

## Goal

Emit `<hp:pic>` (one per HWP picture drawing) with its embedded image. On sample 4:
`hp:pic` == 3, each referencing a `BinData/imageN.bmp` that is **byte-identical** to
Hancom's, declared in `content.hpf`. Sample 3 (no drawings) unchanged — no `BinData/`
entries, no image `opf:item`s.

The GSO **common container** (offset/orgSz/curSz/flip/rotationInfo/renderingInfo/
sz/pos/outMargin) is identical to Slice A (lines) and is reused. Only the middle
subtree (`img`/`imgRect`/`imgClip`/`inMargin`/`imgDim`/`effects`/`shapeComment`) and
the **binary plumbing** are new.

**Success** = `hp:pic` == 3 on sample 4; each `BinData/imageN.bmp` byte-identical to
Hancom's; `content.hpf` declares all three images; the pic subtree tags leave/shrink
in the section0 miss list; sample 4 section0 match rises; sample 3 output unchanged
(no `BinData/`, no image `opf:item`); output opens in Hancom Office.

## Correctness gate

Mostly count-based (pic geometry is computed/recomputed by Hancom, like lines) **plus
two verifiable EXACT checks**:
1. **Byte-identical images** — `hwp5proc cat <hwp> BinData/BIN000N.bmp` returns bytes
   identical to Hancom's `BinData/imageN.bmp` (verified: 1005994 == 1005994 on image 1).
   Asserted exactly.
2. **`content.hpf` declares each image** — `<opf:item id="imageN"
   href="BinData/imageN.bmp" media-type="image/bmp" isEmbeded="1"/>`. Asserted.

Everything else (`hp:pic`==3, `img`/`imgRect`/`pt0-3`/`imgClip`/`imgDim`/`effects`/
`shapeComment`/`inMargin` present) is count-based; unstored/computed values
(`shapeComment` text, matrix formatting, `instid`) get documented defaults.

## Verified ground truth (sample 4)

3 pictures, each a `GShapeObjectControl`/`ShapeComponent` with `chid0="$pic"`. The
image bytes live in the HWP OLE2 storage as `BinData/BIN0001.bmp`..`BIN0003.bmp`
(listed by `hwp5proc ls`). `PictureInfo bindata-id="N"` links the picture to
`BIN000N`. `manifest.xml` is empty (no image entries); only `content.hpf` declares them.

### HWP source (one picture, verified)

```
<ShapeComponent chid="$pic" chid0="$pic" angle="0" flip="0" width="46545"
  height="65913" initial-width="36480" initial-height="51660" ...>
  <Coord attribute-name="rotation_center" x="23272" y="32956"/>
  <Matrix attribute-name="translation" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
  <Array name="scalerotations"><ScaleRotationMatrix>
    <Matrix attribute-name="scaler" a="1.2759..." b="0.0" c="0.0" d="1.2759..." e="0.0" f="0.0"/>
    <Matrix attribute-name="rotator" a="1.0" b="0.0" c="0.0" d="1.0" e="0.0" f="0.0"/>
  </ScaleRotationMatrix></Array>
  <ShapePicture instance-id="37461880" padding-left="0" padding-right="0"
    padding-top="0" padding-bottom="0" border-transparency="0">
    <BorderLine .../>
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
```

### Target OWPML (the same picture, verified — full child order)

```
<hp:pic id="1111203703" zOrder="15" numberingType="PICTURE"
  textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None"
  href="" groupLevel="0" instid="37461880" reverse="0">
  <hp:offset x="0" y="0"/>
  <hp:orgSz width="36480" height="51660"/>
  <hp:curSz width="46545" height="65913"/>
  <hp:flip horizontal="0" vertical="0"/>
  <hp:rotationInfo angle="0" centerX="23272" centerY="32956" rotateimage="1"/>
  <hp:renderingInfo>
    <hc:transMatrix .../><hc:scaMatrix .../><hc:rotMatrix .../>
  </hp:renderingInfo>
  <hc:img binaryItemIDRef="image1" bright="0" contrast="0" effect="REAL_PIC" alpha="0"/>
  <hp:imgRect>
    <hc:pt0 x="0" y="0"/><hc:pt1 x="36480" y="0"/>
    <hc:pt2 x="36480" y="51660"/><hc:pt3 x="0" y="51660"/>
  </hp:imgRect>
  <hp:imgClip left="0" right="36480" top="0" bottom="51660"/>
  <hp:inMargin left="0" right="0" top="0" bottom="0"/>
  <hp:imgDim dimwidth="36480" dimheight="51660"/>
  <hp:effects/>
  <hp:sz width="46545" widthRelTo="ABSOLUTE" height="65913" heightRelTo="ABSOLUTE" protect="0"/>
  <hp:pos treatAsChar="1" ... vertRelTo="PARA" horzRelTo="PARA" .../>
  <hp:outMargin left="0" right="0" top="0" bottom="0"/>
  <hp:shapeComment>그림입니다. ...</hp:shapeComment>
</hp:pic>
```

Namespaces: `hc:` for `transMatrix`/`scaMatrix`/`rotMatrix`/`img`/`pt0..pt3`; `hp:` for
the rest. (`img` and the `pt` points are `hc:`.)

### Attribute mapping

**`hp:pic` element** (from `GShapeObjectControl` + `ShapePicture`): `id` ← GSO
instance-id; `zOrder` ← z-order; `numberingType="PICTURE"`; `textWrap` ← flow;
`textFlow="BOTH_SIDES"`; `lock`/`dropcapstyle`/`href`/`groupLevel` const;
`instid` ← ShapePicture instance-id; `reverse="0"` (const — note: **`reverse`**, not
the line's `isReverseHV`).

**Container** (offset/orgSz/curSz/flip/rotationInfo/renderingInfo/sz/pos/outMargin):
identical mapping to Slice A, except **`rotationInfo rotateimage="1"`** for pictures
(lines use `0`).

**`hc:img`** (from `PictureInfo`): `binaryItemIDRef="image{bindata-id}"`;
`bright` ← brightness; `contrast` ← contrast; `effect` ← effect (`0`→`"REAL_PIC"`,
default `"REAL_PIC"`); `alpha="0"` (const).

**`hp:imgRect`** › `hc:pt0..pt3` (from `ImageRect` Coord p0..p3): x,y.
**`hp:imgClip`** (from `ImageClip`): left/right/top/bottom.
**`hp:inMargin`** (from `ShapePicture` padding-*): left/right/top/bottom (0 in samples).
**`hp:imgDim`** : `dimwidth`/`dimheight` ← ShapeComponent initial-width/initial-height.
**`hp:effects`** : empty element (const).
**`hp:shapeComment`** : text — Hancom auto-generates Korean alt-text NOT stored in the
HWP; emit a minimal placeholder/derived text (count-based; presence is what scores).

### Binary pipeline (verified)

- `hwp5proc cat <hwp> BinData/BIN000N.bmp` → bytes **byte-identical** to Hancom's
  `BinData/imageN.bmp` (no decompression on our side).
- Stream names from `hwp5proc ls` → `BinData/BIN0001.bmp`..; extension → media-type
  (`.bmp`→`image/bmp`, `.png`→`image/png`, `.jpg`/`.jpeg`→`image/jpeg`, `.gif`→
  `image/gif`, `.wmf`→`image/x-wmf`, default `application/octet-stream`).
- Output package: `BinData/imageN.<ext>` ZIP entry + `content.hpf`
  `<opf:item id="imageN" href="BinData/imageN.<ext>" media-type="..." isEmbeded="1"/>`.

## Architecture (extends Slice A + a new binary path)

**Model (`hwpmodel/model.py`):** `HwpPicture(instance_id, bindata_id, img_rect: list,
img_clip: tuple, brightness, contrast, effect, dim_width, dim_height)`; `HwpDrawing`
gains `picture: "HwpPicture" = None` (alongside `line`). `img_rect` is a list of four
`(x,y)` tuples; `img_clip` is `(left, right, top, bottom)`.

**OWPML model (`owpml/model.py`):** a `Pic` dataclass (container fields identical to
`Line` + `Img`/`ImgRect`/`ImgClip`/`InMargin`/`ImgDim`/`Effects`/`ShapeComment`);
reuses `Pt`, `Offset`, `OrgSz`, `CurSz`, `Flip`, `RotationInfo`, `Matrix`,
`RenderingInfo`, `ShapeSz`, `ShapePos`, `ShapeOutMargin`. `BinItem(id, filename,
media_type, data: bytes)`. `OwpmlDocument` gains `bin_items: list`.
`Run.drawing` now holds a `Line` **or** a `Pic`.

**Reader (`hwpmodel/reader.py`):** `_parse_drawing` handles `chid0="$pic"` (Slice A
returned `None`): parse `ShapePicture`/`PictureInfo`/`ImageRect`/`ImageClip` into
`HwpPicture`, set `HwpDrawing(kind="pic", ...)` with the same container fields as lines.

**Orchestration (`convert.py`, or a new `hwpmodel/bindata.py`):**
`extract_bin_items(hwp_path, hwp_doc) -> list[BinItem]` — walk the doc for
`kind="pic"` drawings, collect distinct `bindata_id`s, list `BinData` streams via
`hwp5proc ls`, extract each referenced stream via `hwp5proc cat`, build a `BinItem`
per id (`id="image{n}"`, `filename="image{n}.{ext}"`, media-type from ext). `convert`
attaches the list to the `OwpmlDocument`.

**Mapper (`mapper/drawing.py`):** `map_drawing` returns a `Pic` for `kind="pic"`
(container mapping shared with lines via a helper; `rotate_image=1`;
`bin_item_id="image{bindata_id}"`).

**Writer (`owpml/section_writer.py`, `owpml/writer.py`, `owpml/package_parts.py`):**
`_write_pic`; `_write_run` dispatches by type — `isinstance(drawing, Pic)` →
`_write_pic`, else `_write_line`. `write_hwpx` adds a `BinData/{filename}` ZIP entry
per `bin_item`. `content_hpf(metadata, section_count, bin_items)` appends the image
`opf:item`s.

## Error handling / regression safety

- Sample 3 has no `$pic` GSO → no `HwpPicture`, no `bin_items` → no `BinData/` entries,
  no image `opf:item`s, `content.hpf` unchanged. Asserted.
- A missing/unreadable `BinData` stream → the `BinItem` is skipped with the `hp:pic`
  still emitted referencing it (schema-valid ref; degraded but non-crashing) — logged.
  Does not occur in samples.
- Missing `ImageRect`/`ImageClip`/`PictureInfo` → schema-valid defaults (0 points/clip,
  `bindata_id=0` → `binaryItemIDRef="image0"`); never crash.
- `Run.drawing` type dispatch: only `Line`/`Pic`; anything else emits nothing.

## Testing strategy (TDD)

- **Reader:** a `$pic` `GShapeObjectControl` (synthetic snippet) parses to
  `HwpDrawing(kind="pic")` with expected `bindata_id`, img_rect points, clip,
  brightness; sample 4 has 3 picture drawings.
- **Bindata:** `extract_bin_items` on sample 4 returns 3 `BinItem`s
  (`image1`/`image2`/`image3`, `image/bmp`), and each `data` is byte-identical to the
  corresponding `BinData/imageN.bmp` in Hancom's hwpx.
- **Mapper:** `map_drawing` maps a `$pic` `HwpDrawing` to a `Pic` with
  `bin_item_id="image1"`, `rotate_image=1`, `effect="REAL_PIC"`, imgRect/clip/dim set.
- **Writer:** `_write_pic` emits `hp:pic` with the exact child order and namespaces
  (`hc:img`, `hc:pt0..pt3`, `hp:imgRect/imgClip/imgDim/effects/shapeComment`);
  `content_hpf` with bin_items emits the three `opf:item`s; `write_hwpx` writes three
  `BinData/imageN.bmp` ZIP entries.
- **End-to-end:** sample 4 → `hp:pic`==3; three `BinData/imageN.bmp` entries each
  byte-identical to Hancom's; `content.hpf` declares all three; pic subtree tags gone
  from the miss list; section0 match rises. Sample 3 → no `BinData/`, no image
  `opf:item`, `hp:pic`==0. Full regression suite green.

## Non-goals (Slice B)

- Rectangles/ellipses/arcs/polygons/curves/text boxes/grouped shapes/OLE (not in
  samples).
- Reproducing Hancom's exact auto-generated `shapeComment` alt-text (not derivable).
- Image transcoding/format conversion (bytes pass through byte-identical).
- `manifest.xml` image entries (Hancom leaves it empty).

## Key risks

- **Binary orchestration threads the `.hwp` path** to a stage that previously saw only
  XML — mitigated by isolating extraction in `extract_bin_items(hwp_path, hwp_doc)`
  called from `convert`, keeping reader/mapper pure.
- **`content.hpf` change** must not break existing single-section packaging —
  mitigated by making `bin_items` default empty (no image items when none) and a
  sample-3 unchanged assertion.
- **Stream-name↔bindata-id mapping** (`BIN000N` ↔ id N) — mitigated by the
  byte-identical end-to-end assertion, which fails loudly if the wrong stream is picked.
- **`Run.drawing` now polymorphic** (`Line`|`Pic`) — mitigated by `isinstance` dispatch
  in `_write_run` and a writer test for each type.
- **Single-sample validation** (only sample 4 has pictures) — mitigated by synthetic
  unit tests for reader/mapper/writer and the byte-identical binary check.
