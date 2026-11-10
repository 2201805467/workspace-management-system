from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image
from pypdf import PdfWriter


def pdf_bytes():
    output = BytesIO()
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.write(output); writer.close()
    return output.getvalue()


def text_pdf_bytes(value='SearchablePdfNeedle operations handbook'):
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    output=BytesIO();writer=PdfWriter();page=writer.add_blank_page(width=400,height=400)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 20 300 Td ('+value.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')+') Tj ET').encode('ascii'))
    page[NameObject('/Contents')]=writer._add_object(stream);writer.write(output);writer.close();return output.getvalue()


def image_bytes(format="PNG", size=(4, 4)):
    output = BytesIO()
    Image.new("RGB", size, "green").save(output, format=format)
    return output.getvalue()


def docx_bytes(extra=None, text="Test document"):
    from xml.sax.saxutils import escape
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+escape(text)+'</w:t></w:r></w:p></w:body></w:document>')
        for name, data in (extra or {}).items(): archive.writestr(name, data)
    return output.getvalue()
