"""Private UUID-only storage. No original filename is ever part of a path."""
import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from .config import get_settings

logger = logging.getLogger("workspace.storage")
KEY = re.compile(r"^[0-9a-f]{32}$")
CHUNK_SIZE = 64 * 1024


class PrivateStorage:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or get_settings().file_storage_path).resolve()

    def initialize(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        (self.root / ".tmp").mkdir(mode=0o700, exist_ok=True)
        if (self.root / ".tmp").is_symlink():
            raise OSError("invalid private temporary directory")

    def path(self, key):
        if not KEY.fullmatch(key):
            raise OSError("invalid storage key")
        path = self.root / key
        if path.is_symlink():
            raise OSError("invalid storage entry")
        return path

    @contextmanager
    def temporary(self):
        self.initialize()
        path = self.root / ".tmp" / (uuid4().hex + ".part")
        try:
            with path.open("xb") as stream:
                os.chmod(path, 0o600)
                yield path, stream
        finally:
            self.cleanup(path)

    def promote(self, temporary: Path, key: str):
        final = self.path(key)
        # UUID collision is negligible; never intentionally replace a known entry.
        if final.exists():
            raise FileExistsError("storage collision")
        os.replace(temporary, final)
        return final

    def cleanup(self, path):
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            logger.error("storage_cleanup_failed type=%s", type(error).__name__)


def storage_unavailable(error):
    logger.error("storage_unavailable type=%s", type(error).__name__)
    return HTTPException(503, "خدمة تخزين الملفات غير متاحة مؤقتًا. حاول مجددًا.")
