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
