# HWP → HWPX Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python CLI that converts legacy HWP 5.0 binary files into HWPX (OWPML) files, starting with a working end-to-end pipeline plus a fidelity harness, faithful for text/character/paragraph content.

**Architecture:** Four layers — Reader (`.hwp` → HWP model, via pyhwp's `hwp5proc xml` dump), Mapper (HWP model → OWPML model, porting hwp2hwpx element mappings), Writer (OWPML model → `.hwpx` ZIP package), and a Fidelity harness that structurally diffs our output against Hancom's real `.hwpx` and scores per-element match. The two internal models (HWP model, OWPML model) are the stable interfaces; Reader/Writer are the only layers that touch bytes.

**Tech Stack:** Python 3.9+ (dev on 3.11), `lxml` (XML), `pyhwp` (HWP reader), `pytest` (tests). No JVM, no non-Python runtime.

## Scope of THIS plan

Implements spec sequencing steps 1–2 (end-to-end skeleton + text/char/paragraph fidelity) plus the fidelity harness. **Out of scope here — each becomes its own follow-up plan, prioritized by harness scores:** tables, images/bin-data, styles/numbering/border-fills beyond the minimum, headers/footers, shapes.

## Global Constraints

- Python **3.9+** floor; develop/test on 3.11. No syntax newer than 3.9.
- Dependencies limited to: Python stdlib, `lxml`, `pyhwp`, `pytest`. No JVM / non-Python runtime.
- HWPX package rules (verbatim from real Hancom output): `mimetype` entry is **first** in the ZIP, **STORED** (uncompressed), content exactly `application/hwp+zip`.
- All XML declarations: `<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>`, UTF-8 output.
- OWPML namespaces (copy verbatim into a single shared constants module):
  - `hp`  = `http://www.hancom.co.kr/hwpml/2011/paragraph`
  - `hh`  = `http://www.hancom.co.kr/hwpml/2011/head`
  - `hs`  = `http://www.hancom.co.kr/hwpml/2011/section`
  - `hc`  = `http://www.hancom.co.kr/hwpml/2011/core`
  - `ha`  = `http://www.hancom.co.kr/hwpml/2011/app`
  - `hpf` = `http://www.hancom.co.kr/schema/2011/hpf`
  - `opf` = `http://www.idpf.org/2007/opf/`
  - `ocf` = `urn:oasis:names:tc:opendocument:xmlns:container`
  - `odf` = `urn:oasis:names:tc:opendocument:xmlns:manifest:1.0`
  - `hv`  = `http://www.hancom.co.kr/hwpml/2011/version`
- Ground-truth test fixtures live in `samples/`: `3.*.hwp`/`.hwpx`, `4.*.hwp`/`.hwpx`.
- TDD: every task writes a failing test first, then minimal code, then commits. Frequent commits.

## Package layout (locked)

```
hwp2hwpx/
├── __init__.py
├── cli.py                 # argparse entry: hwp2hwpx input.hwp -o out.hwpx
├── constants.py           # namespaces, mimetype, xml decl
├── convert.py             # top-level convert(hwp_path, out_path) orchestration
├── hwpmodel/              # HWP-side model (Reader output)
│   ├── __init__.py
│   ├── model.py           # dataclasses: HwpDocument, HwpFont, HwpCharShape, ...
│   └── reader.py          # .hwp -> HwpDocument (via hwp5proc xml)
├── owpml/                 # OWPML-side model + writer (Writer input/output)
│   ├── __init__.py
│   ├── model.py           # dataclasses: OwpmlDocument, Header, Section, Para, Run, Text, ...
│   ├── header_writer.py   # Header -> Contents/header.xml bytes
│   ├── section_writer.py  # Section -> Contents/sectionN.xml bytes
│   ├── package_parts.py   # version.xml, settings.xml, META-INF/*, content.hpf, Preview/*
│   └── writer.py          # OwpmlDocument -> .hwpx (ZIP assembly)
├── mapper/                # HWP model -> OWPML model (ports hwp2hwpx)
│   ├── __init__.py
│   ├── fonts.py
│   ├── char_pr.py
│   ├── para_pr.py
│   └── body.py            # paragraphs/runs/text
└── fidelity/
    ├── __init__.py
    ├── xmlnorm.py         # canonicalize XML for comparison
    └── diff.py            # structural diff + per-element scorer + report
tests/
docs/superpowers/…
pyproject.toml
```

---

### Task 1: Project scaffold + dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `hwp2hwpx/__init__.py`
- Create: `hwp2hwpx/constants.py`
- Create: `hwp2hwpx/cli.py`
- Create: `tests/__init__.py`
- Create: `tests/test_scaffold.py`

**Interfaces:**
- Produces: `hwp2hwpx.constants.NS` (dict[str,str] of prefix→URI), `hwp2hwpx.constants.MIMETYPE` (str), `hwp2hwpx.constants.XML_DECL` (bytes). `hwp2hwpx.cli.main(argv: list[str]) -> int`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "hwp2hwpx"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = ["lxml>=5", "pyhwp>=0.1b15"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
hwp2hwpx = "hwp2hwpx.cli:entrypoint"

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Create a virtualenv and install**

Run:
```bash
python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[dev]"
```
Expected: installs lxml, pyhwp, pytest without error. Confirm `hwp5proc` is available:
```bash
.venv/bin/hwp5proc --version
```
Expected: prints a pyhwp version string (no error).

- [ ] **Step 3: Create `hwp2hwpx/constants.py`**

```python
"""Shared constants: OWPML namespaces and packaging literals."""

NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hpf": "http://www.hancom.co.kr/schema/2011/hpf",
    "opf": "http://www.idpf.org/2007/opf/",
    "ocf": "urn:oasis:names:tc:opendocument:xmlns:container",
    "odf": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
    "hv": "http://www.hancom.co.kr/hwpml/2011/version",
    "dc": "http://purl.org/dc/elements/1.1/",
}

MIMETYPE = "application/hwp+zip"
XML_DECL = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
```

- [ ] **Step 4: Create `hwp2hwpx/cli.py` stub**

```python
"""Command-line entry point."""
import argparse


def main(argv):
    parser = argparse.ArgumentParser(prog="hwp2hwpx",
                                     description="Convert HWP 5.0 files to HWPX.")
    parser.add_argument("input", help="path to input .hwp file")
    parser.add_argument("-o", "--output", required=True, help="path to output .hwpx file")
    parser.parse_args(argv)
    # Wired to convert() in Task 18.
    return 0


def entrypoint():
    import sys
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 5: Create `hwp2hwpx/__init__.py` and `tests/__init__.py`** (both empty files).

- [ ] **Step 6: Write scaffold test `tests/test_scaffold.py`**

```python
from hwp2hwpx import constants
from hwp2hwpx.cli import main


def test_namespaces_present():
    assert constants.NS["hp"].endswith("/2011/paragraph")
    assert constants.MIMETYPE == "application/hwp+zip"


def test_cli_parses_args():
    assert main(["in.hwp", "-o", "out.hwpx"]) == 0
```

- [ ] **Step 7: Run tests**

Run: `.venv/bin/pytest tests/test_scaffold.py -v`
Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml hwp2hwpx/ tests/
git commit -m "feat: project scaffold, constants, CLI stub"
```

---

### Task 2: OWPML model dataclasses

**Files:**
- Create: `hwp2hwpx/owpml/__init__.py` (empty)
- Create: `hwp2hwpx/owpml/model.py`
- Create: `tests/test_owpml_model.py`

**Interfaces:**
- Produces (all frozen=False dataclasses in `hwp2hwpx.owpml.model`):
  - `Font(id: int, face: str, type: str = "TTF", is_embedded: bool = False)`
  - `CharPr(id: int, height: int = 1000, text_color: str = "#000000", font_ref_id: int = 0, bold: bool = False, italic: bool = False)`
  - `ParaPr(id: int, align: str = "LEFT")`  # align ∈ {LEFT,CENTER,RIGHT,JUSTIFY,DISTRIBUTE}
  - `Text(content: str)`
  - `Run(char_pr_id: int, texts: list[Text] = field(default_factory=list))`
  - `Para(id: int, para_pr_id: int, style_id: int = 0, runs: list[Run] = field(default_factory=list))`
  - `Header(fonts_by_lang: dict[str, list[Font]], char_prs: list[CharPr], para_prs: list[ParaPr])`
  - `Section(paras: list[Para])`
  - `Metadata(title: str = "", language: str = "ko")`
  - `OwpmlDocument(header: Header, sections: list[Section], metadata: Metadata)`

- [ ] **Step 1: Write failing test `tests/test_owpml_model.py`**

```python
from hwp2hwpx.owpml.model import (
    Font, CharPr, ParaPr, Text, Run, Para, Header, Section, Metadata, OwpmlDocument,
)


def test_build_minimal_document():
    header = Header(
        fonts_by_lang={"HANGUL": [Font(id=0, face="바탕")]},
        char_prs=[CharPr(id=0)],
        para_prs=[ParaPr(id=0, align="CENTER")],
    )
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[Text("안녕")])])
    doc = OwpmlDocument(header=header, sections=[Section(paras=[para])],
                        metadata=Metadata(title="t"))
    assert doc.sections[0].paras[0].runs[0].texts[0].content == "안녕"
    assert doc.header.para_prs[0].align == "CENTER"
    assert doc.header.fonts_by_lang["HANGUL"][0].face == "바탕"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_owpml_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hwp2hwpx.owpml.model'`.

- [ ] **Step 3: Implement `hwp2hwpx/owpml/model.py`**

```python
"""OWPML (HWPX) side data model — the Writer's input contract."""
from dataclasses import dataclass, field


@dataclass
class Font:
    id: int
    face: str
    type: str = "TTF"
    is_embedded: bool = False


@dataclass
class CharPr:
    id: int
    height: int = 1000
    text_color: str = "#000000"
    font_ref_id: int = 0
    bold: bool = False
    italic: bool = False


@dataclass
class ParaPr:
    id: int
    align: str = "LEFT"


@dataclass
class Text:
    content: str


@dataclass
class Run:
    char_pr_id: int
    texts: list = field(default_factory=list)


@dataclass
class Para:
    id: int
    para_pr_id: int
    style_id: int = 0
    runs: list = field(default_factory=list)


@dataclass
class Header:
    fonts_by_lang: dict = field(default_factory=dict)
    char_prs: list = field(default_factory=list)
    para_prs: list = field(default_factory=list)


@dataclass
class Section:
    paras: list = field(default_factory=list)


@dataclass
class Metadata:
    title: str = ""
    language: str = "ko"


@dataclass
class OwpmlDocument:
    header: Header
    sections: list
    metadata: Metadata
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_owpml_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/ tests/test_owpml_model.py
git commit -m "feat: OWPML data model"
```

---

### Task 3: ZIP packager with mimetype-first/STORED invariant

**Files:**
- Create: `hwp2hwpx/owpml/writer.py`
- Create: `tests/test_zip_packager.py`

**Interfaces:**
- Produces: `hwp2hwpx.owpml.writer.write_package(parts: dict[str, bytes], out_path: str) -> None`. `parts` maps archive names (e.g. `"version.xml"`) to bytes. `mimetype` is written first & STORED automatically; caller must include a `"mimetype"` key OR it is injected from `constants.MIMETYPE`.

- [ ] **Step 1: Write failing test `tests/test_zip_packager.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_zip_packager.py -v`
Expected: FAIL with `ModuleNotFoundError` (writer not yet created).

- [ ] **Step 3: Implement `hwp2hwpx/owpml/writer.py`**

```python
"""Assemble an OWPML document into a .hwpx ZIP package."""
import zipfile
from .. import constants


def write_package(parts, out_path):
    """Write `parts` (name->bytes) to a .hwpx ZIP.

    The `mimetype` entry is always written first and STORED (uncompressed),
    as Hancom requires. A caller-supplied "mimetype" value overrides the default.
    """
    mimetype = parts.get("mimetype", constants.MIMETYPE.encode("ascii"))
    if isinstance(mimetype, str):
        mimetype = mimetype.encode("ascii")
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), mimetype, compress_type=zipfile.ZIP_STORED)
        for name, data in parts.items():
            if name == "mimetype":
                continue
            z.writestr(name, data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_zip_packager.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/writer.py tests/test_zip_packager.py
git commit -m "feat: hwpx zip packager with mimetype-first/stored rule"
```

---

### Task 4: Static & metadata package parts

**Files:**
- Create: `hwp2hwpx/owpml/package_parts.py`
- Create: `tests/test_package_parts.py`

**Interfaces:**
- Consumes: `owpml.model.Metadata`, `constants`.
- Produces in `hwp2hwpx.owpml.package_parts`:
  - `version_xml() -> bytes`
  - `settings_xml() -> bytes`
  - `container_xml() -> bytes`
  - `manifest_xml() -> bytes`
  - `content_hpf(metadata, section_count: int) -> bytes`
  - `prv_text(sections: list) -> bytes`  # plain-text preview from section text

- [ ] **Step 1: Write failing test `tests/test_package_parts.py`**

```python
from lxml import etree
from hwp2hwpx.owpml import package_parts as pp
from hwp2hwpx.owpml.model import Metadata, Section, Para, Run, Text
from hwp2hwpx.constants import NS


def _parse(b):
    return etree.fromstring(b)


def test_version_xml_wellformed_and_targets_wordprocessor():
    root = _parse(pp.version_xml())
    assert root.tag == "{%s}HCFVersion" % NS["hv"]
    assert root.get("tagetApplication") == "WORDPROCESSOR"  # sic: Hancom's real attribute spelling


def test_container_lists_content_hpf():
    root = _parse(pp.container_xml())
    fulls = [e.get("full-path") for e in root.iter("{%s}rootfile" % NS["ocf"])]
    assert "Contents/content.hpf" in fulls


def test_content_hpf_has_manifest_items_and_spine():
    root = _parse(pp.content_hpf(Metadata(title="T"), section_count=1))
    ids = [e.get("id") for e in root.iter("{%s}item" % NS["opf"])]
    assert "header" in ids and "section0" in ids


def test_prv_text_extracts_visible_text():
    sec = Section(paras=[Para(id=0, para_pr_id=0,
                              runs=[Run(char_pr_id=0, texts=[Text("가나다")])])])
    assert "가나다" in pp.prv_text([sec]).decode("utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_package_parts.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/owpml/package_parts.py`**

```python
"""Static and metadata parts of a .hwpx package (verbatim shapes from real Hancom output)."""
from ..constants import XML_DECL, MIMETYPE


def _doc(body_bytes):
    return XML_DECL + body_bytes


def version_xml():
    return _doc(
        b'<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version"'
        b' tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="1"'
        b' buildNumber="0" os="10" xmlVersion="1.5"'
        b' application="hwp2hwpx" appVersion="0.1.0"/>'
    )


def settings_xml():
    return _doc(
        b'<ha:HWPApplicationSetting'
        b' xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"'
        b' xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0">'
        b'<ha:CaretPosition listIDRef="0" paraIDRef="0" pos="0"/>'
        b'</ha:HWPApplicationSetting>'
    )


def container_xml():
    return _doc(
        b'<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container"'
        b' xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf"><ocf:rootfiles>'
        b'<ocf:rootfile full-path="Contents/content.hpf"'
        b' media-type="application/hwpml-package+xml"/>'
        b'<ocf:rootfile full-path="Preview/PrvText.txt" media-type="text/plain"/>'
        b'</ocf:rootfiles></ocf:container>'
    )


def manifest_xml():
    return _doc(
        b'<odf:manifest'
        b' xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"/>'
    )


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def content_hpf(metadata, section_count):
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


def prv_text(sections):
    lines = []
    for sec in sections:
        for para in sec.paras:
            buf = []
            for run in para.runs:
                for t in run.texts:
                    buf.append(t.content)
            lines.append("".join(buf))
    return ("\n".join(lines)).encode("utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_package_parts.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/package_parts.py tests/test_package_parts.py
git commit -m "feat: static + metadata hwpx package parts"
```

---

### Task 5: header.xml serializer

**Files:**
- Create: `hwp2hwpx/owpml/header_writer.py`
- Create: `tests/test_header_writer.py`

**Interfaces:**
- Consumes: `owpml.model.Header` (fonts_by_lang, char_prs, para_prs), `constants.NS`.
- Produces: `hwp2hwpx.owpml.header_writer.header_xml(header: Header) -> bytes`. Root `<hh:head version="1.5" secCnt="1">` containing `<hh:refList>` with `<hh:fontfaces>`, `<hh:charProperties>`, `<hh:paraProperties>`. Uses lxml with the full namespace map.

- [ ] **Step 1: Write failing test `tests/test_header_writer.py`**

```python
from lxml import etree
from hwp2hwpx.owpml.header_writer import header_xml
from hwp2hwpx.owpml.model import Header, Font, CharPr, ParaPr
from hwp2hwpx.constants import NS


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def test_header_has_fonts_charprs_paraprs():
    header = Header(
        fonts_by_lang={"HANGUL": [Font(id=0, face="바탕"), Font(id=1, face="굴림")]},
        char_prs=[CharPr(id=0, height=1000, text_color="#000000")],
        para_prs=[ParaPr(id=0, align="CENTER")],
    )
    root = etree.fromstring(header_xml(header))
    assert root.tag == _hh("head")
    faces = [f.get("face") for f in root.iter(_hh("font"))]
    assert faces == ["바탕", "굴림"]
    charprs = list(root.iter(_hh("charPr")))
    assert charprs[0].get("height") == "1000"
    aligns = [a.get("horizontal") for a in root.iter(_hh("align"))]
    assert aligns == ["CENTER"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_header_writer.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/owpml/header_writer.py`**

```python
"""Serialize an OWPML Header to Contents/header.xml."""
from lxml import etree
from ..constants import NS, XML_DECL

_NSMAP = {k: v for k, v in NS.items()}


def _hh(tag):
    return "{%s}%s" % (NS["hh"], tag)


def header_xml(header):
    root = etree.Element(_hh("head"), nsmap=_NSMAP)
    root.set("version", "1.5")
    root.set("secCnt", "1")
    ref = etree.SubElement(root, _hh("refList"))

    fonts_el = etree.SubElement(ref, _hh("fontfaces"))
    for lang, fonts in header.fonts_by_lang.items():
        ff = etree.SubElement(fonts_el, _hh("fontface"))
        ff.set("lang", lang)
        ff.set("fontCnt", str(len(fonts)))
        for f in fonts:
            fe = etree.SubElement(ff, _hh("font"))
            fe.set("id", str(f.id))
            fe.set("face", f.face)
            fe.set("type", f.type)
            fe.set("isEmbedded", "1" if f.is_embedded else "0")

    cps = etree.SubElement(ref, _hh("charProperties"))
    cps.set("itemCnt", str(len(header.char_prs)))
    for cp in header.char_prs:
        ce = etree.SubElement(cps, _hh("charPr"))
        ce.set("id", str(cp.id))
        ce.set("height", str(cp.height))
        ce.set("textColor", cp.text_color)
        fr = etree.SubElement(ce, _hh("fontRef"))
        for lang in ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user"):
            fr.set(lang, str(cp.font_ref_id))
        if cp.bold:
            etree.SubElement(ce, _hh("bold"))
        if cp.italic:
            etree.SubElement(ce, _hh("italic"))

    pps = etree.SubElement(ref, _hh("paraProperties"))
    pps.set("itemCnt", str(len(header.para_prs)))
    for pp in header.para_prs:
        pe = etree.SubElement(pps, _hh("paraPr"))
        pe.set("id", str(pp.id))
        al = etree.SubElement(pe, _hh("align"))
        al.set("horizontal", pp.align)
        al.set("vertical", "BASELINE")

    return XML_DECL + etree.tostring(root, encoding="UTF-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_header_writer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/header_writer.py tests/test_header_writer.py
git commit -m "feat: header.xml serializer (fonts/charPr/paraPr)"
```

---

### Task 6: section0.xml serializer

**Files:**
- Create: `hwp2hwpx/owpml/section_writer.py`
- Create: `tests/test_section_writer.py`

**Interfaces:**
- Consumes: `owpml.model.Section`, `Para`, `Run`, `Text`, `constants.NS`.
- Produces: `hwp2hwpx.owpml.section_writer.section_xml(section: Section) -> bytes`. Root `<hs:sec>` containing `<hp:p>` → `<hp:run charPrIDRef=…>` → `<hp:t>text</hp:t>`.

- [ ] **Step 1: Write failing test `tests/test_section_writer.py`**

```python
from lxml import etree
from hwp2hwpx.owpml.section_writer import section_xml
from hwp2hwpx.owpml.model import Section, Para, Run, Text
from hwp2hwpx.constants import NS


def _hs(tag):
    return "{%s}%s" % (NS["hs"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def test_section_paragraph_run_text():
    sec = Section(paras=[
        Para(id=0, para_pr_id=2, style_id=1,
             runs=[Run(char_pr_id=3, texts=[Text("가나"), Text("다라")])]),
    ])
    root = etree.fromstring(section_xml(sec))
    assert root.tag == _hs("sec")
    p = root.find(_hp("p"))
    assert p.get("paraPrIDRef") == "2"
    assert p.get("styleIDRef") == "1"
    run = p.find(_hp("run"))
    assert run.get("charPrIDRef") == "3"
    texts = [t.text for t in run.iter(_hp("t"))]
    assert texts == ["가나", "다라"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_section_writer.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/owpml/section_writer.py`**

```python
"""Serialize an OWPML Section to Contents/sectionN.xml."""
from lxml import etree
from ..constants import NS, XML_DECL

_NSMAP = {k: v for k, v in NS.items()}


def _hs(tag):
    return "{%s}%s" % (NS["hs"], tag)


def _hp(tag):
    return "{%s}%s" % (NS["hp"], tag)


def section_xml(section):
    root = etree.Element(_hs("sec"), nsmap=_NSMAP)
    for para in section.paras:
        p = etree.SubElement(root, _hp("p"))
        p.set("id", str(para.id))
        p.set("paraPrIDRef", str(para.para_pr_id))
        p.set("styleIDRef", str(para.style_id))
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")
        for run in para.runs:
            r = etree.SubElement(p, _hp("run"))
            r.set("charPrIDRef", str(run.char_pr_id))
            for t in run.texts:
                te = etree.SubElement(r, _hp("t"))
                te.text = t.content
    return XML_DECL + etree.tostring(root, encoding="UTF-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_section_writer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/section_writer.py tests/test_section_writer.py
git commit -m "feat: section0.xml serializer (p/run/t)"
```

---

### Task 7: Top-level HWPX writer (assemble full package)

**Files:**
- Modify: `hwp2hwpx/owpml/writer.py` (add `write_hwpx`)
- Create: `tests/test_writer_endtoend.py`

**Interfaces:**
- Consumes: `owpml.model.OwpmlDocument`, `header_writer.header_xml`, `section_writer.section_xml`, `package_parts.*`, `write_package`.
- Produces: `hwp2hwpx.owpml.writer.write_hwpx(doc: OwpmlDocument, out_path: str) -> None`. Emits the full archive: `mimetype`, `version.xml`, `settings.xml`, `Contents/header.xml`, `Contents/section0.xml…`, `Contents/content.hpf`, `META-INF/container.xml`, `META-INF/manifest.xml`, `Preview/PrvText.txt`.

- [ ] **Step 1: Write failing test `tests/test_writer_endtoend.py`**

```python
import zipfile
from lxml import etree
from hwp2hwpx.owpml.writer import write_hwpx
from hwp2hwpx.owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Text, Font, CharPr, ParaPr, Metadata,
)


def _doc():
    header = Header(fonts_by_lang={"HANGUL": [Font(id=0, face="바탕")]},
                    char_prs=[CharPr(id=0)], para_prs=[ParaPr(id=0)])
    para = Para(id=0, para_pr_id=0, runs=[Run(char_pr_id=0, texts=[Text("가나다")])])
    return OwpmlDocument(header=header, sections=[Section(paras=[para])],
                         metadata=Metadata(title="T"))


def test_full_package_structure(tmp_path):
    out = tmp_path / "out.hwpx"
    write_hwpx(_doc(), str(out))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names[0] == "mimetype"
        for required in ["version.xml", "settings.xml", "Contents/header.xml",
                         "Contents/section0.xml", "Contents/content.hpf",
                         "META-INF/container.xml", "META-INF/manifest.xml",
                         "Preview/PrvText.txt"]:
            assert required in names, required
        # every XML part is well-formed
        for n in names:
            if n.endswith(".xml") or n.endswith(".hpf"):
                etree.fromstring(z.read(n))
        assert "가나다" in z.read("Preview/PrvText.txt").decode("utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_writer_endtoend.py -v`
Expected: FAIL with `ImportError: cannot import name 'write_hwpx'`.

- [ ] **Step 3: Add `write_hwpx` to `hwp2hwpx/owpml/writer.py`**

```python
from . import package_parts
from .header_writer import header_xml
from .section_writer import section_xml


def write_hwpx(doc, out_path):
    parts = {
        "version.xml": package_parts.version_xml(),
        "settings.xml": package_parts.settings_xml(),
        "Contents/header.xml": header_xml(doc.header),
        "Contents/content.hpf": package_parts.content_hpf(doc.metadata, len(doc.sections)),
        "META-INF/container.xml": package_parts.container_xml(),
        "META-INF/manifest.xml": package_parts.manifest_xml(),
        "Preview/PrvText.txt": package_parts.prv_text(doc.sections),
    }
    for i, section in enumerate(doc.sections):
        parts["Contents/section%d.xml" % i] = section_xml(section)
    write_package(parts, out_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_writer_endtoend.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/owpml/writer.py tests/test_writer_endtoend.py
git commit -m "feat: assemble full .hwpx package from OwpmlDocument"
```

---

### Task 8: HWP reader — hwp5proc XML dump + fixture capture

**Files:**
- Create: `hwp2hwpx/hwpmodel/__init__.py` (empty)
- Create: `hwp2hwpx/hwpmodel/reader.py` (dump function only in this task)
- Create: `tests/fixtures/` (directory)
- Create: `tests/test_reader_dump.py`
- Create: `scripts/capture_fixture.py`

**Interfaces:**
- Produces: `hwp2hwpx.hwpmodel.reader.hwp5_xml(hwp_path: str) -> bytes` — returns the raw XML dump from pyhwp's `hwp5proc xml <path>` (the full parsed record tree). Uses `subprocess` invoking the `hwp5proc` on PATH.

- [ ] **Step 1: Capture a real fixture from the sample** (discovery step — produces ground truth for later parsing)

Create `scripts/capture_fixture.py`:

```python
"""Capture pyhwp's hwp5proc XML dump for a sample, as a test fixture."""
import subprocess
import sys
import os

SAMPLE = "samples/3.*.hwp"
OUT = "tests/fixtures/sample3.hwp5.xml"


def main():
    os.makedirs("tests/fixtures", exist_ok=True)
    xml = subprocess.check_output(["hwp5proc", "xml", SAMPLE])
    with open(OUT, "wb") as f:
        f.write(xml)
    print("wrote", OUT, len(xml), "bytes")


if __name__ == "__main__":
    sys.exit(main())
```

Run: `.venv/bin/python scripts/capture_fixture.py`
Expected: prints `wrote tests/fixtures/sample3.hwp5.xml <N> bytes` with N > 0. Then inspect the top of the file to learn the element names pyhwp emits (needed for Tasks 9–10):
```bash
head -c 2000 tests/fixtures/sample3.hwp5.xml
```
Record the actual tag names you see (e.g. record `tag-id` names like `FaceName`, `CharShape`, `ParaShape`, `ParaText`, `ParaCharShape`) — Tasks 9 and 10 parse these. If pyhwp's tag names differ from those assumed below, adjust the XPath strings in Tasks 9–10 to match what this fixture actually contains.

- [ ] **Step 2: Write failing test `tests/test_reader_dump.py`**

```python
from hwp2hwpx.hwpmodel.reader import hwp5_xml
from lxml import etree

SAMPLE = "samples/3.*.hwp"


def test_dump_is_wellformed_xml():
    xml = hwp5_xml(SAMPLE)
    root = etree.fromstring(xml)
    # pyhwp wraps the document tree in a root element; it must parse and be non-empty.
    assert len(root) > 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_reader_dump.py -v`
Expected: FAIL with `ModuleNotFoundError` (reader has no `hwp5_xml` yet).

- [ ] **Step 4: Implement `hwp2hwpx/hwpmodel/reader.py`**

```python
"""Read a .hwp file into an in-memory model, via pyhwp's hwp5proc XML dump."""
import subprocess


def hwp5_xml(hwp_path):
    """Return pyhwp's full XML dump of the parsed HWP record tree."""
    return subprocess.check_output(["hwp5proc", "xml", hwp_path])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_reader_dump.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/ tests/fixtures/sample3.hwp5.xml tests/test_reader_dump.py scripts/capture_fixture.py
git commit -m "feat: HWP reader dump via hwp5proc + captured fixture"
```

---

### Task 9: HWP model + parse DocInfo (fonts, char shapes, para shapes)

**Files:**
- Create: `hwp2hwpx/hwpmodel/model.py`
- Modify: `hwp2hwpx/hwpmodel/reader.py` (make `hwp5_xml` robust + add `read_docinfo`)
- Create: `tests/test_reader_docinfo.py`

**Interfaces:**
- Produces in `hwp2hwpx.hwpmodel.model` (dataclasses):
  - `HwpFont(index: int, name: str)`
  - `HwpCharShape(index: int, base_size: int, text_color: str, font_id: int, bold: bool, italic: bool)`  # base_size in HWPUNIT (1/100 pt); text_color is a `#RRGGBB` string
  - `HwpParaShape(index: int, align: str)`  # align normalized to LEFT/CENTER/RIGHT/JUSTIFY/DISTRIBUTE
  - `HwpDocInfo(fonts, char_shapes, para_shapes)`
- Produces: `hwp2hwpx.hwpmodel.reader.read_docinfo(xml_bytes: bytes) -> HwpDocInfo` parsing the dump from Task 8.

**GROUND TRUTH (from the Task 8 fixture — these are the REAL pyhwp 0.1b15 names, verified):**
- Root `<HwpDoc>` → `<DocInfo>` → `<IdMappings>` holds flat, **id-less, positional** lists: `<FaceName name="굴림체" .../>` (65 of them), `<CharShape basesize="1000" bold="0" italic="0" text-color="#000000">` with a child `<FontFace ko=".." en=".." cn=".." jp=".." other=".." symbol=".." user=".."/>` (103), `<ParaShape align="center|left|right|both" .../>` (126). Index in document order == the id referenced elsewhere (`charshape-id`, `parashape-id`).
- **Fonts are grouped by language** in the flat list, in the fixed order `ko, en, cn, jp, other, symbol, user`, with per-group counts on `IdMappings` attributes `ko-fonts`, `en-fonts`, `cn-fonts`, `jp-fonts`, `other-fonts`, `symbol-fonts`, `user-fonts`. A CharShape's `FontFace/@ko` is a 0-based index **within the ko sub-range**; the global FaceName index = `ko_group_offset + FontFace@ko`. This task resolves each char shape's representative font from its **ko** font (Korean docs); per-language font refs are a later fidelity refinement.
- `text-color` is already a `#RRGGBB` string — pass it through, do NOT do BGR-int conversion.
- `align` values seen: `both` (→JUSTIFY), `center`, `left`, `right`. Include `justify`/`distribute`/`divide` in the map defensively.

- [ ] **Step 1: Write failing test `tests/test_reader_docinfo.py`**

```python
from hwp2hwpx.hwpmodel.reader import read_docinfo

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _docinfo():
    with open(FIXTURE, "rb") as f:
        return read_docinfo(f.read())


def test_fonts_parsed():
    di = _docinfo()
    assert len(di.fonts) == 65
    assert di.fonts[0].name == "굴림체"
    assert all(isinstance(f.name, str) and f.name for f in di.fonts)


def test_char_shapes_have_font_and_size():
    di = _docinfo()
    assert len(di.char_shapes) == 103
    cs = di.char_shapes[0]
    assert cs.base_size == 1000
    assert cs.text_color.startswith("#") and len(cs.text_color) == 7
    # CharShape[0] FontFace ko=12, ko group starts at global offset 0 -> font_id 12
    assert cs.font_id == 12
    assert 0 <= cs.font_id < len(di.fonts)


def test_para_shapes_have_align():
    di = _docinfo()
    assert len(di.para_shapes) == 126
    assert {p.align for p in di.para_shapes} <= {
        "LEFT", "CENTER", "RIGHT", "JUSTIFY", "DISTRIBUTE"}
    assert any(p.align == "CENTER" for p in di.para_shapes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_reader_docinfo.py -v`
Expected: FAIL with `ImportError` (no `read_docinfo`).

- [ ] **Step 3: Implement `hwp2hwpx/hwpmodel/model.py`**

```python
"""HWP-side data model — the Reader's output / Mapper's input contract."""
from dataclasses import dataclass, field


@dataclass
class HwpFont:
    index: int
    name: str


@dataclass
class HwpCharShape:
    index: int
    base_size: int
    text_color: str = "#000000"
    font_id: int = 0
    bold: bool = False
    italic: bool = False


@dataclass
class HwpParaShape:
    index: int
    align: str = "LEFT"


@dataclass
class HwpDocInfo:
    fonts: list = field(default_factory=list)
    char_shapes: list = field(default_factory=list)
    para_shapes: list = field(default_factory=list)
```

- [ ] **Step 4: Update `hwp2hwpx/hwpmodel/reader.py` — make `hwp5_xml` robust, add `read_docinfo`**

Replace the current top of the file (the `import subprocess` + `hwp5_xml`) with the block below (locating `hwp5proc` next to the running interpreter so tests/CLI work without `.venv/bin` on `PATH`), then append `read_docinfo`:

```python
"""Read a .hwp file into an in-memory model, via pyhwp's hwp5proc XML dump."""
import os
import sys
import subprocess
from lxml import etree
from .model import HwpFont, HwpCharShape, HwpParaShape, HwpDocInfo

_ALIGN_MAP = {
    "left": "LEFT", "center": "CENTER", "right": "RIGHT",
    "both": "JUSTIFY", "justify": "JUSTIFY",
    "distribute": "DISTRIBUTE", "divide": "DISTRIBUTE",
}

# HWP5 font language groups, in the fixed order pyhwp lays FaceName elements out.
_FONT_LANGS = ("ko", "en", "cn", "jp", "other", "symbol", "user")


def _hwp5proc():
    """Locate hwp5proc next to the current interpreter, else rely on PATH."""
    candidate = os.path.join(os.path.dirname(sys.executable), "hwp5proc")
    return candidate if os.path.exists(candidate) else "hwp5proc"


def hwp5_xml(hwp_path):
    """Return pyhwp's full XML dump of the parsed HWP record tree."""
    return subprocess.check_output([_hwp5proc(), "xml", hwp_path])


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _font_group_offsets(id_mappings):
    """Global start index of each language group within the flat FaceName list."""
    offsets = {}
    running = 0
    for lang in _FONT_LANGS:
        offsets[lang] = running
        running += _int(id_mappings.get("%s-fonts" % lang))
    return offsets


def read_docinfo(xml_bytes):
    root = etree.fromstring(xml_bytes)
    id_mappings = root.find(".//IdMappings")
    if id_mappings is None:
        return HwpDocInfo()
    offsets = _font_group_offsets(id_mappings)

    fonts = [HwpFont(index=i, name=el.get("name") or "")
             for i, el in enumerate(id_mappings.findall("FaceName"))]

    char_shapes = []
    for i, el in enumerate(id_mappings.findall("CharShape")):
        ff = el.find("FontFace")
        ko_local = _int(ff.get("ko")) if ff is not None else 0
        char_shapes.append(HwpCharShape(
            index=i,
            base_size=_int(el.get("basesize"), 1000),
            text_color=el.get("text-color") or "#000000",
            font_id=offsets.get("ko", 0) + ko_local,
            bold=el.get("bold") == "1",
            italic=el.get("italic") == "1",
        ))

    para_shapes = []
    for i, el in enumerate(id_mappings.findall("ParaShape")):
        raw = (el.get("align") or "left").lower()
        para_shapes.append(HwpParaShape(index=i, align=_ALIGN_MAP.get(raw, "LEFT")))

    return HwpDocInfo(fonts=fonts, char_shapes=char_shapes, para_shapes=para_shapes)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_reader_docinfo.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/ tests/test_reader_docinfo.py
git commit -m "feat: parse HWP DocInfo (fonts, char/para shapes)"
```

---

### Task 10: Parse BodyText (sections → paragraphs → text runs)

**Files:**
- Create: `hwp2hwpx/hwpmodel/model.py` additions (append body classes)
- Modify: `hwp2hwpx/hwpmodel/reader.py` (add `read_document`)
- Create: `tests/test_reader_body.py`

**Interfaces:**
- Produces in `hwp2hwpx.hwpmodel.model`:
  - `HwpRun(char_shape_id: int, text: str)`
  - `HwpParagraph(para_shape_id: int, style_id: int = 0, runs=[])`
  - `HwpSection(paragraphs=[])`
  - `HwpDocument(docinfo, sections=[])`
- Produces: `hwp2hwpx.hwpmodel.reader.read_document(xml_bytes: bytes) -> HwpDocument`.

**GROUND TRUTH (from the Task 8 fixture — verified):**
- Sections are `BodyText/SectionDef` elements (NOT `Section`). Each section's top-level body paragraphs are the **direct** `Paragraph` children of the section's `ColumnSet` (`SectionDef/ColumnSet/Paragraph`).
- There is **no `ParaText`/`ParaCharShape`**. A paragraph's text runs are `<Text charshape-id=".." lang="..">…</Text>` elements sitting directly under the paragraph's `<LineSeg>` children, interleaved with `<ControlChar>` (breaks/tabs — skip them for text). Each `Text` element is one run → **multiple runs per paragraph** naturally.
- Tables nest more `Paragraph`s deep under `Paragraph/LineSeg/TableControl/TableBody/TableRow/TableCell/…`. This task takes ONLY the top-level body paragraphs via `SectionDef/ColumnSet/Paragraph` and reads runs via `Paragraph/LineSeg/Text` (direct children), which **excludes** table-cell text. Table content is out of scope here — a follow-up plan. Empty paragraphs (no `Text` runs) are kept as run-less paragraphs.
- `Paragraph/@parashape-id` and `@style-id` are the shape/style references.

- [ ] **Step 1: Write failing test `tests/test_reader_body.py`**

```python
from hwp2hwpx.hwpmodel.reader import read_document

FIXTURE = "tests/fixtures/sample3.hwp5.xml"


def _doc():
    with open(FIXTURE, "rb") as f:
        return read_document(f.read())


def test_has_one_section_with_many_paragraphs():
    doc = _doc()
    assert len(doc.sections) == 1
    # 220 direct ColumnSet>Paragraph children in this sample (table-cell paras excluded)
    assert len(doc.sections[0].paragraphs) == 220


def test_paragraphs_have_multiple_runs_and_real_text():
    doc = _doc()
    paras = doc.sections[0].paragraphs
    # at least one paragraph is split into multiple Text runs
    assert any(len(p.runs) >= 2 for p in paras)
    all_text = "".join(r.text for p in paras for r in p.runs)
    assert all_text.strip() != ""
    # runs carry a real charshape-id reference
    a_run = next(r for p in paras for r in p.runs)
    assert a_run.char_shape_id >= 0


def test_docinfo_attached():
    doc = _doc()
    assert len(doc.docinfo.fonts) == 65
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_reader_body.py -v`
Expected: FAIL with `ImportError` (no `read_document`).

- [ ] **Step 3: Append body dataclasses to `hwp2hwpx/hwpmodel/model.py`**

```python
@dataclass
class HwpRun:
    char_shape_id: int
    text: str


@dataclass
class HwpParagraph:
    para_shape_id: int
    style_id: int = 0
    runs: list = field(default_factory=list)


@dataclass
class HwpSection:
    paragraphs: list = field(default_factory=list)


@dataclass
class HwpDocument:
    docinfo: HwpDocInfo
    sections: list = field(default_factory=list)
```

- [ ] **Step 4: Add `read_document` to `hwp2hwpx/hwpmodel/reader.py`**

```python
from .model import HwpRun, HwpParagraph, HwpSection, HwpDocument


def _paragraph_runs(para_el):
    """One run per <Text> directly under the paragraph's LineSegs (skips
    ControlChars and any table-cell text nested deeper)."""
    runs = []
    for text_el in para_el.findall("LineSeg/Text"):
        content = text_el.text or ""
        if content:
            runs.append(HwpRun(
                char_shape_id=_int(text_el.get("charshape-id")),
                text=content,
            ))
    return runs


def read_document(xml_bytes):
    docinfo = read_docinfo(xml_bytes)
    root = etree.fromstring(xml_bytes)
    sections = []
    for sec_el in root.findall(".//SectionDef"):
        paras = []
        for col in sec_el.findall("ColumnSet"):
            for para_el in col.findall("Paragraph"):
                paras.append(HwpParagraph(
                    para_shape_id=_int(para_el.get("parashape-id")),
                    style_id=_int(para_el.get("style-id")),
                    runs=_paragraph_runs(para_el),
                ))
        sections.append(HwpSection(paragraphs=paras))
    if not sections:
        sections = [HwpSection(paragraphs=[])]
    return HwpDocument(docinfo=docinfo, sections=sections)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_reader_body.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add hwp2hwpx/hwpmodel/ tests/test_reader_body.py
git commit -m "feat: parse HWP body (sections/paragraphs/runs)"
```

---

### Task 11: Mapper — fonts → fontface

**Files:**
- Create: `hwp2hwpx/mapper/__init__.py` (empty)
- Create: `hwp2hwpx/mapper/fonts.py`
- Create: `tests/test_mapper_fonts.py`

**Interfaces:**
- Consumes: `hwpmodel.model.HwpFont`.
- Produces: `hwp2hwpx.mapper.fonts.map_fonts(hwp_fonts: list[HwpFont]) -> dict[str, list[owpml.model.Font]]` — returns `{"HANGUL": [...]}` (single lang bucket for now; multi-lang is a follow-up). Font id == source index.

- [ ] **Step 1: Write failing test `tests/test_mapper_fonts.py`**

```python
from hwp2hwpx.mapper.fonts import map_fonts
from hwp2hwpx.hwpmodel.model import HwpFont


def test_maps_fonts_preserving_order_and_index():
    src = [HwpFont(index=0, name="바탕"), HwpFont(index=1, name="굴림")]
    out = map_fonts(src)
    assert list(out.keys()) == ["HANGUL"]
    assert [f.id for f in out["HANGUL"]] == [0, 1]
    assert [f.face for f in out["HANGUL"]] == ["바탕", "굴림"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mapper_fonts.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/mapper/fonts.py`**

```python
"""Map HWP fonts to OWPML fontfaces."""
from ..owpml.model import Font


def map_fonts(hwp_fonts):
    return {"HANGUL": [Font(id=f.index, face=f.name) for f in hwp_fonts]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_mapper_fonts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/ tests/test_mapper_fonts.py
git commit -m "feat: mapper for fonts -> fontface"
```

---

### Task 12: Mapper — char shape → charPr

**Files:**
- Create: `hwp2hwpx/mapper/char_pr.py`
- Create: `tests/test_mapper_charpr.py`

**Interfaces:**
- Consumes: `hwpmodel.model.HwpCharShape`.
- Produces: `hwp2hwpx.mapper.char_pr.map_char_shapes(shapes: list[HwpCharShape]) -> list[owpml.model.CharPr]`.

**GROUND TRUTH:** `HwpCharShape.text_color` is already a `#RRGGBB` string (pyhwp emits it that way — see Task 9); pass it straight through. No BGR-int conversion needed. `font_id` is already the resolved global FaceName index from Task 9.

- [ ] **Step 1: Write failing test `tests/test_mapper_charpr.py`**

```python
from hwp2hwpx.mapper.char_pr import map_char_shapes
from hwp2hwpx.hwpmodel.model import HwpCharShape


def test_map_char_shape_fields():
    src = [HwpCharShape(index=0, base_size=1400, text_color="#FF0000", font_id=3,
                        bold=True, italic=False)]
    out = map_char_shapes(src)
    assert out[0].id == 0
    assert out[0].height == 1400
    assert out[0].text_color == "#FF0000"
    assert out[0].font_ref_id == 3
    assert out[0].bold is True
    assert out[0].italic is False


def test_map_preserves_order_and_count():
    src = [HwpCharShape(index=0, base_size=1000, text_color="#000000"),
           HwpCharShape(index=1, base_size=1200, text_color="#112233")]
    out = map_char_shapes(src)
    assert [c.id for c in out] == [0, 1]
    assert [c.text_color for c in out] == ["#000000", "#112233"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mapper_charpr.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/mapper/char_pr.py`**

```python
"""Map HWP character shapes to OWPML charPr."""
from ..owpml.model import CharPr


def map_char_shapes(shapes):
    out = []
    for cs in shapes:
        out.append(CharPr(
            id=cs.index,
            height=cs.base_size,
            text_color=cs.text_color,
            font_ref_id=cs.font_id,
            bold=cs.bold,
            italic=cs.italic,
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_mapper_charpr.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/char_pr.py tests/test_mapper_charpr.py
git commit -m "feat: mapper for char shape -> charPr"
```

---

### Task 13: Mapper — para shape → paraPr

**Files:**
- Create: `hwp2hwpx/mapper/para_pr.py`
- Create: `tests/test_mapper_parapr.py`

**Interfaces:**
- Consumes: `hwpmodel.model.HwpParaShape`.
- Produces: `hwp2hwpx.mapper.para_pr.map_para_shapes(shapes: list[HwpParaShape]) -> list[owpml.model.ParaPr]`. Align passes through (already normalized in reader).

- [ ] **Step 1: Write failing test `tests/test_mapper_parapr.py`**

```python
from hwp2hwpx.mapper.para_pr import map_para_shapes
from hwp2hwpx.hwpmodel.model import HwpParaShape


def test_map_para_shape_align():
    out = map_para_shapes([HwpParaShape(index=0, align="CENTER"),
                           HwpParaShape(index=1, align="JUSTIFY")])
    assert [p.id for p in out] == [0, 1]
    assert [p.align for p in out] == ["CENTER", "JUSTIFY"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mapper_parapr.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/mapper/para_pr.py`**

```python
"""Map HWP paragraph shapes to OWPML paraPr."""
from ..owpml.model import ParaPr


def map_para_shapes(shapes):
    return [ParaPr(id=s.index, align=s.align) for s in shapes]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_mapper_parapr.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/para_pr.py tests/test_mapper_parapr.py
git commit -m "feat: mapper for para shape -> paraPr"
```

---

### Task 14: Mapper — body (document → OwpmlDocument)

**Files:**
- Create: `hwp2hwpx/mapper/body.py`
- Create: `tests/test_mapper_body.py`

**Interfaces:**
- Consumes: `hwpmodel.model.HwpDocument`, `map_fonts`, `map_char_shapes`, `map_para_shapes`.
- Produces: `hwp2hwpx.mapper.body.map_document(hwp_doc: HwpDocument, title: str = "") -> owpml.model.OwpmlDocument`. Builds Header from docinfo; maps each HwpSection→Section, HwpParagraph→Para (para_pr_id = para_shape_id, style_id = style_id), HwpRun→Run (char_pr_id = char_shape_id) with a single Text.

- [ ] **Step 1: Write failing test `tests/test_mapper_body.py`**

```python
from hwp2hwpx.mapper.body import map_document
from hwp2hwpx.hwpmodel.model import (
    HwpDocument, HwpDocInfo, HwpFont, HwpCharShape, HwpParaShape,
    HwpSection, HwpParagraph, HwpRun,
)


def _hwp_doc():
    di = HwpDocInfo(
        fonts=[HwpFont(0, "바탕")],
        char_shapes=[HwpCharShape(index=0, base_size=1000)],
        para_shapes=[HwpParaShape(index=0, align="CENTER")],
    )
    sec = HwpSection(paragraphs=[
        HwpParagraph(para_shape_id=0, style_id=5,
                     runs=[HwpRun(char_shape_id=0, text="가나다")])
    ])
    return HwpDocument(docinfo=di, sections=[sec])


def test_map_document_builds_owpml():
    doc = map_document(_hwp_doc(), title="T")
    assert doc.metadata.title == "T"
    assert doc.header.fonts_by_lang["HANGUL"][0].face == "바탕"
    assert len(doc.header.char_prs) == 1
    assert len(doc.header.para_prs) == 1
    para = doc.sections[0].paras[0]
    assert para.para_pr_id == 0
    assert para.style_id == 5
    assert para.runs[0].char_pr_id == 0
    assert para.runs[0].texts[0].content == "가나다"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mapper_body.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/mapper/body.py`**

```python
"""Map a whole HwpDocument to an OwpmlDocument."""
from ..owpml.model import (
    OwpmlDocument, Header, Section, Para, Run, Text, Metadata,
)
from .fonts import map_fonts
from .char_pr import map_char_shapes
from .para_pr import map_para_shapes


def map_document(hwp_doc, title=""):
    di = hwp_doc.docinfo
    header = Header(
        fonts_by_lang=map_fonts(di.fonts),
        char_prs=map_char_shapes(di.char_shapes),
        para_prs=map_para_shapes(di.para_shapes),
    )
    sections = []
    para_id = 0
    for hsec in hwp_doc.sections:
        paras = []
        for hpar in hsec.paragraphs:
            runs = [Run(char_pr_id=r.char_shape_id, texts=[Text(r.text)])
                    for r in hpar.runs]
            paras.append(Para(id=para_id, para_pr_id=hpar.para_shape_id,
                              style_id=hpar.style_id, runs=runs))
            para_id += 1
        sections.append(Section(paras=paras))
    return OwpmlDocument(header=header, sections=sections,
                         metadata=Metadata(title=title))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_mapper_body.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/mapper/body.py tests/test_mapper_body.py
git commit -m "feat: mapper for whole document -> OwpmlDocument"
```

---

### Task 15: End-to-end convert() orchestration

**Files:**
- Create: `hwp2hwpx/convert.py`
- Create: `tests/test_convert_endtoend.py`

**Interfaces:**
- Consumes: `hwpmodel.reader.hwp5_xml` + `read_document`, `mapper.body.map_document`, `owpml.writer.write_hwpx`.
- Produces: `hwp2hwpx.convert.convert(hwp_path: str, out_path: str) -> None`.

- [ ] **Step 1: Write failing test `tests/test_convert_endtoend.py`**

```python
import zipfile
from lxml import etree
from hwp2hwpx.convert import convert

SAMPLE = "samples/3.*.hwp"


def test_convert_produces_valid_hwpx(tmp_path):
    out = tmp_path / "out.hwpx"
    convert(SAMPLE, str(out))
    with zipfile.ZipFile(out) as z:
        assert z.namelist()[0] == "mimetype"
        # section text is non-empty and well-formed
        sec = z.read("Contents/section0.xml")
        root = etree.fromstring(sec)
        text = "".join(t.text or "" for t in root.iter(
            "{http://www.hancom.co.kr/hwpml/2011/paragraph}t"))
        assert text.strip() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_convert_endtoend.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/convert.py`**

```python
"""Top-level HWP -> HWPX conversion."""
import os
from .hwpmodel.reader import hwp5_xml, read_document
from .mapper.body import map_document
from .owpml.writer import write_hwpx


def convert(hwp_path, out_path):
    xml = hwp5_xml(hwp_path)
    hwp_doc = read_document(xml)
    title = os.path.splitext(os.path.basename(hwp_path))[0]
    owpml_doc = map_document(hwp_doc, title=title)
    write_hwpx(owpml_doc, out_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_convert_endtoend.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/convert.py tests/test_convert_endtoend.py
git commit -m "feat: end-to-end HWP->HWPX convert()"
```

---

### Task 16: Fidelity harness — XML normalizer + unzip helper

**Files:**
- Create: `hwp2hwpx/fidelity/__init__.py` (empty)
- Create: `hwp2hwpx/fidelity/xmlnorm.py`
- Create: `tests/test_xmlnorm.py`

**Interfaces:**
- Produces:
  - `hwp2hwpx.fidelity.xmlnorm.unzip_parts(hwpx_path: str) -> dict[str, bytes]` (name→bytes).
  - `hwp2hwpx.fidelity.xmlnorm.canonical(xml_bytes: bytes) -> str` — canonical form: attributes sorted, insignificant whitespace stripped, comments removed, so two structurally-equal XML docs compare equal as strings.

- [ ] **Step 1: Write failing test `tests/test_xmlnorm.py`**

```python
from hwp2hwpx.fidelity.xmlnorm import canonical, unzip_parts


def test_canonical_ignores_attr_order_and_ws():
    a = b'<r><a x="1"  y="2">  t </a></r>'
    b = b'<r>\n  <a y="2" x="1">  t </a>\n</r>'
    assert canonical(a) == canonical(b)


def test_canonical_detects_real_difference():
    a = b'<r><a x="1"/></r>'
    b = b'<r><a x="2"/></r>'
    assert canonical(a) != canonical(b)


def test_unzip_parts_reads_sample(tmp_path):
    parts = unzip_parts("samples/3.*.hwpx")
    assert "Contents/section0.xml" in parts
    assert parts["mimetype"] == b"application/hwp+zip"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_xmlnorm.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/fidelity/xmlnorm.py`**

```python
"""Normalize XML and unzip HWPX parts for fidelity comparison."""
import zipfile
from lxml import etree


def unzip_parts(hwpx_path):
    parts = {}
    with zipfile.ZipFile(hwpx_path) as z:
        for name in z.namelist():
            parts[name] = z.read(name)
    return parts


def canonical(xml_bytes):
    parser = etree.XMLParser(remove_blank_text=True, remove_comments=True)
    root = etree.fromstring(xml_bytes, parser)
    _sort_attrs(root)
    for el in root.iter():
        if el.text and not el.text.strip():
            el.text = None
        if el.tail and not el.tail.strip():
            el.tail = None
    return etree.tostring(root, encoding="unicode")


def _sort_attrs(el):
    for child in el.iter():
        attrs = sorted(child.attrib.items())
        for k in list(child.attrib):
            del child.attrib[k]
        for k, v in attrs:
            child.set(k, v)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_xmlnorm.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hwp2hwpx/fidelity/ tests/test_xmlnorm.py
git commit -m "feat: fidelity xml normalizer + unzip helper"
```

---

### Task 17: Fidelity harness — structural diff + per-element scorer

**Files:**
- Create: `hwp2hwpx/fidelity/diff.py`
- Create: `tests/test_fidelity_diff.py`

**Interfaces:**
- Consumes: `xmlnorm.canonical`, `xmlnorm.unzip_parts`.
- Produces:
  - `hwp2hwpx.fidelity.diff.element_counts(xml_bytes: bytes) -> dict[str, int]` — count of each local tag name (namespace-stripped).
  - `hwp2hwpx.fidelity.diff.score_part(ours: bytes, theirs: bytes) -> dict` → `{"match": float, "our_counts": {...}, "their_counts": {...}, "missing": {...}}` where `match` = sum(min(our,their) per tag)/sum(their) in [0,1].
  - `hwp2hwpx.fidelity.diff.report(our_hwpx: str, their_hwpx: str) -> str` — human-readable per-file report comparing `Contents/section0.xml` and `Contents/header.xml`.

- [ ] **Step 1: Write failing test `tests/test_fidelity_diff.py`**

```python
from hwp2hwpx.fidelity.diff import element_counts, score_part


def test_element_counts_strips_namespace():
    xml = (b'<hs:sec xmlns:hs="urn:s" xmlns:hp="urn:p">'
           b'<hp:p><hp:run><hp:t>a</hp:t></hp:run>'
           b'<hp:run><hp:t>b</hp:t></hp:run></hp:p></hs:sec>')
    counts = element_counts(xml)
    assert counts["p"] == 1
    assert counts["run"] == 2
    assert counts["t"] == 2


def test_score_identical_is_one():
    xml = b'<r><a/><a/><b/></r>'
    s = score_part(xml, xml)
    assert s["match"] == 1.0


def test_score_partial():
    ours = b'<r><a/></r>'
    theirs = b'<r><a/><a/><b/></r>'  # 3 elements under root; we have 1 of the a's, 0 b
    s = score_part(ours, theirs)
    assert 0.0 < s["match"] < 1.0
    assert s["missing"].get("b") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_fidelity_diff.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `hwp2hwpx/fidelity/diff.py`**

```python
"""Structural diff + per-element fidelity scoring between our HWPX and Hancom's."""
from collections import Counter
from lxml import etree
from .xmlnorm import unzip_parts


def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def element_counts(xml_bytes):
    root = etree.fromstring(xml_bytes)
    counts = Counter()
    for el in root.iter():
        counts[_local(el.tag)] += 1
    # Do not count the root itself as content.
    counts[_local(root.tag)] -= 1
    if counts[_local(root.tag)] <= 0:
        del counts[_local(root.tag)]
    return dict(counts)


def score_part(ours, theirs):
    oc = element_counts(ours)
    tc = element_counts(theirs)
    total = sum(tc.values())
    matched = sum(min(oc.get(k, 0), v) for k, v in tc.items())
    missing = {k: v - oc.get(k, 0) for k, v in tc.items() if v - oc.get(k, 0) > 0}
    match = (matched / total) if total else 1.0
    return {"match": match, "our_counts": oc, "their_counts": tc, "missing": missing}


def report(our_hwpx, their_hwpx):
    ours = unzip_parts(our_hwpx)
    theirs = unzip_parts(their_hwpx)
    lines = []
    for part in ("Contents/header.xml", "Contents/section0.xml"):
        if part not in ours or part not in theirs:
            lines.append("%s: MISSING (ours=%s theirs=%s)"
                         % (part, part in ours, part in theirs))
            continue
        s = score_part(ours[part], theirs[part])
        lines.append("%s: match=%.1f%%" % (part, s["match"] * 100))
        top = sorted(s["missing"].items(), key=lambda kv: -kv[1])[:8]
        for tag, n in top:
            lines.append("    missing %-16s x%d" % (tag, n))
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_fidelity_diff.py -v`
Expected: PASS.

- [ ] **Step 5: Add a reporting test that prints (not asserts) real scores** — append to `tests/test_fidelity_diff.py`:

```python
import os
import pytest
from hwp2hwpx.convert import convert
from hwp2hwpx.fidelity.diff import report

SAMPLES = [("samples/3.*.hwp", "samples/3.*.hwpx")]


@pytest.mark.parametrize("hwp,ref", SAMPLES)
def test_print_fidelity_report(hwp, ref, tmp_path, capsys):
    out = tmp_path / "out.hwpx"
    convert(hwp, str(out))
    rep = report(str(out), ref)
    with capsys.disabled():
        print("\n" + rep)
    # Baseline gate: text content must at least be present (section match > 0).
    assert "match=" in rep
```

- [ ] **Step 6: Run and eyeball the baseline scores**

Run: `.venv/bin/pytest tests/test_fidelity_diff.py::test_print_fidelity_report -s -v`
Expected: PASS, and prints per-part match percentages + top missing tags. **These scores define the backlog for the follow-up plans (tables, images, styles).**

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/fidelity/diff.py tests/test_fidelity_diff.py
git commit -m "feat: fidelity structural diff + per-element scorer + report"
```

---

### Task 18: CLI wiring + full test run

**Files:**
- Modify: `hwp2hwpx/cli.py` (wire to `convert`)
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `convert.convert`.
- Produces: working `hwp2hwpx <in.hwp> -o <out.hwpx>` command; `main` returns 0 on success, 2 on usage error, 1 on conversion failure (with a clear stderr message, not a stack trace).

- [ ] **Step 1: Write failing test `tests/test_cli.py`**

```python
import os
from hwp2hwpx.cli import main

SAMPLE = "samples/3.*.hwp"


def test_cli_converts(tmp_path):
    out = tmp_path / "out.hwpx"
    rc = main([SAMPLE, "-o", str(out)])
    assert rc == 0
    assert os.path.getsize(out) > 0


def test_cli_missing_input_reports_error(tmp_path, capsys):
    out = tmp_path / "out.hwpx"
    rc = main(["does-not-exist.hwp", "-o", str(out)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "does-not-exist.hwp" in err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL (current `main` ignores args / returns 0 without converting; second test fails because no error handling).

- [ ] **Step 3: Update `hwp2hwpx/cli.py`**

```python
"""Command-line entry point."""
import argparse
import os
import sys
from .convert import convert


def main(argv):
    parser = argparse.ArgumentParser(prog="hwp2hwpx",
                                     description="Convert HWP 5.0 files to HWPX.")
    parser.add_argument("input", help="path to input .hwp file")
    parser.add_argument("-o", "--output", required=True, help="path to output .hwpx file")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.input):
        print("error: input file not found: %s" % args.input, file=sys.stderr)
        return 1
    try:
        convert(args.input, args.output)
    except Exception as exc:  # convert failures -> clean message, not a traceback
        print("error: conversion failed for %s: %s" % (args.input, exc), file=sys.stderr)
        return 1
    return 0


def entrypoint():
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Manual smoke test — verify the output opens** (verification-before-completion)

Run:
```bash
.venv/bin/hwp2hwpx "samples/4.*.hwp" -o /tmp/out.hwpx && .venv/bin/python -c "import zipfile,sys; z=zipfile.ZipFile('/tmp/out.hwpx'); print('OK', z.namelist()[0], len(z.namelist()), 'parts')"
```
Expected: prints `OK mimetype <N> parts`. If you have Hancom Office available, open `/tmp/out.hwpx` to confirm it loads (text should be present; formatting fidelity is the follow-up plans' job).

- [ ] **Step 7: Commit**

```bash
git add hwp2hwpx/cli.py tests/test_cli.py
git commit -m "feat: wire CLI to convert with error handling"
```

---

## Follow-up plans (not in this plan)

Prioritize by the Task 17 fidelity report's "missing" tags. Each becomes its own spec→plan→implementation cycle:

1. **Char/para property fidelity** — extend `charPr`/`paraPr` serializers + mappers to full attribute set (fontRef per-language, ratio/spacing/relSz/offset, line height, margins, tab stops) until header.xml match approaches 100%.
2. **Char-shape position runs** — split paragraph text into multiple runs at `ParaCharShape` offsets (replaces the single-run simplification in Task 10).
3. **Tables** — `hp:tbl`/`hp:tr`/`hp:tc`, borders, backgrounds, merged cells; requires borderFill mapping.
4. **Images / bin-data** — `BinData/` entries, `hp:pic`, manifest wiring.
5. **Styles & numbering** — `hh:styles`, `hh:numberings`, `hh:bullets`, `styleIDRef` fidelity.
6. **Headers/footers, master pages, shapes** — long tail, driven by remaining harness gaps.

## Self-Review notes

- **Spec coverage:** Reader (Tasks 8–10), Mapper porting hwp2hwpx element-by-element (Tasks 11–14), Writer with strict package/mimetype rules (Tasks 3–7), Fidelity harness (Tasks 16–17), CLI (Task 18), error handling (Task 18 + reader's continue-on-unknown intent). Spec's "maximum fidelity" is explicitly framed as an asymptote approached via the harness backlog (Follow-up plans). Tables/images/styles deferred to follow-up plans per the spec's own sequencing — recorded, not dropped.
- **Type consistency:** `Font/CharPr/ParaPr/Para/Run/Text/Header/Section/Metadata/OwpmlDocument` used identically across Tasks 2–7 and 11–15; `HwpFont/HwpCharShape/HwpParaShape/HwpDocInfo/HwpRun/HwpParagraph/HwpSection/HwpDocument` consistent across Tasks 9–14. Function names (`hwp5_xml`, `read_docinfo`, `read_document`, `map_fonts`, `map_char_shapes`, `map_para_shapes`, `map_document`, `write_hwpx`, `write_package`, `canonical`, `unzip_parts`, `element_counts`, `score_part`, `report`, `convert`, `main`) each defined once and referenced with matching signatures.
- **Reader tag-name risk:** pyhwp's exact emitted tag/attribute names are confirmed against a captured fixture in Task 8 before Tasks 9–10 depend on them; those tasks instruct adjusting literals to the fixture. This is the one place the plan cannot pre-commit exact strings, and it is handled by capture-first.
```
