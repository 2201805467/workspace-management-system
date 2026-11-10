import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_engine
from .models import FileSearchIndex as Index, ProjectFile, utcnow

logger = logging.getLogger("workspace.indexer")


def process_one(engine=None):
    engine = engine or get_engine()
    settings = get_settings()
    with Session(engine) as db:
        cutoff = utcnow() - timedelta(seconds=settings.index_lease_seconds)
        job = db.scalar(
            select(Index)
            .where(
                or_(
                    Index.indexing_status == "pending",
                    (Index.indexing_status == "processing")
                    & (Index.updated_at < cutoff),
                )
            )
            .order_by(Index.updated_at, Index.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        file = db.get(ProjectFile, job.file_id)
        if not file or file.deleted_at:
            job.indexing_status = "failed"
            job.error_code = "deleted"
            job.extracted_text = ""
            job.lease_token = None
            db.commit()
            return True
        identifier, key, extension = job.id, file.storage_key, file.extension
        token = str(uuid4())
        job.lease_token = token
        job.indexing_status = "processing"
        job.updated_at = utcnow()
        db.commit()
    result = dict(text="", error=None)
    if extension in {"pdf", "docx"}:
        try:
            child = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "app.extract_document",
                    key,
                    extension,
                    str(settings.index_max_text_chars),
                    str(settings.index_max_pages),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=settings.index_timeout_seconds,
            )
            if child.returncode != 0:
                result["error"] = "resource_limit"
            else:
                result = json.loads(child.stdout)
        except subprocess.TimeoutExpired:
            result["error"] = "timeout"
        except Exception:
            result["error"] = "extraction_failed"
    with Session(engine) as db:
        job = db.scalar(
            select(Index)
            .where(
                Index.id == identifier,
                Index.lease_token == token,
                Index.indexing_status == "processing",
            )
            .with_for_update()
        )
        if job is None:
            return True  # Lease superseded, deleted or manually requeued.
        file = db.get(ProjectFile, job.file_id)
        if not file or file.deleted_at:
            result = dict(text="", error="deleted")
        job.extracted_text = (
            (result.get("text") or "")[: settings.index_max_text_chars]
            if not result.get("error")
            else ""
        )
        job.error_code = result.get("error")
        job.indexing_status = "failed" if job.error_code else "ready"
        if job.indexing_status == "ready":
            job.indexed_at = utcnow()
        job.updated_at = utcnow()
        job.lease_token = None
        db.commit()
        if job.error_code:
            logger.warning(
                "index_failed file_id=%s code=%s",
                file.id if file else identifier,
                job.error_code,
            )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--drain", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if args.rebuild:
        with Session(get_engine()) as db:
            db.execute(
                update(Index)
                .where(
                    Index.file_id.in_(
                        select(ProjectFile.id).where(ProjectFile.deleted_at.is_(None))
                    )
                )
                .values(
                    indexing_status="pending",
                    lease_token=None,
                    error_code=None,
                    updated_at=utcnow(),
                    extracted_text="",
                )
            )
            from sqlalchemy import text

            db.execute(text("UPDATE knowledge_articles SET title=title"))
            db.commit()
    while True:
        try:
            worked = process_one()
        except Exception as error:
            logger.error("index_worker_failure type=%s", type(error).__name__)
            worked = False
        if args.once or (args.drain and not worked):
            return
        if not worked:
            time.sleep(get_settings().index_poll_seconds)


if __name__ == "__main__":
    main()
