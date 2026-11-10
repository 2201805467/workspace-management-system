"""Read-only storage reconciliation; also used by isolated restore checks."""
import argparse
import hashlib
import json
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_engine
from .file_storage import CHUNK_SIZE, KEY, PrivateStorage
from .models import ProjectFile


def audit(db, storage=None, *, verify_checksums=False, grace_seconds=3600):
    storage = storage or PrivateStorage()
    rows = db.execute(select(ProjectFile.id, ProjectFile.storage_key, ProjectFile.size_bytes,
                             ProjectFile.checksum, ProjectFile.deleted_at)).all()
    keys = {row.storage_key for row in rows}
    result = {"records": len(rows), "retained_deleted_bytes": sum(row.size_bytes for row in rows if row.deleted_at),
              "missing": [], "mismatched": [], "orphans": [], "stale_temporary": 0, "unavailable": 0}
    for row in rows:
        try:
            path = storage.path(row.storage_key)
            if not path.is_file():
                result["missing"].append(row.id)
                continue
            if path.stat().st_size != row.size_bytes:
                result["mismatched"].append(row.id)
            elif verify_checksums:
                checksum = hashlib.sha256()
                with path.open("rb") as stream:
                    while chunk := stream.read(CHUNK_SIZE): checksum.update(chunk)
                if checksum.hexdigest() != row.checksum:
                    result["mismatched"].append(row.id)
        except OSError:
            result["unavailable"] += 1
    if storage.root.is_dir():
        for path in storage.root.iterdir():
            if KEY.fullmatch(path.name) and path.name not in keys and time.time() - path.stat().st_mtime >= grace_seconds:
                result["orphans"].append(path.name)
        temporary = storage.root / ".tmp"
        if temporary.is_dir() and not temporary.is_symlink():
            result["stale_temporary"] = sum(1 for path in temporary.iterdir() if time.time() - path.stat().st_mtime > 86400)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-checksums", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    with Session(get_engine()) as db:
        report = audit(db, verify_checksums=args.verify_checksums)
    print(json.dumps(report))
    if args.strict and (report["missing"] or report["mismatched"] or report["unavailable"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
