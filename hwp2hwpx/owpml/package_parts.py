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


_PACKAGE_NAMESPACES = (
    'xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"'
    ' xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
    ' xmlns:hp10="http://www.hancom.co.kr/hwpml/2016/paragraph"'
    ' xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
    ' xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"'
    ' xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'
    ' xmlns:hhs="http://www.hancom.co.kr/hwpml/2011/history"'
    ' xmlns:hm="http://www.hancom.co.kr/hwpml/2011/master-page"'
    ' xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf"'
    ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
    ' xmlns:opf="http://www.idpf.org/2007/opf/"'
    ' xmlns:ooxmlchart="http://www.hancom.co.kr/hwpml/2016/ooxmlchart"'
    ' xmlns:hwpunitchar="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar"'
    ' xmlns:epub="http://www.idpf.org/2007/ops"'
    ' xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0"'
)

# (opf:meta name, Metadata field), in emission order.
_META_FIELDS = (
    ("creator", "creator"),
    ("subject", "subject"),
    ("description", "description"),
    ("lastsaveby", "last_saved_by"),
    ("CreatedDate", "created_date"),
    ("ModifiedDate", "modified_date"),
    ("date", "date"),
    ("keyword", "keyword"),
)


def _meta_block(name, value):
    value = _esc(value)
    if not value:
        return '<opf:meta name="%s" content="text"/>' % name
    return '<opf:meta name="%s" content="text">%s</opf:meta>' % (name, value)


def content_hpf(metadata, section_count, bin_items=()):
    title = _esc(metadata.title)
    lang = _esc(metadata.language)
    meta_blocks = "".join(
        _meta_block(name, getattr(metadata, attr, ""))
        for name, attr in _META_FIELDS
    )
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
        '<opf:package %s version="" unique-identifier="" id="">'
        '<opf:metadata>'
        '<opf:title>%s</opf:title>'
        '<opf:language>%s</opf:language>'
        '%s'
        '</opf:metadata>'
        '<opf:manifest>%s</opf:manifest>'
        '<opf:spine>%s</opf:spine>'
        '</opf:package>'
    ) % (_PACKAGE_NAMESPACES, title, lang, meta_blocks, "".join(items), "".join(itemrefs))
    return _doc(body.encode("utf-8"))


def prv_text(sections):
    lines = []
    for sec in sections:
        for para in sec.paras:
            buf = []
            for run in para.runs:
                for t in run.texts:
                    c = getattr(t, "content", None)
                    if c:
                        buf.append(c)
            lines.append("".join(buf))
    return ("\n".join(lines)).encode("utf-8")
