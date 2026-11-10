"""Bounded structural validation. This is not an antivirus scanner."""
import logging
import errno
import stat
import unicodedata
import warnings
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader

MIME_TYPES = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
              "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
Image.MAX_IMAGE_PIXELS = 25_000_000
# Parser warnings can contain fragments of untrusted document contents.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)


def validate_name(name: str | None):
    name = unicodedata.normalize("NFC", name or "").strip()
    decoded = unquote(unquote(name))
    if (not name or len(name) > 255 or any(char in decoded for char in "/\\")
            or any(ord(char) < 32 or ord(char) == 127 for char in decoded)
            or decoded in {".", ".."} or ":" in decoded):
        raise HTTPException(400, "اسم الملف غير صالح. استخدم اسمًا دون مسارات أو محارف تحكم.")
    extension = Path(name).suffix.lower().lstrip(".")
    if extension not in MIME_TYPES:
        raise HTTPException(415, "الأنواع المسموحة هي PDF وPNG وJPEG وDOCX فقط.")
    return name, extension


def validate_docx(path):
    with ZipFile(path) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        if len(entries) > 2000 or len(entries) != len(names):
            raise ValueError("archive limits")
        if not {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= names:
            raise ValueError("not Word OOXML")
        if sum(entry.file_size for entry in entries) > 50 * 1024 * 1024:
            raise ValueError("expanded size")
        for entry in entries:
            parts = PurePosixPath(entry.filename).parts
            if (entry.filename.startswith("/") or ".." in parts or "\\" in entry.filename or ":" in entry.filename
                    or entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16)
                    or entry.compress_type not in {0, 8}
                    or entry.file_size > 200 * max(1, entry.compress_size)
                    or "embeddings" in parts or entry.filename.lower().endswith(("vbaproject.bin", ".exe", ".dll", ".js", ".py"))):
                raise ValueError("unsafe archive")
            if entry.filename.endswith((".xml", ".rels")):
                if entry.file_size > 8 * 1024 * 1024:
                    raise ValueError("XML size")
                ElementTree.fromstring(archive.read(entry))
        if archive.testzip() is not None:
            raise ValueError("corrupt archive")
        content_types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
        expected_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        if not any(node.get("PartName") == "/word/document.xml" and node.get("ContentType") == expected_type for node in content_types):
            raise ValueError("invalid document content type")
        document = ElementTree.fromstring(archive.read("word/document.xml"))
        if document.tag not in {"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document",
                                "{http://purl.oclc.org/ooxml/wordprocessingml/main}document"}:
            raise ValueError("invalid document root")
        relationships = ElementTree.fromstring(archive.read("_rels/.rels"))
        if not any(node.get("Type", "").endswith("/officeDocument") and node.get("Target", "").lstrip("/") == "word/document.xml"
                   and node.get("TargetMode") != "External" for node in relationships):
            raise ValueError("invalid document relationship")


def validate_content(path: Path, extension: str):
    with path.open("rb") as stream:
        signature = stream.read(16)
    detected = ("pdf" if signature.startswith(b"%PDF-") else "png" if signature.startswith(b"\x89PNG\r\n\x1a\n")
                else "jpeg" if signature.startswith(b"\xff\xd8\xff") else "docx" if signature.startswith(b"PK\x03\x04") else None)
    expected = "jpeg" if extension in {"jpg", "jpeg"} else extension
    if detected != expected:
        raise HTTPException(415, "محتوى الملف لا يتطابق مع امتداده أو نوعه غير مدعوم.")
    try:
        if detected in {"png", "jpeg"}:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    if image.format != ("JPEG" if detected == "jpeg" else "PNG"):
                        raise ValueError("image mismatch")
                    image.verify()
                with Image.open(path) as image:
                    image.load()
        elif detected == "pdf":
            # Passing a path makes pypdf copy the whole file into BytesIO.
            # A seekable file handle keeps validation backed by disk instead.
            with path.open("rb") as pdf_stream:
                reader = PdfReader(pdf_stream, strict=True, xref_stream_maximum_entries=100_000)
                try:
                    if reader.is_encrypted:
                        raise ValueError("encrypted PDF")
                    root = reader.trailer["/Root"]
                    if root.get("/Type") != "/Catalog" or not 1 <= int(root["/Pages"]["/Count"]) <= 2000:
                        raise ValueError("invalid PDF page tree")
                    if not 1 <= len(reader.pages) <= 2000:
                        raise ValueError("PDF page limit")
                    for page in reader.pages:
                        if len(page.mediabox) != 4:
                            raise ValueError("invalid PDF page")
                finally:
                    reader.close()
        else:
            validate_docx(path)
    except OSError as error:
        if error.errno in {errno.EACCES, errno.EPERM, errno.EIO, errno.ENOSPC, errno.EROFS, errno.EMFILE, errno.ENFILE}:
            raise
        # File I/O failures are handled by the storage service; image decoding
        # failures may also be OSError, so report these as invalid content.
        raise HTTPException(415, "الملف تالف أو لا يمكن التحقق من بنيته.") from None
    except Exception:
        raise HTTPException(415, "الملف تالف أو مشفّر أو يتجاوز حدود فحص المحتوى.") from None
    return MIME_TYPES[extension]
