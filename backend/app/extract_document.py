"""Untrusted parsers run in this short-lived, resource-limited child process."""

import json
import logging
import os
import sys
from zipfile import ZipFile


def extract(key, extension, max_chars=100000, max_pages=200):
    from .file_storage import PrivateStorage

    path = PrivateStorage().path(key)
    parts, length = [], 0

    def add(value):
        nonlocal length
        value = (
            (value or "")
            .replace("\0", "")
            .encode("utf-8", errors="replace")
            .decode("utf-8")
        )
        value = value[: max_chars - length]
        parts.append(value)
        length += len(value)

    if extension == "pdf":
        from pypdf import PdfReader

        logging.getLogger("pypdf").setLevel(logging.CRITICAL)
        with path.open("rb") as stream:
            reader = PdfReader(stream, strict=True, xref_stream_maximum_entries=100000)
            if reader.is_encrypted:
                raise ValueError("encrypted")
            if int(reader.trailer["/Root"]["/Pages"]["/Count"]) > max_pages:
                raise ValueError("page_limit")
            for page in reader.pages:
                add(page.extract_text() or "")
                add("\n")
                if length >= max_chars:
                    break
    elif extension == "docx":
        from defusedxml import ElementTree

        with ZipFile(path) as archive:
            entry = archive.getinfo("word/document.xml")
            if entry.file_size > 8 * 1024 * 1024:
                raise ValueError("xml_limit")
            root = ElementTree.fromstring(archive.read(entry))
            for node in root.iter():
                if node.tag.endswith("}t"):
                    add(node.text)
                    add(" ")
                if length >= max_chars:
                    break
    return "".join(parts).strip()


def main():
    # Docker also caps the entire worker. Linux caps this child independently.
    if os.name == "posix":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    try:
        value = extract(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        result = dict(text=value, error=None)
    except FileNotFoundError:
        result = dict(text="", error="missing_file")
    except MemoryError:
        result = dict(text="", error="resource_limit")
    except Exception:
        result = dict(text="", error="extraction_failed")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
